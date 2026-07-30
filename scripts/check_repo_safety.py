"""Fail CI for suspicious committed secrets or files larger than 5 MiB."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024
IGNORE_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


def main() -> None:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in IGNORE_PARTS for part in path.parts):
            continue
        if path.stat().st_size > MAX_BYTES:
            failures.append(f"large file: {path.relative_to(ROOT)}")
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in PATTERNS:
            if pattern.search(text):
                failures.append(f"secret pattern in {path.relative_to(ROOT)}")
    if failures:
        raise SystemExit("\n".join(failures))
    print("repository safety checks passed")


if __name__ == "__main__":
    main()
