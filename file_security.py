from __future__ import annotations

import re
from pathlib import Path

_STORED_XLSX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\.xlsx$", re.IGNORECASE)


def resolve_stored_xlsx(base_dir: Path, stored_name: object) -> Path | None:
    """Resolve a server-generated workbook name without allowing directory escape."""
    if not isinstance(stored_name, str) or not _STORED_XLSX_RE.fullmatch(stored_name):
        return None
    base = base_dir.resolve()
    candidate = (base / stored_name).resolve()
    if not candidate.is_relative_to(base):
        return None
    return candidate
