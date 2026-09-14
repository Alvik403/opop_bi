from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.ops import backup_restore


def test_backup_and_restore_round_trip(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "project"
    database_path = project_root / "runtime" / "dashboard.sqlite3"
    database_path.parent.mkdir(parents=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES ('original')")

    data_file = project_root / "data" / "data.xlsx"
    data_file.parent.mkdir(parents=True)
    data_file.write_bytes(b"sample-data")
    upload_file = project_root / "uploads" / "version.xlsx"
    upload_file.parent.mkdir(parents=True)
    upload_file.write_bytes(b"sample-upload")

    monkeypatch.setattr(backup_restore, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(backup_restore, "BACKUP_ROOT", project_root / "backups")
    archive = backup_restore.create_backup(project_root / "backups" / "test.zip")

    data_file.write_bytes(b"changed")
    upload_file.unlink()
    backup_restore.restore_backup(archive, confirmed=True)

    assert data_file.read_bytes() == b"sample-data"
    assert upload_file.read_bytes() == b"sample-upload"
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("original",)


def test_backup_uses_env_paths(tmp_path: Path, monkeypatch):
    custom_root = tmp_path / "volumes"
    database_path = custom_root / "db" / "app.sqlite3"
    database_path.parent.mkdir(parents=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES ('custom')")

    data_dir = custom_root / "excel"
    data_dir.mkdir()
    (data_dir / "data.xlsx").write_bytes(b"custom-data")
    uploads_dir = custom_root / "files"
    uploads_dir.mkdir()
    (uploads_dir / "version.xlsx").write_bytes(b"custom-upload")

    monkeypatch.setattr(backup_restore, "PROJECT_ROOT", tmp_path / "project")
    monkeypatch.setattr(backup_restore, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("UPLOADS_DIR", str(uploads_dir))

    archive = backup_restore.create_backup(tmp_path / "backups" / "custom.zip")
    (data_dir / "data.xlsx").write_bytes(b"changed")
    backup_restore.restore_backup(archive, confirmed=True)
    assert (data_dir / "data.xlsx").read_bytes() == b"custom-data"
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("custom",)
