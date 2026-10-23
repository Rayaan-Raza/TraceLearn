"""Toolchain identification for the cache key and the G0b manifest."""

from __future__ import annotations

import functools
import os
import platform
import shutil
import subprocess


def _first_line(argv: list[str]) -> str | None:
    if not shutil.which(argv[0]):
        return None
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (r.stdout or r.stderr).strip()
    return text.splitlines()[0] if text else None


@functools.lru_cache(maxsize=1)
def toolchain_versions() -> dict:
    return {
        "gcc": _first_line(["gcc", "--version"]),
        "g++": _first_line(["g++", "--version"]),
        "clang": _first_line(["clang", "--version"]),
        "valgrind": _first_line(["valgrind", "--version"]),
        "python": platform.python_version(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "image": os.environ.get("SANDBOX_IMAGE_DIGEST"),
    }


@functools.lru_cache(maxsize=1)
def toolchain_id() -> str:
    v = toolchain_versions()
    return f"g++={v['g++']}|gcc={v['gcc']}|valgrind={v['valgrind']}|image={v['image']}"
