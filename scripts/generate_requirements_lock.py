from __future__ import annotations

import json
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "requirements.lock"

# Pinned runtime set for CPython 3.12 (Linux Docker + Windows). Includes uvicorn[standard].
PACKAGES = [
    ("annotated-doc", "0.0.5"),
    ("annotated-types", "0.7.0"),
    ("anyio", "4.14.0"),
    ("click", "8.4.1"),
    ("colorama", "0.4.6"),
    ("et-xmlfile", "2.0.0"),
    ("fastapi", "0.141.1"),
    ("h11", "0.16.0"),
    ("httptools", "0.8.0"),
    ("idna", "3.18"),
    ("itsdangerous", "2.2.0"),
    ("jinja2", "3.1.6"),
    ("markupsafe", "3.0.3"),
    ("numpy", "2.4.6"),
    ("openpyxl", "3.1.5"),
    ("pandas", "3.0.5"),
    ("pydantic", "2.13.4"),
    ("pydantic-core", "2.46.4"),
    ("pydantic-settings", "2.15.0"),
    ("python-dateutil", "2.9.0.post0"),
    ("python-dotenv", "1.2.2"),
    ("python-multipart", "0.0.32"),
    ("pyyaml", "6.0.3"),
    ("six", "1.17.0"),
    ("starlette", "1.6.0"),
    ("typing-extensions", "4.15.0"),
    ("typing-inspection", "0.4.2"),
    ("tzdata", "2026.2"),
    ("uvicorn", "0.52.4"),
    ("uvloop", "0.22.1"),
    ("watchfiles", "1.2.0"),
    ("websockets", "16.0"),
]


def fetch(name: str, version: str) -> tuple[str, str, list[str]]:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    else:
        raise RuntimeError(f"Failed to fetch {name}=={version}: {last_error}")
    canonical = payload["info"]["name"]
    hashes = sorted(
        {
            file["digests"]["sha256"]
            for file in payload["urls"]
            if file.get("packagetype") in {"bdist_wheel", "sdist"}
        }
    )
    if not hashes:
        raise RuntimeError(f"No hashes for {name}=={version}")
    return canonical, version, hashes


def main() -> int:
    rows = []
    for item in PACKAGES:
        rows.append(fetch(*item))
    lines = [
        "#",
        "# Hashed lockfile generated from the runtime package set.",
        "# Recreate: python scripts/generate_requirements_lock.py",
        "#",
        "# pip install --require-hashes --no-cache-dir -r requirements.lock",
        "#",
    ]
    for name, version, hashes in sorted(rows, key=lambda item: item[0].lower()):
        hash_lines = " \\\n    ".join(f"--hash=sha256:{digest}" for digest in hashes)
        lines.append(f"{name}=={version} \\")
        lines.append(f"    {hash_lines}")
    lines.append("")
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
