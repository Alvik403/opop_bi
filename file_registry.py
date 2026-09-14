from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from file_security import resolve_stored_xlsx
from settings import Settings

Validator = Callable[[Path], object]


@dataclass(frozen=True)
class FileRecord:
    id: int
    original_name: str
    stored_name: str
    sha256: str
    size: int
    mtime: float
    uploaded_at: str
    status: str
    validation_error: str | None
    is_latest: bool
    source: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "original_name": self.original_name,
            "stored_name": self.stored_name,
            "sha256": self.sha256,
            "size": self.size,
            "mtime": self.mtime,
            "uploaded_at": self.uploaded_at,
            "status": self.status,
            "validation_error": self.validation_error,
            "is_latest": self.is_latest,
            "source": self.source,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database_path = settings.resolved_database_path
        self.uploads_dir = settings.resolved_uploads_dir
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_db(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    validation_error TEXT,
                    is_latest INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'upload'
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_latest ON files(is_latest)")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_files_stored_name ON files(stored_name)"
            )

    def row_to_record(self, row: sqlite3.Row | None) -> FileRecord | None:
        if row is None:
            return None
        return FileRecord(
            id=int(row["id"]),
            original_name=str(row["original_name"]),
            stored_name=str(row["stored_name"]),
            sha256=str(row["sha256"]),
            size=int(row["size"]),
            mtime=float(row["mtime"]),
            uploaded_at=str(row["uploaded_at"]),
            status=str(row["status"]),
            validation_error=row["validation_error"],
            is_latest=bool(row["is_latest"]),
            source=str(row["source"]),
        )

    def path_for(self, record: FileRecord) -> Path:
        if record.source == "default":
            base = self.settings.resolved_data_dir.resolve()
            candidate = self.settings.default_excel_path.resolve()
            if not candidate.is_relative_to(base):
                raise ValueError("Некорректный путь файла по умолчанию")
            return candidate
        resolved = resolve_stored_xlsx(self.uploads_dir, record.stored_name)
        if resolved is None:
            raise ValueError("Некорректное имя хранимого файла")
        return resolved

    def ensure_default_file(
        self,
        path: Path,
        validator: Validator | None = None,
    ) -> FileRecord | None:
        if not path.exists():
            return self.get_latest_valid()

        status = "valid"
        validation_error: str | None = None
        if validator is None:
            status = "invalid"
            validation_error = "Файл по умолчанию не прошёл изолированную проверку"
        else:
            try:
                validator(path)
            except Exception as exc:
                status = "invalid"
                validation_error = str(exc)

        stat = path.stat()
        digest = sha256_file(path)
        uploaded_at = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT * FROM files WHERE source = 'default' AND stored_name = ?",
                (path.name,),
            ).fetchone()
            latest_exists = conn.execute(
                "SELECT 1 FROM files WHERE status = 'valid' AND is_latest = 1"
            ).fetchone()
            is_latest = 1 if status == "valid" and not latest_exists else 0
            if existing and status != "valid":
                is_latest = 0
            elif existing and existing["is_latest"] and status == "valid":
                is_latest = 1
            if existing:
                conn.execute(
                    """
                    UPDATE files
                    SET original_name = ?, sha256 = ?, size = ?, mtime = ?, status = ?,
                        validation_error = ?, is_latest = ?
                    WHERE id = ?
                    """,
                    (
                        path.name,
                        digest,
                        stat.st_size,
                        stat.st_mtime,
                        status,
                        validation_error,
                        is_latest,
                        existing["id"],
                    ),
                )
                file_id = int(existing["id"])
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO files (
                        original_name, stored_name, sha256, size, mtime, uploaded_at,
                        status, validation_error, is_latest, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'default')
                    """,
                    (
                        path.name,
                        path.name,
                        digest,
                        stat.st_size,
                        stat.st_mtime,
                        uploaded_at,
                        status,
                        validation_error,
                        is_latest,
                    ),
                )
                file_id = int(cursor.lastrowid)

        return self.get_by_id(file_id)

    def get_by_id(self, file_id: int) -> FileRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        return self.row_to_record(row)

    def get_valid_by_id(self, file_id: int) -> FileRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM files WHERE id = ? AND status = 'valid'",
                (file_id,),
            ).fetchone()
        return self.row_to_record(row)

    def get_latest_valid(self) -> FileRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM files
                WHERE status = 'valid'
                ORDER BY is_latest DESC, uploaded_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        return self.row_to_record(row)

    def list_files(self) -> list[FileRecord]:
        with self.connect() as conn:
            rows: Iterable[sqlite3.Row] = conn.execute(
                "SELECT * FROM files ORDER BY uploaded_at DESC, id DESC"
            ).fetchall()
        return [record for row in rows if (record := self.row_to_record(row)) is not None]

    def add_valid_upload(self, *, original_name: str, stored_name: str, path: Path) -> FileRecord:
        if resolve_stored_xlsx(self.uploads_dir, stored_name) is None:
            raise ValueError("Некорректное имя хранимого файла")
        stat = path.stat()
        digest = sha256_file(path)
        uploaded_at = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute("UPDATE files SET is_latest = 0 WHERE is_latest = 1")
            cursor = conn.execute(
                """
                INSERT INTO files (
                    original_name, stored_name, sha256, size, mtime, uploaded_at,
                    status, validation_error, is_latest, source
                ) VALUES (?, ?, ?, ?, ?, ?, 'valid', NULL, 1, 'upload')
                """,
                (original_name, stored_name, digest, stat.st_size, stat.st_mtime, uploaded_at),
            )
            file_id = int(cursor.lastrowid)
        record = self.get_by_id(file_id)
        if not record:
            raise RuntimeError("Не удалось зарегистрировать загруженный файл")
        return record

    def plan_upload_capacity(
        self,
        *,
        incoming_size: int,
        max_files: int,
        max_bytes: int,
        protected_ids: set[int] | None = None,
    ) -> list[FileRecord]:
        protected = set(protected_ids or ())
        latest = self.get_latest_valid()
        if latest:
            protected.add(latest.id)

        uploads = [record for record in reversed(self.list_files()) if record.source == "upload"]
        total_bytes = sum(record.size for record in uploads)
        victims: list[FileRecord] = []

        while uploads and (
            len(uploads) - len(victims) + 1 > max_files
            or total_bytes + incoming_size > max_bytes
        ):
            candidate = next((record for record in uploads if record.id not in protected), None)
            if candidate is None:
                break
            uploads.remove(candidate)
            total_bytes -= candidate.size
            protected.add(candidate.id)
            victims.append(candidate)

        remaining = len(uploads)
        if remaining + 1 > max_files or total_bytes + incoming_size > max_bytes:
            raise ValueError("Недостаточно квоты хранилища для нового файла")
        return victims

    def delete_uploads(self, records: list[FileRecord]) -> list[int]:
        deleted_ids: list[int] = []
        for record in records:
            try:
                path = self.path_for(record)
            except ValueError:
                path = None
            if path is not None:
                path.unlink(missing_ok=True)
            with self.connect() as conn:
                conn.execute("DELETE FROM files WHERE id = ?", (record.id,))
            deleted_ids.append(record.id)
        return deleted_ids

    def prepare_upload_capacity(
        self,
        *,
        incoming_size: int,
        max_files: int,
        max_bytes: int,
        protected_ids: set[int] | None = None,
    ) -> list[int]:
        victims = self.plan_upload_capacity(
            incoming_size=incoming_size,
            max_files=max_files,
            max_bytes=max_bytes,
            protected_ids=protected_ids,
        )
        return self.delete_uploads(victims)
