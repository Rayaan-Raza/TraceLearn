"""Lane-evidence normalization tests (merge integration, §6 row shape).

Every lane emits its evidence in its own raw vocabulary:

- SYNTHETIC (tier0): `static.source_code`, raw gcc text in
  `warnings.compile_warnings`, and test totals in `runtime.tests_*`;
- CODESTREAM (tier1a): `static=null`, raw `-Wflag` count keys, a sandbox
  runtime dict (`any_crash`/`sanitizer`/`valgrind`) and test results keyed
  by `status`;
- PROGPEDIA (tier1b): already canonical (the lane ran the extractor).

The merge must map each lane's vocabulary onto the canonical registry before
flattening to `features.csv` — otherwise the canonical column is NaN for a
source that actually provided the evidence. Normalization never overwrites a
value a lane already supplied.

Null policy (§6): evidence a lane does not carry stays NaN. In particular an
empty CodeStream warnings dict means "not mined", not "zero warnings".
"""

from __future__ import annotations

import math

import pytest

from tracelearn_features.normalize import normalize_row

SYN_CODE = """#include <iostream>
int main() {
    int n;
    std::cin >> n;
    int s = 0;
    for (int i = 1; i < n; i++) {
        s += i;
    }
    std::cout << s << std::endl;
}
"""

CS_CODE = (
    "int main() { int a[10]; for (int i = 0; i <= 10; i++) a[i] = i; "
    "return a[0]; }"
)

SYN_WARNINGS = (
    "x.cpp:12:12: warning: suggest parentheses around assignment used as "
    "truth value [-Wparentheses]\n"
    "x.cpp:13:5: warning: 'v' is used uninitialized [-Wuninitialized]\n"
    "x.cpp:14:5: warning: self-comparison always evaluates to true "
    "[-Wtautological-compare]\n"
)


def _synthetic_row() -> dict:
    return {
        "row_id": "mut-1",
        "dataset_source": "SYNTHETIC",
        "language": "cpp",
        "label": "CPP_LOOP_BOUNDARY",
        "static": {"source_code": SYN_CODE, "source_code_sha256": "ab", "loc": 10},
        "warnings": {"compile_warnings": SYN_WARNINGS},
        "runtime": {"tests_passed": 1, "tests_failed": 2, "tests_total": 3,
                    "sanitizer_ok": False},
        "tests": {},
        "cpg": {},
        "context": {},
    }


def _codestream_row() -> dict:
    return {
        "row_id": "cs-1",
        "dataset_source": "CODESTREAM",
        "language": "cpp",
        "label": "CPP_ARRAY_BOUNDS",
        "static": None,
        "warnings": {"-Wparentheses": 2, "-Wunused-result": 1},
        "runtime": {
            "any_crash": True,
            "any_timeout": False,
            "signals": [11],
            "stack_overflow": False,
            "max_seconds": 0.0351,
            "sanitizer": {
                "complete": True,
                "kinds": {"asan:heap-buffer-overflow": 1,
                          "ubsan:signed-integer-overflow": 1},
                "reports": [
                    {"tool": "asan", "kind": "heap-buffer-overflow"},
                    {"tool": "ubsan", "kind": "signed-integer-overflow"},
                ],
            },
            "valgrind": {
                "complete": True,
                "kinds": {"uninit-value": {"count": 1}},
                "uninit": True,
                "error_count": 1,
            },
        },
        "tests": {
            "total": 3,
            "passed": 1,
            "passed_lenient": 1,
            "results": [
                {"status": "pass"},
                {"status": "wrong",
                 "diff": {"numeric_deltas": [2, 1], "max_abs_delta": 2}},
                {"status": "crash"},
            ],
        },
        "context": {"source_problem_id": "p-1", "tests_total": 20,
                    "statement_chars": 1860},
    }


# ------------------------------------------------------------------ synthetic


def test_synthetic_static_is_mined_from_embedded_mutant_code():
    out = normalize_row(_synthetic_row())
    static = out["static"]
    assert static["loc"] == 10                 # lane value preserved
    assert static["sloc"] > 1
    assert static["loop_count"] == 1
    assert static["function_count"] == 1
    assert static["include_count"] == 1
    assert static["token_count"] > 10


