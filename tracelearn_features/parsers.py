"""G2 report parsers: raw tool output -> extract_features evidence blocks (§6).

Two entry points, both pinned by tests/test_report_parsers.py:

- `parse_warnings(text)` -> `[{"flag": "-Wunused-variable", "count": n}, ...]`.
  Line-based scan of compiler stderr; only `warning:` lines count (notes and
  errors do not). A warning without a `[-W...]` flag bracket is returned with
  flag "" and lands in `warnings.other` upstream.

- `parse_runtime_report(text, *, timed_out, exit_code, duration_s)` ->
  a runtime evidence dict for `extract_features`:
      crashed, signal, exit_code, duration_s, timed_out,
      asan_reports, ubsan_reports, valgrind_reports

  Semantics:
  - str input (even "") => a report existed; returns a dict (block available).
    An empty report is a clean run.
  - non-str input (None included) => None; the block stays NaN upstream
    (source cannot provide it — never a false "clean").
  - crashed: ASan reports abort, or a fatal signal is evidenced. UBSan
    recover output and Valgrind memcheck errors do NOT kill the process.
  - signal: SEGV->11, ABRT->6, glibc "Segmentation fault"/"Aborted",
    Valgrind "default action of signal N". Unknown -> None (NaN upstream).
  - valgrind_reports only carries memcheck *error* descriptions (plus a
    non-zero ERROR SUMMARY), never headers or "0 errors" lines — so a clean
    Valgrind run parses to an empty list, not a false positive.

Never raises on malformed input (§5: a parser bug must not block a lane).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

_WARNING_LINE = re.compile(r"warning\s*:")
_FLAG_BRACKET = re.compile(r"\[(-W[a-z0-9-]+)\]")

_ASAN_LINE = re.compile(r"ERROR:\s*AddressSanitizer")
_UBSAN_LINE = re.compile(r"runtime error\s*:")
_VG_PREFIX = re.compile(r"^==\d+==\s?")
_VG_SUMMARY_ERRORS = re.compile(r"ERROR SUMMARY:\s*(\d+)\s+errors?")
_VG_LOST = re.compile(r"(\d+)\s+bytes in \d+ blocks are (?:definitely|indirectly|possibly) lost")
_VG_SIGNAL = re.compile(r"default action of signal (\d+)")

_VG_ERROR_DESCRIPTIONS = (
    re.compile(r"depends on uninitiali[sz]ed value", re.IGNORECASE),
    re.compile(r"Use of uninitiali[sz]ed value", re.IGNORECASE),
    re.compile(r"Invalid read of size", re.IGNORECASE),
    re.compile(r"Invalid write of size", re.IGNORECASE),
    re.compile(r"Invalid free", re.IGNORECASE),
    re.compile(r"Mismatched free", re.IGNORECASE),
    re.compile(r"Source and destination overlap", re.IGNORECASE),
)


def parse_warnings(text: Any) -> list[dict[str, Any]] | None:
    """Parse compiler stderr into `[{"flag", "count"}]` rows.

    Returns None when `text` is not a string (no evidence — block stays NaN),
    and [] for a string with zero warnings (evidence present — zeros).
    """
    if not isinstance(text, str):
        return None
    counts: Counter[str] = Counter()
    for line in text.splitlines():
        if not _WARNING_LINE.search(line):
            continue
        match = _FLAG_BRACKET.search(line)
        counts[match.group(1) if match else ""] += 1
    return [{"flag": flag, "count": n} for flag, n in counts.items()]


def parse_runtime_report(
    text: Any,
    *,
    timed_out: bool | None = None,
    exit_code: int | None = None,
    duration_s: float | None = None,
) -> dict[str, Any] | None:
    """Parse sanitizer/Valgrind/glibc report text into runtime evidence.

    Returns None for non-str input (evidence absent -> NaN upstream).
    """
    if not isinstance(text, str):
        return None

    asan_lines = [ln for ln in text.splitlines() if _ASAN_LINE.search(ln)]
    ubsan_lines = [ln for ln in text.splitlines() if _UBSAN_LINE.search(ln)]

    valgrind_lines: list[str] = []
    for raw in text.splitlines():
        if not raw.startswith("=="):
            continue
        body = _VG_PREFIX.sub("", raw).rstrip()
        if not body:
            continue
        if any(p.search(body) for p in _VG_ERROR_DESCRIPTIONS):
            valgrind_lines.append(body)
            continue
        summary = _VG_SUMMARY_ERRORS.search(body)
        if summary and int(summary.group(1)) > 0:
            valgrind_lines.append(body)
            continue
        lost = _VG_LOST.search(body)
        if lost and int(lost.group(1)) > 0:
            valgrind_lines.append(body)

    # --- signal + crash determination -------------------------------
    signal: int | None = None
    asan_text = "\n".join(asan_lines)
    if re.search(r"\bSEGV\b", asan_text):
        signal = 11
    elif re.search(r"\bABRT\b", asan_text):
        signal = 6
    if signal is None:
        vg_signal = _VG_SIGNAL.search(text)
        if vg_signal:
            signal = int(vg_signal.group(1))
    if signal is None and re.search(r"Segmentation fault", text):
        signal = 11
    if signal is None and re.search(r"\bAborted\b", text):
        signal = 6

    crashed = bool(asan_lines) or signal is not None

    return {
        "crashed": crashed,
        "signal": signal,
        "exit_code": exit_code,
        "duration_s": duration_s,
        "timed_out": bool(timed_out),
        "asan_reports": asan_lines,
        "ubsan_reports": ubsan_lines,
        "valgrind_reports": valgrind_lines,
    }
