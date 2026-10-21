"""Run configuration for sandbox_runner.

Every number here is part of the G0b environment manifest. Change a default
only together with a version bump, because cached results are keyed on it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field

SANDBOX_VERSION = "0.2.1"  # 0.2.1: C <stdbool.h> compile fallback

# Compile flags. The two compile passes of Master Plan §9.2-U0 plus the plain
# build that the tests run against.
WARNING_FLAGS = [
    "-O2",
    "-Wall",
    "-Wextra",
    "-Wmaybe-uninitialized",
    "-Wparentheses",
    "-Warray-bounds",
    "-Wshadow",
    "-Wconversion",
    "-fdiagnostics-color=never",
    "-fno-diagnostics-show-caret",
]
EXEC_FLAGS = ["-O2", "-pipe"]
SANITIZER_FLAGS = [
    "-O1",
    "-g",
    "-fno-omit-frame-pointer",
    "-fsanitize=address,undefined",
]
VALGRIND_FLAGS = ["-O0", "-g"]

LANG_STD = {"cpp": "c++17", "c": "c11"}
LANG_COMPILER = {"cpp": "g++", "c": "gcc"}

# Sanitizer runtime options. Keep halt_on_error=0 for UBSan so one run reports
# every distinct signal; ASan always aborts on its first report.
ASAN_OPTIONS = (
    "detect_leaks=0:abort_on_error=0:symbolize=1:detect_stack_use_after_return=0:"
    "allocator_may_return_null=1:handle_segv=1:exitcode=86"
)
UBSAN_OPTIONS = "print_stacktrace=0:halt_on_error=0:report_error_type=1"
SANITIZER_EXIT_CODE = 86
VALGRIND_EXIT_CODE = 87


@dataclass(frozen=True)
class Limits:
    """Per-process resource limits."""

    time_s: float = 2.0  # wall clock per test, plain build
    sanitizer_time_factor: float = 3.0  # ×3 for the sanitizer build (§9.2-U0)
    valgrind_time_factor: float = 15.0  # memcheck is ~10–30× slower
    compile_time_s: float = 30.0
    memory_mb: int = 512
    stack_mb: int = 64  # fixed stack limit; recorded in the manifest
    output_bytes: int = 1 << 20  # 1 MB stdout/stderr cap
    file_size_mb: int = 16
    pids: int = 64  # enforced by the docker backend (--pids-limit)


@dataclass(frozen=True)
class RunConfig:
    """What to run for one submission."""

    limits: Limits = field(default_factory=Limits)
    warnings_pass: bool = True
    sanitizer_pass: bool = True
    valgrind_pass: bool = True
    # Which tests the sanitizer build runs: "all", "failing", or "first_failing".
    sanitizer_tests: str = "all"
    # Valgrind is slow, so by default it runs only on the first failing test
    # (or the first test when everything passes).
    valgrind_tests: str = "first_failing"
    # Stop the sanitizer loop after this many tests produced a report.
    sanitizer_stop_after_reports: int = 2
    # Run each test twice and drop tests whose output differs (determinism).
    double_run: bool = True
    # Stop running the remaining plain tests after a timeout, to bound cost.
    stop_after_timeouts: int = 3
    keep_stdout_bytes: int = 2048  # how much stdout each test result keeps
    network_isolation: bool = True  # local backend: unshare -n when possible
    use_pch: bool = True  # speed only; excluded from the fingerprint

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def fingerprint(self) -> str:
        cfg = self.to_dict()
        cfg.pop("use_pch", None)
        cfg.pop("network_isolation", None)
        blob = json.dumps(
            {"cfg": cfg, "v": SANDBOX_VERSION, "w": WARNING_FLAGS,
             "e": EXEC_FLAGS, "s": SANITIZER_FLAGS, "vg": VALGRIND_FLAGS,
             "std": LANG_STD},
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


def normalize_lang(lang: str) -> str:
    """Map source-specific language names onto "cpp" or "c"."""
    key = (lang or "").strip().lower()
    if key in {"c++", "cpp", "cxx", "cc", "c++11", "c++14", "c++17", "c++20", "cpp17", "g++"}:
        return "cpp"
    if key in {"c", "c99", "c11", "c17", "gcc"}:
        return "c"
    raise ValueError(f"sandbox_runner supports C and C++ only, got {lang!r}")
