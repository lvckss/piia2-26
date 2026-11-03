"""Copy PostgreSQL to an empty destination, preserving the source (32/AC-013).

Uses the PostgreSQL CLI, with credentials in subprocess environment variables.
No dependency on OpenAI, Docker SDK, ORM or a particular explorer table layout.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
from urllib.parse import parse_qs, quote, unquote, urlparse

CASE = Path(__file__).resolve().parents[1]
PREPARE_SQL = CASE / "app/bd/docker/10-vector.sql"


class MigrationError(Exception):
    pass


def load_env(path):
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator:
            values = shlex.split(value, comments=True)
            result[key.strip()] = " ".join(values)
    return result


def connection(url):
    u = urlparse(url)
    if u.scheme not in ("postgres", "postgresql") or not u.hostname or not u.path.strip("/"):
        raise MigrationError("DATABASE_URL debe identificar un servidor y una base PostgreSQL.")
    env = os.environ.copy()
    # Explicit connection details prevent inherited PG* settings selecting another DB.
    for key in list(env):
        if key.startswith("PG"):
            del env[key]
    env.update(PGHOST=u.hostname, PGPORT=str(u.port or 5432),
               PGUSER=unquote(u.username or "postgres"), PGPASSWORD=unquote(u.password or ""),
               PGDATABASE=unquote(u.path.lstrip("/")), PGCONNECT_TIMEOUT="10")
    options = parse_qs(u.query)
    for key in ("sslmode", "sslrootcert", "sslcert", "sslkey"):
        if key in options:
            env["PG" + key.upper()] = options[key][0]
    return env


def call(args, env):
    r = subprocess.run(args, env=env, capture_output=True)
    if r.returncode:
        # Do not echo stderr: SQL errors may contain data, queries or credentials.
        raise MigrationError(f"{args[0]} ha fallado (código {r.returncode}); no se cambia la conexión de la aplicación.")
    return r.stdout


def sql(env, query):
    return call(["psql", "-XqAt", "--no-password", "-v", "ON_ERROR_STOP=1", "-c", query], env).decode().strip()


def identifier(name):
    return '"' + name.replace('"', '""') + '"'


def canonical_constraint(definition):
    """Canonicalize only varchar-literal-array -> text[] cast distribution.

    pg_dump/restore can turn (ARRAY['x'::varchar])::text[] into
    ARRAY[('x'::varchar)::text]. Preserve all other expressions and casts.
    """
    literal = r"'(?:[^']|'')*'::character varying"
    pattern = r"\(ARRAY\[((?:" + literal + r")(?:,\s*" + literal + r")*)\]\)::text\[\]"
    return re.sub(pattern, lambda match: "ARRAY[" + ", ".join(
        "(" + value + ")::text" for value in re.findall(literal, match.group(1))) + "]", definition)


def relations(env):
    return json.loads(sql(env, """SELECT coalesce(json_agg(x ORDER BY schema, name),'[]') FROM (
      SELECT n.nspname AS schema, c.relname AS name, c.relkind::text AS kind
      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname NOT IN ('pg_catalog','information_schema')
        AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp%'
        AND c.relkind IN ('r','p','S','v','m','f')
        AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_class'::regclass
          AND d.objid=c.oid AND d.deptype='e')
    ) x"""))


def snapshot(env):
    result = {"relations": relations(env), "tables": {}, "sequences": {}}
    for rel in result["relations"]:
        table = identifier(rel["schema"]) + "." + identifier(rel["name"])
        if rel["kind"] in ("r", "p", "m", "f"):
            # ONLY keeps partition contents from being counted both in parent and child.
            data = call(["psql", "-XqAt", "--no-password", "-v", "ON_ERROR_STOP=1", "-c",
                         f'COPY (SELECT row_to_json(t)::text FROM ONLY {table} t '
                         f'ORDER BY row_to_json(t)::text COLLATE "C") TO STDOUT'], env)
            result["tables"][table] = {
                "rows": int(sql(env, f"SELECT count(*) FROM ONLY {table}")),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        if rel["kind"] == "S":
            result["sequences"][table] = json.loads(sql(env,
                f"SELECT json_build_object('last_value',last_value,'is_called',is_called) FROM {table}"))
    result["columns"] = json.loads(sql(env, """SELECT coalesce(json_agg(x ORDER BY table_schema,table_name,ordinal_position),'[]')
      FROM (SELECT table_schema,table_name,column_name,ordinal_position,data_type,udt_name,
                   is_nullable,column_default FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog','information_schema','rag')) x"""))
    result["constraints"] = json.loads(sql(env, """SELECT coalesce(json_agg(x ORDER BY schema,table_name,name),'[]')
      FROM (SELECT n.nspname AS schema,c.relname AS table_name,k.conname AS name,
                   pg_get_constraintdef(k.oid) AS definition
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema')) x"""))
    for constraint in result["constraints"]:
        constraint["definition"] = canonical_constraint(constraint["definition"])
    result["indexes"] = json.loads(sql(env, """SELECT coalesce(json_agg(x ORDER BY schemaname,tablename,indexname),'[]')
      FROM (SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes
            WHERE schemaname NOT IN ('pg_catalog','information_schema')) x"""))
    return result


def target_url(config):
    if not config.get("POSTGRES_PASSWORD"):
        raise MigrationError("Falta POSTGRES_PASSWORD en la configuración de destino.")
    port = int(config.get("POSTGRES_PORT", "5433"))
    user = quote(config.get("POSTGRES_USER", "postgres"), safe="")
    password = quote(config["POSTGRES_PASSWORD"], safe="")
    database = quote(config.get("POSTGRES_DB", "cardd_webapp"), safe="")
    return f"postgresql://{user}:{password}@127.0.0.1:{port}/{database}"


def private_write(path, content):
    # Refuse existing backups/configuration rather than silently replacing them.
    with open(path, "x", encoding="utf-8", opener=lambda p, flags: os.open(p, flags, 0o600)) as out:
        out.write(content)


def configure(args):
    if args.target_env.exists():
        target_url(load_env(args.target_env))
        print("Configuración PostgreSQL existente conservada.")
        return
    source = load_env(args.source_env).get("DATABASE_URL") if args.source_env.exists() else None
    u = urlparse(source) if source else None
    database = unquote(u.path.lstrip("/")) if u else "cardd_webapp"
    user = unquote(u.username or "postgres") if u else "postgres"
    # shlex.quote is also a valid single-quoted dotenv value for these identifiers.
    content = (f"POSTGRES_DB={shlex.quote(database)}\nPOSTGRES_USER={shlex.quote(user)}\n"
               f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\nPOSTGRES_PORT=5433\n")
    private_write(args.target_env, content)
    print("Configuración PostgreSQL creada con contraseña aleatoria privada. Puerto local: 5433.")


def migrate(args):
    original = args.source_env.read_text()
    source_url = load_env(args.source_env).get("DATABASE_URL")
    if not source_url:
        raise MigrationError("Falta DATABASE_URL en el archivo de origen.")
    source = connection(source_url)
    if not args.execute:
        print("Sin cambios. Se copiará la base de origen a un destino vacío; "
              "usa --execute y, para cambiar la aplicación tras verificar, --update-app-env.")
        return
    destination_url = target_url(load_env(args.target_env))
    destination = connection(destination_url)
    a = sql(source, "SELECT system_identifier FROM pg_control_system()")
    b = sql(destination, "SELECT system_identifier FROM pg_control_system()")
    if a == b and source["PGDATABASE"] == destination["PGDATABASE"]:
        raise MigrationError("Origen y destino son la misma base; no se realiza la copia.")
    if not args.verify_backup and relations(destination):
        raise MigrationError("El destino ya contiene objetos o datos; se rechaza la restauración.")

    before = snapshot(source)
    if args.verify_backup:
        # Resume checking an existing copy; this path never restores or overwrites tables.
        backup = args.verify_backup
        archive = backup / "database.dump"
        if not archive.is_file() or (backup / "app.env.before").read_text() != original:
            raise MigrationError("El respaldo no corresponde al archivo de conexión de origen.")
    else:
        args.backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        backup = args.backup_dir / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup.mkdir(mode=0o700)
        private_write(backup / "app.env.before", original)
        archive = backup / "database.dump"
        # pg_dump opens the archive itself; reserve it first with private permissions.
        archive.touch(mode=0o600, exist_ok=False)
        call(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(archive)], source)
        if snapshot(source) != before:
            raise MigrationError("El origen cambió durante el dump. Se conserva la copia; reintenta sin escrituras concurrentes.")
        call(["pg_restore", "--no-owner", "--no-acl", "--exit-on-error", "--single-transaction",
              "--dbname", destination["PGDATABASE"], str(archive)], destination)
    after = snapshot(destination)
    if after != before or snapshot(source) != before:
        raise MigrationError("La comparación de origen y destino no coincide; se conserva la conexión original.")
    sql(destination, PREPARE_SQL.read_text())
    if sql(destination, "SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector") != "1":
        raise MigrationError("La extensión vector no supera la comprobación.")
    with archive.open("rb") as stream:
        archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {"source": before, "destination": after,
                "postgres_version": sql(destination, "SHOW server_version"),
                "pgvector_version": sql(destination, "SELECT extversion FROM pg_extension WHERE extname='vector'"),
                "archive_sha256": archive_hash}
    record = backup / "verification.json"
    if record.exists():
        if json.loads(record.read_text()) != manifest:
            raise MigrationError("El manifiesto previo del respaldo no coincide; no se sobrescribe.")
    else:
        private_write(record, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    if args.update_app_env:
        if args.source_env.read_text() != original:
            raise MigrationError("El archivo de conexión cambió durante la migración; no se sobrescribe.")
        updated, count = re.subn(r"(?m)^(?:export )?DATABASE_URL=.*$", "DATABASE_URL=" + destination_url, original)
        if count != 1:
            raise MigrationError("Se esperaba una sola DATABASE_URL; revisa la configuración.")
        temp = args.source_env.with_name(args.source_env.name + ".migrating")
        private_write(temp, updated)
        temp.replace(args.source_env)
    print(json.dumps({"verified": True, "tables": {k: v["rows"] for k, v in before["tables"].items()},
                      "backup": str(backup), "application_connection_updated": args.update_app_env}, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--configure", action="store_true", help="create private .env.postgres without overwriting")
    mode.add_argument("--execute", action="store_true", help="copy into an empty, already running PostgreSQL")
    parser.add_argument("--update-app-env", action="store_true", help="update the source env file only after verification")
    parser.add_argument("--source-env", type=Path, default=CASE / "app/.env")
    parser.add_argument("--target-env", type=Path, default=CASE / ".env.postgres")
    parser.add_argument("--backup-dir", type=Path, default=CASE / "backups/postgres")
    parser.add_argument("--verify-backup", type=Path, help="only recheck an existing copy and its backup; never restore")
    args = parser.parse_args(argv)
    try:
        if args.configure:
            configure(args)
        else:
            migrate(args)
    except (MigrationError, OSError, ValueError) as error:
        # Unexpected exceptions propagate rather than appearing as a successful copy.
        message = str(error) if isinstance(error, MigrationError) else "Revisa archivos, permisos, herramientas PostgreSQL y configuración."
        print("Error: " + message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
