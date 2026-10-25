"""Normalize each lane's raw evidence onto the canonical feature registry.

The three lanes do not store evidence in the same vocabulary:

- **SYNTHETIC (tier0)** embeds the mutant's source in
  `static.source_code`, raw compiler output in `warnings.compile_warnings`,
  and test totals in the non-canonical `runtime.tests_*` keys;
- **CODESTREAM (tier1a)** ships `static=null` (the merge resolves the
  submission's code), raw `-Wflag` count keys, a sandbox runtime block
  (`any_crash` / `sanitizer` / `valgrind`), and test results keyed by
  `status` (pass/wrong/crash/presentation/timeout);
- **PROGPEDIA (tier1b)** already emits canonical blocks (its lane ran the
  extractor).

`flatten_features()` reads canonical short names only, so a lane that stored
evidence in its own vocabulary silently produced NaN columns. This module
maps each vocabulary onto the registry *before* flattening, without touching
lane inputs:

- a value the lane already supplied is never overwritten;
- evidence the lane does not carry stays NaN (§6 null policy);
- an empty CodeStream warnings dict means "not mined", not "zero warnings";
- test-status vocabulary is translated, never guessed (a failure kind the
  lane does not classify stays NaN);
- no label-derived metadata (`mutation_op`, `seed_ref`, ...) is ever used as
  a feature.
"""

from __future__ import annotations

import copy
import math
import re
from collections import Counter
from typing import Any

from tracelearn_features.cpg_source import extract_cpg_source
from tracelearn_features.extractor import extract_features
from tracelearn_features.schema import WARNING_FLAG_OF
from tracelearn_features.semantics import extract_semantics

_NAN = float("nan")
_FLAG_TO_FEATURE = {
    flag: name.split(".", 1)[1] for name, flag in WARNING_FLAG_OF.items()
}
_GCC_WARNING_FLAG_RE = re.compile(r"\[-W([A-Za-z0-9_=-]+)\]")

# Lanes whose `static` block is a raw carrier (tier0 embeds the mutant's
# source; tier1a ships null and the merge resolves the submission's code).
# PROGPedia arrives canonical — a null there is a lane gap and must stay
# visible in the availability report, never silently re-mined.
_MINE_STATIC_SOURCES = frozenset({"SYNTHETIC", "CODESTREAM"})


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return True


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and not math.isnan(value):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return None if isinstance(value, float) and math.isnan(value) else float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _fill_block(row: dict[str, Any], block_name: str, computed: dict[str, Any]) -> None:
    """Fill canonical keys the lane did not already provide; never overwrite."""
    if not computed:
        return
    block = row.get(block_name)
    if not isinstance(block, dict):
        block = {}
    for name, value in computed.items():
        if _present(block.get(name)):
            continue
        if not _present(value):
            continue
        block[name] = value
    row[block_name] = block


# ------------------------------------------------------------------- static


def _static_source(row: dict[str, Any], code: str | None) -> str | None:
    """The row's own source code, never another row's (seed) code.

    SYNTHETIC rows embed the mutant's code; CodeStream rows get the code the
    merge resolved for their own submission.
    """
    block = row.get("static")
    if isinstance(block, dict) and isinstance(block.get("source_code"), str):
        return block["source_code"]
    return code


def _static_needs_mining(block: Any) -> bool:
    # `None` (CodeStream) or a raw `source_code` carrier (tier0) has not been
    # measured yet. A canonical block (PROGPedia) is left untouched.
    return block is None or (
        isinstance(block, dict) and "source_code" in block
    )


# ----------------------------------------------------------------- warnings


