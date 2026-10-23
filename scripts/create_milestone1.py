"""Generate all Milestone 1 files for TraceLearn POC."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print(f"created {rel}")


def main() -> None:
    write("backend/app/__init__.py", "")
    write("backend/app/api/__init__.py", "")
    write("backend/app/db/__init__.py", "")
    write("backend/app/schemas/__init__.py", "")
    write("backend/app/evaluation/__init__.py", "")
