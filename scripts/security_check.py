from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from shutil import which

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    npm = which("npm") or which("npm.cmd")
    if not npm:
        raise RuntimeError("npm is required for frontend security checks")
    run([sys.executable, "-m", "pytest", "-q"])
    run([sys.executable, "-m", "pip_audit", "-r", "requirements.txt"])
    run([npm, "run", "build"])
    run([npm, "run", "audit"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
