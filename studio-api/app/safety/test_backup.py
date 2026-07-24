from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path

from .backup import BackupError, create_backup, restore_backup, verify_backup


class BackupRecoveryTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        repo = root / "repo"
        data = repo / "data"
        (data / "projects" / "sample-project").mkdir(parents=True)
        (data / "projects" / "sample-project" / "project.json").write_text(
            '{"name":"sample"}', encoding="utf-8"
        )
        (data / "secrets").mkdir()
        (data / "secrets" / "master.key").write_bytes(b"opaque-secret-bytes")
        (repo / "workflows").mkdir(parents=True)
        (repo / "workflows" / "scene.json").write_text("{}", encoding="utf-8")
        (repo / "studio-api" / "app" / "workflows").mkdir(parents=True)
        (repo / "studio-api" / "app" / "workflows" / "builder.py").write_text(
            "WORKFLOW = {}\n", encoding="utf-8"
        )
        (repo / "studio-api" / "knowledgebase").mkdir(parents=True)
        (repo / "studio-api" / "knowledgebase" / "guide.md").write_text(
            "# Guide\n", encoding="utf-8"
        )
        with closing(sqlite3.connect(data / "studio.db")) as connection:
            connection.execute("CREATE TABLE projects (id TEXT PRIMARY KEY)")
            connection.execute("INSERT INTO projects VALUES ('sample')")
            connection.commit()
        return repo, data

    def test_create_verify_and_isolated_restore(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, data = self._fixture(root)
            archive = root / "backup.zip"
            manifest = create_backup(archive, repo_root=repo, data_dir=data)

            self.assertEqual(manifest["schema_version"], 1)
            verified = verify_backup(archive)
            self.assertEqual(manifest, verified)
            secret_entry = next(
                item
                for item in manifest["entries"]
                if item["path"] == "data/secrets/master.key"
            )
            self.assertTrue(secret_entry["sensitive"])
            self.assertNotIn("opaque-secret-bytes", json.dumps(manifest))

            destination = root / "isolated-restore"
            restore_backup(
                archive,
                destination,
                repo_root=repo,
                data_dir=data,
            )
            with closing(
                sqlite3.connect(destination / "data" / "studio.db")
            ) as connection:
                self.assertEqual(
                    connection.execute("SELECT id FROM projects").fetchone(),
                    ("sample",),
                )

    def test_restore_refuses_existing_or_live_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, data = self._fixture(root)
            archive = root / "backup.zip"
            create_backup(archive, repo_root=repo, data_dir=data)

            with self.assertRaises(BackupError):
                restore_backup(archive, data, repo_root=repo, data_dir=data)
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaises(BackupError):
                restore_backup(archive, existing, repo_root=repo, data_dir=data)

    def test_verify_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("../outside.txt", b"unsafe")
            with self.assertRaises(BackupError):
                verify_backup(archive)


if __name__ == "__main__":
    unittest.main()
