"""C++ diagnostic problem definitions.

This package holds the problem definitions for the C++ diagnostic bank. The
generator `scripts/build_cpp_diagnostics.py` imports every module and writes
the data files. The seeder `scripts/seed_cpp_diagnostics.py` reads those data
files.

Author: Agent 4, C++ test author and quality judge.
Standard: ASD-STE100 Simplified Technical English.
"""
from __future__ import annotations

from .m01_m02 import PROBLEMS as _M01_M02
from .m03_m04 import PROBLEMS as _M03_M04
from .m05_m06 import PROBLEMS as _M05_M06
from .m07_m08 import PROBLEMS as _M07_M08

__all__ = ["ALL_PROBLEMS", "MODULES"]

MODULES = {
    "m01_m02": _M01_M02,
    "m03_m04": _M03_M04,
    "m05_m06": _M05_M06,
    "m07_m08": _M07_M08,
}


def _collect() -> list[dict]:
    """Return the definitions from every module that is present."""
    problems: list[dict] = []
    for module in MODULES.values():
        problems.extend(module)
    return problems


ALL_PROBLEMS = _collect()
