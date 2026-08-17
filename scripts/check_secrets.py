"""Scan the repository for accidentally committed secrets.

Exit 1 when anything looks like a real credential. Run as ``make security``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Generic secret assignment", re.compile(r"""(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*['"][A-Za-z0-9/+=]{16,}['"]""")),
    ("Private key header", re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----")),
    ("Bearer token", re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)),
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}")),
    ("OpenAI API key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
]

SKIP_DIRS = {".venv", "venv", ".git", "__pycache__", "node_modules", ".mypy_cache", ".ruff_cache"}
SKIP_EXTENSIONS = {".pyc", ".pyo", ".egg-info", ".whl", ".tar.gz"}
SAFE_FILES = {"check_secrets.py", ".env.example", "SECURITY.md"}


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in SKIP_EXTENSIONS or not path.is_file():
            continue
        if path.name in SAFE_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in PATTERNS:
            for match in pattern.finditer(text):
                rel = path.relative_to(root)
                line_no = text[: match.start()].count("\n") + 1
                findings.append(f"  {rel}:{line_no}  [{label}]  {match.group()[:40]}...")
    return findings


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    findings = scan(root)
    if findings:
        print("SECRET SCAN FAILED — potential credentials found:\n")
        print("\n".join(findings))
        print(f"\n{len(findings)} finding(s). Fix before committing.")
        sys.exit(1)
    else:
        print("Secret scan passed — no credentials detected.")


if __name__ == "__main__":
    main()
