"""Spec specs/32-rag-normativa.md, AC-013 and preservation of explorer data.

Use a disposable PostgreSQL with pgvector installed, not a mock of SQL:
POSTGRES_TEST_URL must point at its administrative database. Each test creates
and drops only databases with a random cu19_test_ prefix.
"""

import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlparse, urlunparse
import uuid

SCRIPT = Path(__file__).resolve().parents[1] / "migrate_postgres.py"


class ConstraintRoundTripTests(unittest.TestCase):
    def test_ac013_cast_distribution_does_not_hide_a_changed_constraint(self):
        spec = importlib.util.spec_from_file_location("migration", SCRIPT)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        source = "CHECK (((split)::text = ANY ((ARRAY['train'::character varying, 'test'::character varying])::text[])))"
        restored = "CHECK (((split)::text = ANY (ARRAY[('train'::character varying)::text, ('test'::character varying)::text])))"
        self.assertEqual(migration.canonical_constraint(source), migration.canonical_constraint(restored))
        self.assertNotEqual(migration.canonical_constraint(source),
                            migration.canonical_constraint(restored.replace("'test'", "'other'")))


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_URL"), "requires disposable POSTGRES_TEST_URL")
class PostgresIntegrationTests(unittest.TestCase):
    def sql(self, url, query):
        u = urlparse(url)
        env = os.environ.copy()
        env.update(PGHOST=u.hostname, PGPORT=str(u.port or 5432),
                   PGUSER=unquote(u.username), PGPASSWORD=unquote(u.password or ""),
                   PGDATABASE=unquote(u.path.lstrip("/")))
        return subprocess.check_output(
            ["psql", "-XqAt", "--no-password", "-v", "ON_ERROR_STOP=1", "-c", query],
            env=env, text=True, stderr=subprocess.PIPE,
        ).strip()

    def setUp(self):
        self.admin = os.environ["POSTGRES_TEST_URL"]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.names = ["cu19_test_" + uuid.uuid4().hex for _ in range(2)]
        for name in self.names:
            self.sql(self.admin, f'CREATE DATABASE "{name}"')
            self.addCleanup(self.sql, self.admin, f'DROP DATABASE "{name}" WITH (FORCE)')
        u = urlparse(self.admin)
        self.source, self.target = [urlunparse(u._replace(path="/" + name)) for name in self.names]
        self.sql(self.source, "CREATE TABLE items(id serial PRIMARY KEY, data jsonb NOT NULL); "
                 "CREATE INDEX items_data ON items USING gin(data); "
                 "INSERT INTO items(data) VALUES ('{\"clase\":\"daño\"}'), ('{\"n\":2}'); "
                 "SELECT setval('items_id_seq',42,true)")
        self.source_env = self.root / "app.env"
        self.source_env.write_text("OTHER_SETTING=preserved\nDATABASE_URL=" + self.source + "\n")
        self.target_env = self.root / "postgres.env"
        self.target_env.write_text(
            f"POSTGRES_USER={unquote(u.username)}\nPOSTGRES_PASSWORD={unquote(u.password or '')}\n"
            f"POSTGRES_DB={self.names[1]}\nPOSTGRES_PORT={u.port or 5432}\n"
        )
        self.backups = self.root / "backups"

    def migrate(self, *extra, source=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--source-env", str(source or self.source_env),
             "--target-env", str(self.target_env), "--backup-dir", str(self.backups), *extra],
            text=True, capture_output=True,
        )

    def test_ac013_service_prepares_vector_without_modifying_explorer(self):
        self.assertEqual(self.sql(self.admin, "SELECT extversion FROM pg_extension WHERE extname='vector'"), "0.8.7")
        self.assertEqual(self.sql(self.admin, "SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector"), "1")
        self.assertEqual(self.sql(self.admin, "SELECT count(*) FROM pg_namespace WHERE nspname='rag'"), "1")

    def test_ac013_dry_run_does_not_change_connections_or_data(self):
        before = self.source_env.read_bytes()
        r = self.migrate()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Sin cambios", r.stdout)
        self.assertNotIn(unquote(urlparse(self.source).password), r.stdout + r.stderr)
        self.assertEqual(self.source_env.read_bytes(), before)
        self.assertFalse(self.backups.exists())
        self.assertEqual(self.sql(self.target, "SELECT count(*) FROM pg_tables WHERE schemaname='public'"), "0")

    def test_ac013_refuses_nonempty_target_and_preserves_source(self):
        self.sql(self.target, "CREATE TABLE keep(value int); INSERT INTO keep VALUES (7)")
        before = self.source_env.read_bytes()
        r = self.migrate("--execute", "--update-app-env")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("destino", r.stderr.lower())
        self.assertEqual(self.sql(self.target, "SELECT value FROM keep"), "7")
        self.assertEqual(self.sql(self.source, "SELECT count(*) FROM items"), "2")
        self.assertEqual(self.source_env.read_bytes(), before)

    def test_ac013_copy_preserves_rows_sequences_and_configuration(self):
        expected = self.sql(self.source, "SELECT json_agg(t ORDER BY id) FROM items t")
        r = self.migrate("--execute", "--update-app-env")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.sql(self.target, "SELECT json_agg(t ORDER BY id) FROM items t"), expected)
        self.assertEqual(self.sql(self.source, "SELECT json_agg(t ORDER BY id) FROM items t"), expected)
        self.assertEqual(self.sql(self.target, "SELECT last_value || ':' || is_called FROM items_id_seq"), "42:true")
        self.assertEqual(self.sql(self.target, "SELECT count(*) FROM pg_indexes WHERE tablename='items'"), "2")
        self.assertEqual(self.sql(self.target, "SELECT extversion FROM pg_extension WHERE extname='vector'"), "0.8.7")
        self.assertIn("OTHER_SETTING=preserved", self.source_env.read_text())
        self.assertNotIn(self.source + "\n", self.source_env.read_text())
        archives = list(self.backups.glob("*/database.dump"))
        self.assertEqual(len(archives), 1)
        self.assertEqual(stat.S_IMODE(archives[0].stat().st_mode), 0o600)
        old_env = archives[0].parent / "app.env.before"
        self.assertIn(self.source, old_env.read_text())
        repeat = self.migrate("--execute", source=old_env)
        self.assertNotEqual(repeat.returncode, 0)
        self.assertEqual(self.sql(self.target, "SELECT count(*) FROM items"), "2")
        recheck = self.migrate("--execute", "--verify-backup", str(archives[0].parent), source=old_env)
        self.assertEqual(recheck.returncode, 0, recheck.stderr)
        self.assertEqual(self.sql(self.target, "SELECT count(*) FROM items"), "2")


if __name__ == "__main__":
    unittest.main()
