from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_ROOT = PROJECT_ROOT / "backups"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def env_path(name: str, default: str) -> Path:
    raw = os.environ.get(name, default)
    path = Path(raw)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def database_path() -> Path:
    return env_path("DATABASE_PATH", "runtime/dashboard.sqlite3")


def data_dir() -> Path:
    return env_path("DATA_DIR", "data")


def uploads_dir() -> Path:
    return env_path("UPLOADS_DIR", "uploads")


def create_backup(output: Path | None) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = output or BACKUP_ROOT / f"opop-bi-{timestamp}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        database_copy = temp_dir / "dashboard.sqlite3"
        source_database = database_path()
        if not source_database.is_file():
            raise FileNotFoundError(f"Database not found: {source_database}")
        with closing(sqlite3.connect(source_database)) as source, closing(
            sqlite3.connect(database_copy)
        ) as target:
            source.backup(target)

        files: list[tuple[Path, str]] = [(database_copy, "runtime/dashboard.sqlite3")]
        for archive_prefix, directory in (("data", data_dir()), ("uploads", uploads_dir())):
            if not directory.exists():
                continue
            for path in directory.rglob("*"):
                if path.is_file() and ".incoming" not in path.parts:
                    files.append((path, f"{archive_prefix}/{path.relative_to(directory).as_posix()}"))

        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "files": {archive_name: sha256_file(path) for path, archive_name in files},
        }
        with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for path, archive_name in files:
                archive.write(path, archive_name)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    return destination


def restore_backup(archive_path: Path, *, confirmed: bool) -> None:
    if not confirmed:
        raise ValueError("Restore requires --confirm and the application must be stopped")
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        with ZipFile(archive_path) as archive:
            names = archive.namelist()
            if "manifest.json" not in names:
                raise ValueError("Backup manifest is missing")
            for name in names:
                target = (temp_dir / name).resolve()
                if temp_dir.resolve() not in target.parents and target != temp_dir.resolve():
                    raise ValueError("Unsafe path in backup archive")
            archive.extractall(temp_dir)

        manifest = json.loads((temp_dir / "manifest.json").read_text(encoding="utf-8"))
        for name, expected_hash in manifest["files"].items():
            restored = temp_dir / name
            if not restored.is_file() or sha256_file(restored) != expected_hash:
                raise ValueError(f"Backup integrity check failed: {name}")

        db_source = temp_dir / "runtime" / "dashboard.sqlite3"
        if db_source.is_file():
            destination = database_path()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_source, destination)

        for archive_name, destination_dir in (("data", data_dir()), ("uploads", uploads_dir())):
            source = temp_dir / archive_name
            if not source.exists():
                continue
            destination_dir.mkdir(parents=True, exist_ok=True)
            for path in source.rglob("*"):
                if path.is_file():
                    target = destination_dir / path.relative_to(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or restore an OPOP BI backup")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--output", type=Path)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("archive", type=Path)
    restore_parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    if args.command == "backup":
        print(create_backup(args.output))
    else:
        restore_backup(args.archive, confirmed=args.confirm)
        print("Restore completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