def _warning_evidence(row: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Canonical warnings evidence for a lane's raw vocabulary.

    `None` means "the lane did not carry warnings evidence" (leave the block
    alone); an empty list means "the compiler ran and emitted no warnings".
    """
    warnings = row.get("warnings")
    if not isinstance(warnings, dict) or not warnings:
        return None

    text = warnings.get("compile_warnings")
    if isinstance(text, str):
        counts = Counter(
            flag.rstrip("=") for flag in _GCC_WARNING_FLAG_RE.findall(text)
        )
        return [{"flag": f"-W{flag}", "count": n} for flag, n in counts.items()]

    raw_flags = [
        (key, value)
        for key, value in warnings.items()
        if isinstance(key, str) and key.startswith("-W")
    ]
    if not raw_flags:
        return None
    evidence: list[dict[str, Any]] = []
    for key, value in raw_flags:
        count = _as_int(value)
        if count is None or count <= 0:
            continue
        flag = "-W" + key[2:].rstrip("=")
        evidence.append({"flag": flag, "count": count})
    return evidence


# ------------------------------------------------------------------ runtime


def _codestream_runtime(runtime: Any) -> dict[str, Any]:
    """Map the sandbox runtime shape onto the canonical runtime block."""
    if not isinstance(runtime, dict) or not runtime:
        return {}
    sanitizer = runtime.get("sanitizer")
    sanitizer = sanitizer if isinstance(sanitizer, dict) else {}
    reports = sanitizer.get("reports")
    reports = [r for r in reports if isinstance(r, dict)] if isinstance(reports, list) else []
    kinds = [str(r.get("kind") or "") for r in reports]
    sanitizer_kinds = sanitizer.get("kinds")
    if isinstance(sanitizer_kinds, dict):
        kinds += [str(k) for k in sanitizer_kinds]

    tools = {str(r.get("tool") or "").lower() for r in reports}
    asan = "asan" in tools or any(k.startswith("asan:") for k in kinds)
    ubsan = "ubsan" in tools or any(k.startswith("ubsan:") for k in kinds)
    signed = any("signed" in k and "overflow" in k for k in kinds) or any(
        "signed integer overflow" in str(r.get("message") or "").lower()
        for r in reports
    )
    stack = any("stack" in k and ("overflow" in k or "buffer" in k) for k in kinds)

    valgrind = runtime.get("valgrind")
    valgrind = valgrind if isinstance(valgrind, dict) else {}
    valgrind_kinds = [str(k) for k in (valgrind.get("kinds") or {})]
    valgrind_errors = _as_int(valgrind.get("error_count")) or 0
    valgrind_uninit = bool(valgrind.get("uninit")) or any(
        "uninit" in k for k in valgrind_kinds
    )

    out: dict[str, Any] = {"available": True}
    crashed = runtime.get("any_crash")
    if isinstance(crashed, bool):
        out["crashed"] = crashed
    timed_out = runtime.get("any_timeout")
    if isinstance(timed_out, bool):
        out["timed_out"] = timed_out
    signals = runtime.get("signals")
    if isinstance(signals, list) and signals:
        signal = _as_int(signals[0])
        if signal is not None:
            out["signal"] = signal
    duration = _as_float(runtime.get("max_seconds"))
    if duration is not None:
        out["duration_s"] = duration
    if reports or sanitizer.get("complete") is not None:
        out["asan_error"] = asan
        out["asan_heap_buffer_overflow"] = any("heap-buffer-overflow" in k for k in kinds)
        out["asan_stack_buffer_overflow"] = any("stack-buffer-overflow" in k for k in kinds)
        out["ubsan_error"] = ubsan
        out["ubsan_signed_overflow"] = signed
        raw_stack = runtime.get("stack_overflow")
        out["stack_overflow"] = bool(raw_stack) if isinstance(raw_stack, bool) else stack
    if valgrind:
        out["valgrind_error"] = valgrind_errors > 0 or bool(valgrind_kinds)
        out["valgrind_uninit_value"] = valgrind_uninit
    return out


# -------------------------------------------------------------------- tests


def _first_numeric_delta(diff: Any) -> float:
    if not isinstance(diff, dict):
        return _NAN
    deltas = diff.get("numeric_deltas")
    if isinstance(deltas, list) and deltas:
        value = _as_float(deltas[0])
        if value is not None:
            return value
    return _NAN


def _codestream_tests(tests: Any) -> dict[str, Any]:
    """Map sandbox test results (status vocabulary) onto the tests block."""
    if not isinstance(tests, dict) or not tests:
        return {}
    results = tests.get("results")
    if isinstance(results, list) and results:
        total = len(results)
        passed = failed = wrong = runtime_errors = timeouts = 0
        first_fail = -1
        first_diff = _NAN
        for index, result in enumerate(results):
            if not isinstance(result, dict):
                failed += 1
                continue
            status = result.get("status")
            if status == "pass":
                passed += 1
                continue
            failed += 1
            if first_fail < 0:
                first_fail = index
                first_diff = _first_numeric_delta(result.get("diff"))
            if status == "wrong":
                wrong += 1
            elif status == "crash":
                runtime_errors += 1
            elif status == "timeout":
                timeouts += 1
            # `presentation` (same tokens, different layout) and any
            # unclassified status count as failed but not as a wrong answer
            # — the canonical block has no field for it, and guessing would
            # fabricate evidence.
        out: dict[str, Any] = {
            "available": True,
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total else 0.0,
            "wrong_answer_count": wrong,
            "runtime_error_count": runtime_errors,
            "timeout_count": timeouts,
        }
        if first_fail >= 0:
            out["first_fail_index"] = first_fail
        if not math.isnan(first_diff):
            out["first_fail_numeric_diff"] = first_diff
        # boundary_fail_count needs per-test boundary metadata the lane does
        # not carry -> stays NaN (never a fabricated zero).
        return out

    total = _as_int(tests.get("total"))
    if total is None:
        return {}
    passed = _as_int(tests.get("passed"))
    failed = _as_int(tests.get("failed"))
    if failed is None:
        failed = total - (passed or 0)
    out = {
        "available": True,
        "total": total,
        "passed": passed if passed is not None else _NAN,
        "failed": failed,
        "pass_rate": (passed or 0) / total if total else 0.0,
    }
    return {k: v for k, v in out.items() if _present(v)}


# ------------------------------------------------------------------ context


def _codestream_context(context: Any) -> dict[str, Any]:
    if not isinstance(context, dict) or not context:
        return {}
    out: dict[str, Any] = {}
    statement = _as_int(context.get("statement_chars"))
    if statement is not None:
        out["statement_length"] = statement
    sample_tests = _as_int(context.get("tests_total"))
    if sample_tests is not None:
        out["sample_test_count"] = sample_tests
        out["sample_tests_present"] = sample_tests > 0
    return out


# --------------------------------------------------------------- public API


def normalize_row(row: dict[str, Any], code: str | None = None) -> dict[str, Any]:
    """Return a copy of `row` with canonical feature blocks filled in.

    `code` is the row's own resolved source (CodeStream); SYNTHETIC rows use
    their embedded mutant code instead. Values the lane already supplied win.
    """
    out = copy.deepcopy(row)
    language = str(out.get("language") or "c")

    source = _static_source(out, code)
    if (
        str(out.get("dataset_source") or "") in _MINE_STATIC_SOURCES
        and source is not None
        and _static_needs_mining(out.get("static"))
    ):
        _fill_block(out, "static", extract_features(source, language)["static"])

    source_kind = out.get("dataset_source")
    if source_kind in _MINE_STATIC_SOURCES and source:
        _fill_block(out, "semantics", extract_semantics(source))
        _fill_block(out, "cpg", extract_cpg_source(source))

    evidence = _warning_evidence(out)
    if evidence is not None:
        _fill_block(
            out, "warnings", extract_features("", language, warnings=evidence)["warnings"]
        )

    if source_kind == "CODESTREAM":
        _fill_block(out, "runtime", _codestream_runtime(out.get("runtime")))
        _fill_block(out, "tests", _codestream_tests(out.get("tests")))
        _fill_block(out, "context", _codestream_context(out.get("context")))
    elif source_kind == "SYNTHETIC":
        runtime = out.get("runtime")
        runtime = runtime if isinstance(runtime, dict) else {}
        total = _as_int(runtime.get("tests_total"))
        if total is not None:
            evidence = {
                "total": total,
                "passed": _as_int(runtime.get("tests_passed")),
                "failed": _as_int(runtime.get("tests_failed")),
            }
            _fill_block(
                out, "tests", extract_features("", language, tests=evidence)["tests"]
            )

    return out
