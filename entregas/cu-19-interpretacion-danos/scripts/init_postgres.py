"""Initialize the shared Docker PostgreSQL once (spec 32, AC-013)."""

from pathlib import Path
import os
import re
import secrets
import shlex
import subprocess
from urllib.parse import quote

CASE = Path(__file__).resolve().parents[1]


def read_config(path):
    return {
        key: shlex.split(value)[0]
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
        for key, value in [line.split("=", 1)]
    }


def private_write(path, text):
    with open(path, "x", encoding="utf-8", opener=lambda p, flags: os.open(p, flags, 0o600)) as out:
        out.write(text)


def main():
    config_file = CASE / ".env.postgres"
    if not config_file.exists():
        private_write(config_file, "POSTGRES_DB=cardd_webapp\nPOSTGRES_USER=postgres\n"
                      f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
                      f"POSTGRES_PORT={int(os.environ.get('POSTGRES_PORT', '5433'))}\n")
    config = read_config(config_file)
    if not config.get("POSTGRES_PASSWORD"):
        raise ValueError("POSTGRES_PASSWORD no puede estar vacía")
    env = os.environ.copy()
    env.update(config)
    compose = ["docker", "compose", "--env-file", str(config_file), "-f", str(CASE / "compose.yaml")]
    subprocess.run([*compose, "up", "-d", "--wait", "postgres"], env=env, check=True)
    check = ("SELECT (to_regclass('public.imagenes') IS NOT NULL AND "
             "to_regclass('public.instancias') IS NOT NULL AND "
             "to_regclass('public.etiquetas') IS NOT NULL AND "
             "EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector'))::int")
    result = subprocess.run(
        [*compose, "exec", "-T", "postgres", "sh", "-c",
         'exec psql -XqAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"', "sh", check],
        env=env, capture_output=True, text=True, check=True,
    )
    if result.stdout.strip() != "1":
        raise RuntimeError("La base no tiene el esquema esperado; se conserva app/.env")
    user = quote(config.get("POSTGRES_USER", "postgres"), safe="")
    password = quote(config["POSTGRES_PASSWORD"], safe="")
    database = quote(config.get("POSTGRES_DB", "cardd_webapp"), safe="")
    port = int(config.get("POSTGRES_PORT", "5433"))
    line = f"DATABASE_URL=postgresql://{user}:{password}@127.0.0.1:{port}/{database}"
    app_env = CASE / "app/.env"
    app_env.parent.mkdir(exist_ok=True)
    before = app_env.read_text() if app_env.exists() else ""
    if re.search(r"(?m)^(?:export )?DATABASE_URL=", before):
        after = re.sub(r"(?m)^(?:export )?DATABASE_URL=.*$", lambda _: line, before)
    else:
        after = before + ("\n" if before and not before.endswith("\n") else "") + line + "\n"
    if after != before:
        backup = app_env.with_name(".env.before-docker")
        if before and not backup.exists():
            private_write(backup, before)
        temp = app_env.with_name(".env.initializing")
        private_write(temp, after)
        temp.replace(app_env)
    print(f"PostgreSQL preparada en Docker (127.0.0.1:{port}); app/.env configurado. Próximos arranques: just db-up.")


if __name__ == "__main__":
    main()
