"""Wipe generated runtime state. CORE_DNA is never touched.

Run as ``make reset``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

WIPE_DIRS = [
    "memory/episodic",
    "memory/semantic",
    "memory/creative",
    "memory/rejected",
    "memory/successful",
    "memory/experiments",
    "memory/graveyard",
    "memory/canon",
    "memory/dead_letter",
    "memory/.state",
    "logs",
    "outputs",
]

NEVER_TOUCH = [
    "memory/core_dna",
]


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    wiped = 0

    for rel in WIPE_DIRS:
        target = root / rel
        if not target.exists():
            continue
        if any(str(target).startswith(str(root / nt)) for nt in NEVER_TOUCH):
            print(f"  PROTECTED    {rel}")
            continue
        for child in sorted(target.iterdir()):
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
            print(f"  wiped        {child.relative_to(root)}")
            wiped += 1

    evolving = root / "memory" / "evolving_dna"
    if evolving.exists():
        for f in evolving.glob("*.json"):
            f.unlink()
            print(f"  wiped        {f.relative_to(root)}")
            wiped += 1

    if wiped:
        print(f"\nReset {wiped} item(s). CORE_DNA untouched.")
    else:
        print("Nothing to reset.")


if __name__ == "__main__":
    main()