def test_synthetic_semantics_are_mined_from_embedded_code():
    semantics = normalize_row(_synthetic_row())["semantics"]
    assert semantics["loop_lt"] == 1
    assert semantics["increment"] == 1
    assert semantics["assign_in_cond"] == 0
    assert semantics["recursion"] == 0


def test_synthetic_warning_text_maps_to_canonical_counts():
    warnings = normalize_row(_synthetic_row())["warnings"]
    assert warnings["available"] is True
    assert warnings["parentheses"] == 1
    assert warnings["uninitialized"] == 1
    assert warnings["total"] == 3
    assert warnings["tautological_compare"] == 1
    assert warnings["other"] == 0


def test_infinite_recursion_warning_maps_to_canonical_count():
    row = _synthetic_row()
    row["warnings"] = {
        "compile_warnings": "x.cpp:9:1: warning: infinite recursion detected "
                            "[-Winfinite-recursion]\n"
    }
    warnings = normalize_row(row)["warnings"]
    assert warnings["infinite_recursion"] == 1
    assert warnings["other"] == 0


def test_gcc_format_warning_flag_trailing_equals_is_normalized():
    row = _synthetic_row()
    row["warnings"] = {
        "compile_warnings": "x.cpp:3:1: warning: format issue [-Wformat=]\n"
    }
    warnings = normalize_row(row)["warnings"]
    assert warnings["format"] == 1
    assert warnings["other"] == 0


def test_synthetic_test_totals_bridge_into_tests_block():
    tests = normalize_row(_synthetic_row())["tests"]
    assert tests["available"] is True
    assert tests["total"] == 3
    assert tests["passed"] == 1
    assert tests["failed"] == 2
    assert tests["pass_rate"] == pytest.approx(1 / 3)
    # the lane carried no failure taxonomy -> unknown, never zero
    assert math.isnan(tests.get("wrong_answer_count", math.nan))


def test_synthetic_empty_warning_text_is_zero_warnings_not_unknown():
    row = _synthetic_row()
    row["warnings"] = {"compile_warnings": ""}
    warnings = normalize_row(row)["warnings"]
    assert warnings["available"] is True
    assert warnings["total"] == 0


def test_synthetic_runtime_is_not_fabricated_from_test_counts():
    # tests_passed/failed are test results, not crash/sanitizer evidence
    runtime = normalize_row(_synthetic_row())["runtime"]
    assert runtime.get("crashed") is None or (
        isinstance(runtime.get("crashed"), float) and math.isnan(runtime["crashed"])
    )


# ----------------------------------------------------------------- codestream


def test_codestream_static_is_mined_from_resolved_code():
    static = normalize_row(_codestream_row(), code=CS_CODE)["static"]
    assert static["loop_count"] == 1
    assert static["function_count"] == 1
    assert static["array_decl_count"] >= 1
    assert static["return_count"] == 1


def test_codestream_semantics_are_mined_from_resolved_code():
    semantics = normalize_row(_codestream_row(), code=CS_CODE)["semantics"]
    assert semantics["loop_le"] == 1
    assert semantics["increment"] == 1
    assert semantics["idx_plus1"] == 0
    assert semantics["assign_in_cond"] == 0


def test_codestream_warning_flag_keys_map_to_canonical_counts():
    warnings = normalize_row(_codestream_row(), code=CS_CODE)["warnings"]
    assert warnings["available"] is True
    assert warnings["parentheses"] == 2
    assert warnings["total"] == 3
    assert warnings["other"] == 1              # -Wunused-result


def test_codestream_empty_warnings_mean_unknown_not_zero():
    row = _codestream_row()
    row["warnings"] = {}
    warnings = normalize_row(row, code=CS_CODE)["warnings"]
    assert warnings.get("available") is not True
    assert not warnings or math.isnan(warnings.get("total", math.nan))


