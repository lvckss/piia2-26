"""CLI checks for plan v1, https://github.com/lvckss/piia2-26/issues/64#issuecomment-6448595256.

Fixtures contain synthetic bytes, never CARDD images or credentials.
"""

import functools
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/download_cardd.py"


class DownloadCarddTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.destination = self.root / "bd"
        self.files = {"rawdata/image_info.xlsx": b"synthetic excel"}
        for split in ("train", "test", "val"):
            self.files[f"rawdata/instances_{split}.json"] = json.dumps(
                {"images": [{"id": 1, "file_name": f"{split}.jpg"}],
                 "annotations": [], "categories": []}
            ).encode()
            self.files[f"clean_data/{split}/fullsize/{split}.jpg"] = b"synthetic image"
            self.files[f"clean_data/{split}/thumbnails/{split}.webp"] = b"synthetic thumb"
        self.archive = self.root / "dataset.tar.gz"
        self.make_archive()

    def make_archive(self, extra=None):
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, content in self.files.items():
                info = tarfile.TarInfo(name)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
            if extra is not None:
                archive.addfile(extra, io.BytesIO(b"x") if extra.isfile() else None)
        self.sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def cli(self, *args, env=None, sha=None):
        environment = os.environ.copy()
        for key in ("CARDD_URL", "CARDD_SHA256", "PYTHONPATH"):
            environment.pop(key, None)
        environment.update(env or {})
        return subprocess.run(
            [sys.executable, "-S", str(SCRIPT), "--destination", str(self.destination),
             "--sha256", sha or self.sha, *map(str, args)],
            env=environment, capture_output=True, text=True, timeout=30,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_rejected(self, result, message):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertFalse((self.destination / "rawdata").exists())
        self.assertFalse((self.destination / "clean_data").exists())
        self.assertFalse((self.destination / ".cardd-install.json").exists())

    def test_AC001_local_archive_installs_expected_files(self):
        self.assert_success(self.cli("--archive", self.archive))
        for name, data in self.files.items():
            self.assertEqual((self.destination / name).read_bytes(), data)
        self.assertTrue((self.destination / ".cardd-install.json").is_file())

    def test_AC001_http_archive_is_downloaded_and_verified(self):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        handler = functools.partial(Handler, directory=str(self.root))
        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/dataset.tar.gz"
                self.assert_success(self.cli("--url", url))
            finally:
                server.shutdown()
                worker.join()
        self.assertTrue((self.destination / "clean_data/test/fullsize/test.jpg").exists())

    def test_AC002_drive_uses_gdown_without_cookies(self):
        package = self.root / "gdown"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "__main__.py").write_text(
            "import json, os, pathlib, shutil, sys\n"
            "pathlib.Path(os.environ['GD_LOG']).write_text(json.dumps(sys.argv[1:]))\n"
            "shutil.copyfile(os.environ['GD_SOURCE'], sys.argv[sys.argv.index('--output')+1])\n"
        )
        url = "https://drive.google.com/file/d/synthetic-file-id/view?usp=sharing"
        log = self.root / "gdown-log.json"
        self.assert_success(self.cli(env={
            "CARDD_URL": url, "PYTHONPATH": str(self.root),
            "GD_SOURCE": str(self.archive), "GD_LOG": str(log),
        }))
        args = json.loads(log.read_text())
        self.assertIn(url, args)
        self.assertIn("--fuzzy", args)
        self.assertIn("--no-cookies", args)

    def test_AC002_missing_gdown_explains_dependency(self):
        self.assert_rejected(
            self.cli("--url", "https://drive.google.com/file/d/test/view"), "gdown"
        )

    def test_AC002_failed_drive_download_does_not_install(self):
        package = self.root / "gdown"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "__main__.py").write_text("raise SystemExit(1)\n")
        self.assert_rejected(self.cli(
            "--url", "https://drive.google.com/file/d/test/view",
            env={"PYTHONPATH": str(self.root)},
        ), "Drive")

    def test_AC002_missing_url_explains_configuration(self):
        self.assert_rejected(self.cli(), "CARDD_URL")

    def test_AC002_http_failure_does_not_install(self):
        self.assert_rejected(self.cli("--url", "http://127.0.0.1:1/no-file"), "descarga")

    def test_AC002_invalid_url_is_rejected(self):
        self.assert_rejected(self.cli("--url", "file:///etc/passwd"), "HTTP")

    def test_AC003_wrong_checksum_preserves_existing_files(self):
        self.destination.mkdir()
        sentinel = self.destination / "schema.sql"
        sentinel.write_text("preservar")
        self.assert_rejected(self.cli("--archive", self.archive, sha="0" * 64), "SHA-256")
        self.assertEqual(sentinel.read_text(), "preservar")

    def test_AC003_invalid_checksum_is_rejected(self):
        self.assert_rejected(self.cli("--archive", self.archive, sha="bad"), "SHA-256")

    def test_AC003_unsafe_tar_entries_are_rejected(self):
        for name, kind in (("../escaped", tarfile.REGTYPE),
                           ("/absolute", tarfile.REGTYPE),
                           ("rawdata/link", tarfile.SYMTYPE),
                           ("clean_data/link", tarfile.LNKTYPE),
                           ("rawdata/pipe", tarfile.FIFOTYPE),
                           ("unexpected/file", tarfile.REGTYPE)):
            with self.subTest(name=name, kind=kind):
                info = tarfile.TarInfo(name)
                info.type = kind
                info.linkname = "../../escaped" if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE} else ""
                info.size = 1 if kind == tarfile.REGTYPE else 0
                self.make_archive(info)
                self.assert_rejected(self.cli("--archive", self.archive), "Entrada no permitida")
                self.assertFalse((self.root / "escaped").exists())

    def test_AC003_duplicate_tar_entry_is_rejected(self):
        info = tarfile.TarInfo("rawdata/image_info.xlsx")
        info.size = 1
        self.make_archive(info)
        self.assert_rejected(self.cli("--archive", self.archive), "duplicada")

    def test_AC003_missing_metadata_is_rejected(self):
        del self.files["rawdata/instances_val.json"]
        self.make_archive()
        self.assert_rejected(self.cli("--archive", self.archive), "instances_val.json")

    def test_AC003_missing_referenced_image_is_rejected(self):
        del self.files["clean_data/test/fullsize/test.jpg"]
        self.make_archive()
        self.assert_rejected(self.cli("--archive", self.archive), "test.jpg")

    def test_AC003_annotation_path_cannot_escape(self):
        self.files["rawdata/instances_test.json"] = json.dumps(
            {"images": [{"file_name": "../../../rawdata/image_info.xlsx"}]}
        ).encode()
        self.make_archive()
        self.assert_rejected(self.cli("--archive", self.archive), "file_name")

    def test_AC003_bad_json_is_rejected(self):
        self.files["rawdata/instances_train.json"] = b"not json"
        self.make_archive()
        self.assert_rejected(self.cli("--archive", self.archive), "JSON")

    def test_AC003_invalid_tar_is_rejected(self):
        self.archive.write_bytes(b"not an archive")
        self.sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.assert_rejected(self.cli("--archive", self.archive), "archivo tar")

    def test_AC003_existing_destination_is_preserved(self):
        (self.destination / "rawdata").mkdir(parents=True)
        sentinel = self.destination / "rawdata/local.txt"
        sentinel.write_text("preservar")
        result = self.cli("--archive", self.archive)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("existentes", result.stderr)
        self.assertEqual(sentinel.read_text(), "preservar")
        self.assertFalse((self.destination / "clean_data").exists())

    def test_AC004_second_run_skips_missing_source(self):
        self.assert_success(self.cli("--archive", self.archive))
        self.archive.unlink()
        result = self.cli("--archive", self.archive)
        self.assert_success(result)
        self.assertIn("ya instalado", result.stdout)

    def test_AC004_partial_installation_is_detected_and_preserved(self):
        self.assert_success(self.cli("--archive", self.archive))
        image = self.destination / "clean_data/test/fullsize/test.jpg"
        image.unlink()
        result = self.cli("--archive", self.archive)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("incompleta", result.stderr)
        self.assertFalse(image.exists())

    def test_AC004_changed_file_size_is_detected(self):
        self.assert_success(self.cli("--archive", self.archive))
        image = self.destination / "clean_data/test/fullsize/test.jpg"
        image.write_bytes(b"changed")
        self.assertNotEqual(self.cli("--archive", self.archive).returncode, 0)
        self.assertEqual(image.read_bytes(), b"changed")

    def test_AC005_data_and_local_state_are_ignored(self):
        app = ROOT / "entregas/cu-19-interpretacion-danos/app"
        paths = [app / "bd/rawdata/image_info.xlsx", app / "bd/clean_data/test/fullsize/test.jpg",
                 app / "bd/.cardd-install.json", app / "bd/.cardd-stage-test/file"]
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", *map(str, paths)],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(len(result.stdout.splitlines()), len(paths), result.stdout)


if __name__ == "__main__":
    unittest.main()
