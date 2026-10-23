"""G2 parser fixture tests (master plan §9.0-G2, §6).

Gate: fixture reports for ASan / UBSan / stack-overflow / Valgrind-uninit /
clean all parse, and every parsed evidence block drives extract_features to
the right enumerated values. Also pins the NaN-vs-zero distinction:

  - evidence present, nothing found  -> 0 (ran, none)
  - evidence absent                  -> NaN (source cannot provide)

Fixtures live in data/misconception_dataset/fixtures/parser/*.txt.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from tracelearn_features import extract_features
from tracelearn_features.parsers import parse_runtime_report, parse_warnings

FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "misconception_dataset"
    / "fixtures"
    / "parser"
)

G2_FIXTURES = (
    "asan_heap_overflow.txt",   # ASan
    "ubsan_signed_overflow.txt",  # UBSan
    "asan_stack_overflow.txt",  # stack-overflow
    "valgrind_uninit.txt",      # Valgrind-uninit
    "clean_runtime.txt",        # clean
    "warnings_mixed.txt",
    "warnings_clean.txt",
)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _is_nan(value) -> bool:
    return isinstance(value, float) and math.isnan(value)


def test_g2_fixture_set_complete():
    missing = [n for n in G2_FIXTURES if not (FIXTURES / n).is_file()]
    assert missing == [], f"G2 parser fixtures missing: {missing}"


# ------------------------------------------------------------------ warnings


def test_warning_fixture_parses_to_enumerated_flags():
    flags = parse_warnings(_fixture("warnings_mixed.txt"))
    out = extract_features("int main() { return 0; }", warnings=flags)
    w = out["warnings"]
    assert w["available"] is True
    assert w["parentheses"] == 1
    assert w["unused_variable"] == 1
    assert w["return_type"] == 1
    # -Wformat-truncation is not in the frozen enumeration -> catch-all
    assert w["other"] == 1
    assert w["total"] == 4
    # every flag in the fixture resolved to a schema feature (no silent drops)
    assert w["format"] == 0
    assert w["maybe_uninitialized"] == 0


def test_clean_warning_fixture_is_zero_not_nan():
    flags = parse_warnings(_fixture("warnings_clean.txt"))
    assert flags == []
    w = extract_features("int main() { return 0; }", warnings=flags)["warnings"]
    assert w["available"] is True
    assert w["total"] == 0
    assert w["parentheses"] == 0  # pass ran, none found -> 0, never NaN


def test_no_warnings_evidence_is_nan_not_zero():
    w = extract_features("int main() { return 0; }")["warnings"]
    assert w["available"] is False
    assert _is_nan(w["parentheses"])
    assert _is_nan(w["total"])


# ------------------------------------------------------------------- runtime


def test_asan_heap_overflow_fixture():
    ev = parse_runtime_report(_fixture("asan_heap_overflow.txt"))
    rt = extract_features("int main() { return 0; }", runtime=ev)["runtime"]
    assert rt["available"] is True
    assert rt["crashed"] is True
    assert rt["asan_error"] is True
    assert rt["asan_heap_buffer_overflow"] is True
    assert rt["asan_stack_buffer_overflow"] is False
    assert rt["stack_overflow"] is False
    assert rt["ubsan_error"] is False
    assert rt["valgrind_error"] is False


def test_asan_segv_fixture_is_crash_but_not_stack_overflow():
    ev = parse_runtime_report(_fixture("asan_segv.txt"))
    rt = extract_features("int main() { return 0; }", runtime=ev)["runtime"]
    assert rt["crashed"] is True
    assert rt["signal"] == 11
    assert rt["asan_error"] is True
    # a null deref must not masquerade as class-6 stack overflow evidence
    assert rt["stack_overflow"] is False
    assert rt["asan_heap_buffer_overflow"] is False


def test_stack_overflow_fixture():
    ev = parse_runtime_report(_fixture("asan_stack_overflow.txt"))
    rt = extract_features("int main() { return 0; }", runtime=ev)["runtime"]
    assert rt["crashed"] is True
    assert rt["stack_overflow"] is True
    assert rt["asan_error"] is True
    assert rt["asan_heap_buffer_overflow"] is False


def test_ubsan_signed_overflow_fixture():
    ev = parse_runtime_report(_fixture("ubsan_signed_overflow.txt"))
    rt = extract_features("int main() { return 0; }", runtime=ev)["runtime"]
    assert rt["available"] is True
    assert rt["ubsan_error"] is True
    assert rt["ubsan_signed_overflow"] is True
    assert rt["asan_error"] is False
    # UBSan recover mode does not kill the process
    assert rt["crashed"] is False


def test_valgrind_uninit_fixture():
    ev = parse_runtime_report(_fixture("valgrind_uninit.txt"))
    rt = extract_features("int main() { return 0; }", runtime=ev)["runtime"]
    assert rt["available"] is True
    assert rt["valgrind_error"] is True
    assert rt["valgrind_uninit_value"] is True  # class 4 / det-4 evidence
    assert rt["crashed"] is False  # memcheck errors don't kill the process
    assert rt["asan_error"] is False


def test_clean_runtime_fixture_is_all_false_not_nan():
    ev = parse_runtime_report(_fixture("clean_runtime.txt"))
    rt = extract_features("int main() { return 0; }", runtime=ev)["runtime"]
    assert rt["available"] is True
    assert rt["crashed"] is False
    assert rt["asan_error"] is False
    assert rt["ubsan_error"] is False
    assert rt["valgrind_error"] is False
    assert rt["stack_overflow"] is False


def test_runtime_evidence_absent_is_nan():
    rt = extract_features("int main() { return 0; }")["runtime"]
    assert rt["available"] is False
    assert _is_nan(rt["crashed"])


# --------------------------------------------------------- process facts pass


def test_process_facts_are_carried_through():
    ev = parse_runtime_report(
        _fixture("clean_runtime.txt"), timed_out=True, exit_code=124, duration_s=2.0
    )
    assert ev["timed_out"] is True
    assert ev["exit_code"] == 124
    assert ev["duration_s"] == pytest.approx(2.0)
    rt = extract_features("int main() {}", runtime=ev)["runtime"]
    assert rt["timed_out"] is True
    assert rt["exit_code"] == 124
    assert rt["duration_s"] == pytest.approx(2.0)


# ------------------------------------------------------------------ robustness


def test_malformed_inputs_never_raise():
    for garbage in (None, "", 42, object(), {"not": "a string"}, ["x"]):
        parse_warnings(garbage)  # type: ignore[arg-type]
        parse_runtime_report(garbage)  # type: ignore[arg-type]


def test_garbage_evidence_lands_in_extract_features_without_raising():
    for garbage in (None, 42, object(), {"duration_s": "abc"}):
        out = extract_features(
            "int main() {}", warnings=garbage, runtime=garbage  # type: ignore[arg-type]
        )
        assert "warnings" in out and "runtime" in out
