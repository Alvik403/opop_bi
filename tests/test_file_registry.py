from __future__ import annotations

from pathlib import Path

import pytest

from file_registry import FileRecord, FileRegistry
from file_security import resolve_stored_xlsx
from settings import Settings
from conftest import create_sample_workbook


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        debug=True,
        allow_insecure_debug=True,
        data_dir=tmp_path / "data",
        uploads_dir=tmp_path / "uploads",
        database_path=tmp_path / "runtime" / "test.sqlite3",
        logs_dir=tmp_path / "logs",
        session_secret="test-secret",
        allowed_hosts="testserver",
    )


def test_resolve_stored_xlsx_rejects_traversal(tmp_path: Path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    assert resolve_stored_xlsx(uploads, "../../etc/passwd.xlsx") is None
    assert resolve_stored_xlsx(uploads, "..\\secret.xlsx") is None
    assert resolve_stored_xlsx(uploads, "ok.xlsx") == (uploads / "ok.xlsx").resolve()


def test_path_for_rejects_unsafe_stored_name(tmp_path: Path):
    settings = _settings(tmp_path)
    settings.ensure_runtime_dirs()
    registry = FileRegistry(settings)
    record = FileRecord(
        id=1,
        original_name="evil.xlsx",
        stored_name="../../etc/passwd.xlsx",
        sha256="0" * 64,
        size=1,
        mtime=0,
        uploaded_at="2026-01-01T00:00:00+00:00",
        status="valid",
        validation_error=None,
        is_latest=True,
        source="upload",
    )
    with pytest.raises(ValueError, match="Некорректное имя"):
        registry.path_for(record)


def test_ensure_default_file_invalid_is_not_latest(tmp_path: Path):
    settings = _settings(tmp_path)
    settings.ensure_runtime_dirs()
    broken = settings.default_excel_path
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_bytes(b"not-xlsx")
    registry = FileRegistry(settings)

    def fail(_path: Path) -> None:
        raise ValueError("broken workbook")

    record = registry.ensure_default_file(broken, validator=fail)
    assert record is not None
    assert record.status == "invalid"
    assert record.is_latest is False
    assert registry.get_latest_valid() is None


def test_ensure_default_file_valid_becomes_latest(tmp_path: Path):
    settings = _settings(tmp_path)
    settings.ensure_runtime_dirs()
    create_sample_workbook(settings.default_excel_path)
    registry = FileRegistry(settings)
    record = registry.ensure_default_file(settings.default_excel_path, validator=lambda path: path)
    assert record is not None
    assert record.status == "valid"
    assert record.is_latest is True