def test_codestream_runtime_sandbox_shape_maps_to_canonical_block():
    runtime = normalize_row(_codestream_row(), code=CS_CODE)["runtime"]
    assert runtime["crashed"] is True
    assert runtime["timed_out"] is False
    assert runtime["signal"] == 11
    assert runtime["duration_s"] == pytest.approx(0.0351)
    assert runtime["asan_error"] is True
    assert runtime["asan_heap_buffer_overflow"] is True
    assert runtime["asan_stack_buffer_overflow"] is False
    assert runtime["ubsan_error"] is True
    assert runtime["ubsan_signed_overflow"] is True
    assert runtime["valgrind_error"] is True
    assert runtime["valgrind_uninit_value"] is True


def test_codestream_test_status_vocabulary_maps_to_tests_block():
    tests = normalize_row(_codestream_row(), code=CS_CODE)["tests"]
    assert tests["available"] is True
    assert tests["total"] == 3
    assert tests["passed"] == 1
    assert tests["failed"] == 2
    assert tests["wrong_answer_count"] == 1
    assert tests["runtime_error_count"] == 1
    assert tests["timeout_count"] == 0
    assert tests["first_fail_index"] == 1
    assert tests["first_fail_numeric_diff"] == pytest.approx(2.0)
    # no per-test boundary metadata -> unknown, never a fabricated zero
    assert math.isnan(tests.get("boundary_fail_count", math.nan))


def test_codestream_context_shape_maps_to_canonical_block():
    context = normalize_row(_codestream_row(), code=CS_CODE)["context"]
    assert context["statement_length"] == 1860
    assert context["sample_test_count"] == 20
    assert context["sample_tests_present"] is True


# ------------------------------------------------------- preservation / nulls


def test_canonical_lane_values_are_never_overwritten():
    row = {
        "row_id": "pg-1",
        "dataset_source": "PROGPEDIA",
        "language": "c",
        "label": "CPP_ARRAY_BOUNDS",
        "static": {"loc": 32, "sloc": 23, "loop_count": 5},
        "warnings": {"available": True, "total": 2, "other": 2},
        "runtime": {"available": False},
        "tests": {"available": False},
        "cpg": {"available": True, "node_count": 135},
        "semantics": {"assign_in_cond": 0, "recursion": 0},
        "context": {"available": True, "statement_length": 1860},
    }
    out = normalize_row(row, code="int main() { return 0; }")
    assert out["static"] == {"loc": 32, "sloc": 23, "loop_count": 5}
    assert out["warnings"] == {"available": True, "total": 2, "other": 2}
    assert out["cpg"] == {"available": True, "node_count": 135}
    assert out["semantics"] == {"assign_in_cond": 0, "recursion": 0}


def test_missing_code_leaves_static_absent():
    row = _codestream_row()
    out = normalize_row(row, code=None)
    assert out["static"] is None
    assert not out.get("semantics")


# ------------------------------------------- PROGPedia rows executed by the sandbox

def _progpedia_exec_row() -> dict:
    row = _codestream_row()
    row.update(row_id="pgx-1", dataset_source="PROGPEDIA", evidence_vocab="sandbox_runner",
               context={"available": True, "statement_length": 1860, "sample_test_count": 2,
                        "sample_tests_present": True, "constraints_present": False})
    return row


def test_progpedia_sandbox_vocab_maps_like_codestream():
    out = normalize_row(_progpedia_exec_row(), code=CS_CODE)
    assert out["runtime"]["asan_heap_buffer_overflow"] is True
    assert out["tests"]["total"] == 3 and out["tests"]["wrong_answer_count"] == 1
    assert out["static"]["loc"] >= 1  # mined from the row's own code
    assert out["context"]["sample_test_count"] == 2  # canonical context kept, not overwritten


def test_canonical_progpedia_rows_are_still_left_alone():
    row = _progpedia_exec_row()
    row.pop("evidence_vocab")
    row["static"] = None
    out = normalize_row(row, code=CS_CODE)
    assert out["static"] is None  # a pg-lane gap stays visible


def test_explicit_compiled_flag_means_zero_warnings():
    row = _progpedia_exec_row()
    row["warnings"] = {"_compiled": True}
    warnings = normalize_row(row, code=CS_CODE)["warnings"]
    assert warnings["available"] is True and warnings["total"] == 0
