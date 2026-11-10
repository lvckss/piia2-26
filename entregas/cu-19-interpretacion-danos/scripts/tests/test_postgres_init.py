"""Spec 32, AC-013: one-command Docker setup and persistent subsequent starts.

RUN_POSTGRES_INTEGRATION=1 runs this with an isolated Compose project and volume.
POSTGRES_BASELINE_REF optionally reproduces the missing behavior on a Git ref.
"""

import os
import importlib.util
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import uuid

CASE = Path(__file__).resolve().parents[2]


class PostgresConfigTests(unittest.TestCase):
    def test_ac013_empty_password_has_explicit_error_before_docker(self):
        spec = importlib.util.spec_from_file_location("init_postgres_test", CASE / "scripts/init_postgres.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory)
            for value in ("", '""', "''"):
                with self.subTest(value=value):
                    (case / ".env.postgres").write_text("POSTGRES_PASSWORD=" + value + "\n")
                    with patch.object(module, "CASE", case), patch.object(module.subprocess, "run") as docker:
                        with self.assertRaisesRegex(ValueError, "POSTGRES_PASSWORD no puede estar vacía"):
                            module.main()
                        docker.assert_not_called()


@unittest.skipUnless(os.environ.get("RUN_POSTGRES_INTEGRATION") == "1", "requires Docker integration opt-in")
class PostgresInitTests(unittest.TestCase):
    def test_ac013_init_and_up_preserve_data_and_private_configuration(self):
        with tempfile.TemporaryDirectory(prefix="cu19 postgres ") as directory:
            case = Path(directory)
            files = ["justfile", "compose.yaml", "scripts/init_postgres.py",
                     "app/bd/schema.sql", "app/bd/docker/10-vector.sql"]
            baseline = os.environ.get("POSTGRES_BASELINE_REF")
            for name in files:
                target = case / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if baseline:
                    relative = (CASE / name).relative_to(CASE.parents[1]).as_posix()
                    result = subprocess.run(["git", "show", baseline + ":" + relative],
                                            cwd=CASE.parents[1], capture_output=True)
                    if result.returncode == 0:
                        target.write_bytes(result.stdout)
                else:
                    shutil.copyfile(CASE / name, target)
            (case / "app/.env").write_text("OTHER_SETTING=kept\nDATABASE_URL=postgresql://old:old@localhost:5432/old\n")
            env = os.environ.copy()
            env["COMPOSE_PROJECT_NAME"] = "cu19-init-test-" + uuid.uuid4().hex[:10]
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                env["POSTGRES_PORT"] = str(listener.getsockname()[1])
            compose = ["docker", "compose", "--env-file", str(case / ".env.postgres"),
                       "-f", str(case / "compose.yaml")]

            def command(args):
                return subprocess.run(args, cwd=case, env=env, capture_output=True, text=True)

            def sql(query):
                result = command([*compose, "exec", "-T", "postgres", "sh", "-c",
                                  'exec psql -XqAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"',
                                  "sh", query])
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout.strip()

            try:
                initialized = command(["just", "db-init"])
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                self.assertEqual(sql("SELECT count(*) FROM imagenes"), "0")
                self.assertEqual(sql("SELECT count(*) FROM instancias"), "0")
                self.assertEqual(sql("SELECT extversion FROM pg_extension WHERE extname='vector'"), "0.8.7")
                self.assertEqual(sql("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector"), "1")
                self.assertEqual(sql("SELECT count(*) FROM pg_namespace WHERE nspname='rag'"), "1")
                config = (case / ".env.postgres").read_bytes()
                app_env = (case / "app/.env").read_text()
                self.assertIn("OTHER_SETTING=kept", app_env)
                self.assertIn("@127.0.0.1:" + env["POSTGRES_PORT"], app_env)
                self.assertEqual((case / ".env.postgres").stat().st_mode & 0o777, 0o600)
                sql("INSERT INTO etiquetas(nombre) VALUES ('bootstrap-test')")
                repeated = command(["just", "db-init"])
                self.assertEqual(repeated.returncode, 0, repeated.stderr)
                self.assertEqual((case / ".env.postgres").read_bytes(), config)
                self.assertEqual((case / "app/.env").read_text(), app_env)
                self.assertEqual(command([*compose, "stop", "postgres"]).returncode, 0)
                self.assertEqual(command(["just", "db-up"]).returncode, 0)
                self.assertEqual(sql("SELECT count(*) FROM etiquetas"), "1")
                self.assertEqual(command([*compose, "up", "-d", "--force-recreate", "--wait", "postgres"]).returncode, 0)
                self.assertEqual(sql("SELECT count(*) FROM etiquetas"), "1")
            finally:
                if (case / ".env.postgres").exists():
                    cleanup = command([*compose, "down", "--volumes"])
                    self.assertEqual(cleanup.returncode, 0, cleanup.stderr)


if __name__ == "__main__":
    unittest.main()
