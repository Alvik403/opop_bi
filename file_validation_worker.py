from __future__ import annotations

import argparse
import json
from pathlib import Path

from file_validation import ValidationLimits, validate_excel_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--max-archive-entries", type=int, required=True)
    parser.add_argument("--max-uncompressed-bytes", type=int, required=True)
    parser.add_argument("--max-compression-ratio", type=int, required=True)
    parser.add_argument("--max-sheets", type=int, required=True)
    parser.add_argument("--max-rows-per-sheet", type=int, required=True)
    args = parser.parse_args()

    limits = ValidationLimits(
        max_archive_entries=args.max_archive_entries,
        max_uncompressed_bytes=args.max_uncompressed_bytes,
        max_compression_ratio=args.max_compression_ratio,
        max_sheets=args.max_sheets,
        max_rows_per_sheet=args.max_rows_per_sheet,
    )
    try:
        result = validate_excel_file(args.path, limits)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **result.to_dict()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
