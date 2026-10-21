"""Precompiled ``<bits/stdc++.h>`` per flag set — a pure speed optimisation.

Most competitive-style C++ submissions include ``<bits/stdc++.h>``, which costs
~1.5 s per compile and ~4 s with sanitizers. We precompile it once per flag
set into ``<cache>/<hash>/bits/stdc++.h.gch`` next to a copy of the real
header and add ``-I <cache>/<hash>``. GCC uses the .gch only when the flags
match (``-Winvalid-pch`` would say otherwise) and falls back to the copied
header, so results are identical with or without it.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import shutil
import subprocess

import tempfile

# Under /tmp, not $HOME: compiles run as uid 65534, which must read the PCH.
CACHE_ROOT = os.environ.get(
    "SANDBOX_PCH_DIR", os.path.join(tempfile.gettempdir(), f"sandbox_runner_pch_{os.geteuid()}"))


def _find_header() -> str | None:
    try:
        r = subprocess.run(["g++", "-std=c++17", "-x", "c++", "-E", "-H", "-"],
                           input="#include <bits/stdc++.h>\n", capture_output=True, text=True,
                           timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in r.stderr.splitlines():
        if line.startswith(". ") and line.endswith("bits/stdc++.h"):
            return line[2:].strip()
    return None


def pch_include_dir(std: str, flags: list[str]) -> str | None:
    """Return an ``-I`` directory holding a matching PCH, building it if needed."""
    if os.environ.get("SANDBOX_NO_PCH"):
        return None
    key = hashlib.sha256(repr((std, flags)).encode()).hexdigest()[:16]
    d = os.path.join(CACHE_ROOT, key)
    gch = os.path.join(d, "bits", "stdc++.h.gch")
    if os.path.exists(gch):
        return d
    try:
        os.makedirs(os.path.join(d, "bits"), exist_ok=True)
        with open(os.path.join(d, ".lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if os.path.exists(gch):
                return d
            hdr = _find_header()
            if not hdr:
                return None
            shutil.copy(hdr, os.path.join(d, "bits", "stdc++.h"))
            tmp = gch + f".tmp{os.getpid()}"
            r = subprocess.run(["g++", f"-std={std}", *flags, "-x", "c++-header",
                                os.path.join(d, "bits", "stdc++.h"), "-o", tmp],
                               capture_output=True, timeout=300)
            if r.returncode != 0:
                return None
            os.chmod(tmp, 0o644)
            os.replace(tmp, gch)
            for p in (d, os.path.join(d, "bits")):
                os.chmod(p, 0o755)
            os.chmod(os.path.join(d, "bits", "stdc++.h"), 0o644)
            return d
    except OSError:
        return None
