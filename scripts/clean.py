"""Remove caches and build artifacts. Run as ``make clean``."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

TARGETS = [
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    "*.egg-info",
    "build",
    "dist",
    "htmlcov",
]

FILE_TARGETS = [
    ".coverage",
    ".coverage.*",
    "coverage.xml",
]


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    removed = 0

    for pattern in TARGETS:
        for path in root.rglob(pattern):
            if ".venv" in path.parts or "venv" in path.parts:
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                print(f"  removed dir  {path.relative_to(root)}")
                removed += 1

    for pattern in FILE_TARGETS:
        for path in root.glob(pattern):
            path.unlink(missing_ok=True)
            print(f"  removed file {path.relative_to(root)}")
            removed += 1

    if removed:
        print(f"\nCleaned {removed} item(s).")
    else:
        print("Nothing to clean.")


if __name__ == "__main__":
    main()
