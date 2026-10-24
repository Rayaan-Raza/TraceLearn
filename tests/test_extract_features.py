"""tracelearn_features v0 interface tests (§5, §6, R1).

Contract under test: `extract_features(source, language, *, warnings, runtime,
tests, cpg, context)` returns every schema block, computes `static` from source
always, fills NaN + available=False for omitted evidence, never raises on
malformed evidence, and never emits `meta`.
"""

from __future__ import annotations

import math

import pytest

from tracelearn_features import SCHEMA_VERSION, extract_features, feature_names
from tracelearn_features.schema import FEATURE_BLOCKS


def _nan(value) -> bool:
    return isinstance(value, float) and math.isnan(value)


def test_returns_all_blocks_in_schema_order():
    out = extract_features("int main() { return 0; }")
    assert list(out.keys()) == list(FEATURE_BLOCKS.keys())


def test_every_schema_feature_present_with_declared_type():
    out = extract_features("int main() { return 0; }")
    for name, ftype in feature_names(with_types=True):
        block, _, short = name.partition(".")
        assert short in out[block], f"missing {name}"
        value = out[block][short]
        if ftype == "int":
            assert value is None or (isinstance(value, int) and not isinstance(value, bool)) or _nan(value), (
                f"{name} = {value!r} not int"
            )
        elif ftype == "float":
            assert value is None or isinstance(value, float) or _nan(value), f"{name} = {value!r} not float"
        elif ftype == "bool":
            assert value is None or isinstance(value, bool) or _nan(value), f"{name} = {value!r} not bool"


def test_static_computed_from_source_always():
    code = (
        "#include <stdio.h>\n"
        "int main() {\n"
        "    int a[10];\n"
        "    for (int i = 0; i < 10; i++) {\n"
        "        if (i) { a[i] = i; }\n"
        "    }\n"
        "    return 0;\n"
        "}\n"
    )
    out = extract_features(code)
    st = out["static"]
    assert st["available"] if "available" in st else True
    assert st["loop_count"] == 1
    assert st["if_count"] == 1
    assert st["include_count"] == 1
    assert st["uses_stdio"] is True
    assert st["array_decl_count"] == 1
    assert st["loc"] == 9


def test_empty_source_does_not_raise():
    out = extract_features("")
    assert out["static"]["loc"] == 0


def test_missing_evidence_blocks_are_nan_with_gate_false():
    out = extract_features("int main() {}")
    # no warnings/runtime/tests/cpg/context evidence passed
    for block in ("warnings", "runtime", "tests", "cpg", "context"):
        feats = out[block]
        gate = feats.get("available")
        assert gate is False or _nan(gate), f"{block}.available = {gate!r}"
    # a countable feature must be NaN (never 0 — §6 null policy)
    assert _nan(out["warnings"]["parentheses"])
    assert _nan(out["runtime"]["asan_error"])
    assert _nan(out["tests"]["total"])


def test_warnings_evidence_parsed_into_enumerated_ids():
    evidence = [
        {"flag": "-Wparentheses", "count": 2},
        {"flag": "-Wunused-variable", "count": 1},
        {"flag": "-Wsomething-new", "count": 3},
    ]
    out = extract_features("int main() {}", warnings=evidence)
    w = out["warnings"]
    assert w["available"] is True
    assert w["parentheses"] == 2
    assert w["unused_variable"] == 1
    assert w["other"] == 3  # unmatched flags land in the catch-all
    assert w["total"] == 6


def test_new_label_defining_warning_flags_are_enumerated():
    evidence = [
        {"flag": "-Winfinite-recursion", "count": 2},
        {"flag": "-Wtautological-compare", "count": 1},
    ]
    w = extract_features("int main() {}", warnings=evidence)["warnings"]
    assert w["infinite_recursion"] == 2
    assert w["tautological_compare"] == 1
    assert w["other"] == 0
    assert w["total"] == 3


def test_runtime_evidence_maps_sanitizer_signals():
    evidence = {
        "crashed": True,
        "signal": 11,
        "duration_s": 0.42,
        "asan_reports": ["heap-buffer-overflow on 0x..."],
        "ubsan_reports": ["signed integer overflow: 2147483647 + 1"],
        "valgrind_reports": ["Conditional jump depends on uninitialised value"],
        "timed_out": False,
        "exit_code": None,
    }
    out = extract_features("int main() {}", runtime=evidence)
    rt = out["runtime"]
    assert rt["available"] is True
    assert rt["crashed"] is True
    assert rt["signal"] == 11
    assert rt["asan_error"] is True
    assert rt["asan_heap_buffer_overflow"] is True
    assert rt["ubsan_signed_overflow"] is True
    assert rt["valgrind_uninit_value"] is True
    assert rt["exit_code"] is None or _nan(rt["exit_code"])


def test_tests_evidence_maps_and_computes_numeric_diff():
    evidence = {
        "total": 5,
        "passed": 4,
        "results": [
            {"ok": True},
            {"ok": True},
            {"ok": False, "expected": "10", "actual": "9", "index": 2, "boundary": False},
            {"ok": True},
            {"ok": True},
        ],
    }
    out = extract_features("int main() {}", tests=evidence)
    ts = out["tests"]
    assert ts["available"] is True
    assert ts["total"] == 5
    assert ts["passed"] == 4
    assert ts["failed"] == 1
    assert ts["first_fail_index"] == 2
    assert ts["first_fail_numeric_diff"] == pytest.approx(-1.0)
    assert ts["boundary_fail_count"] == 0


def test_malformed_evidence_never_raises():
    """NaN means cannot-provide; a garbage payload must not crash a lane (§5)."""
    for bad in (
        {"duration_s": "not-a-number", "asan_reports": "oops"},
        {"results": "not-a-list"},
        {"total": None, "passed": "x"},
        object(),
    ):
        out = extract_features("int main() {}", runtime=bad, tests=bad, cpg=bad)
        assert list(out.keys()) == list(FEATURE_BLOCKS.keys())


def test_no_meta_key_ever_emitted():
    out = extract_features("int main() {}")
    assert "meta" not in out


def test_context_evidence_fills_context_block():
    evidence = {
        "statement": "x" * 300,
        "sample_test_count": 2,
        "has_constraints": True,
        "difficulty": None,
        "concept_tags": ["loops", "arrays"],
        "cpp_submission_count": 12,
    }
    out = extract_features("int main() {}", context=evidence)
    ctx = out["context"]
    assert ctx["statement_length"] == 300
    assert ctx["sample_test_count"] == 2
    assert ctx["constraints_present"] is True
    assert _nan(ctx["difficulty"])
    assert ctx["concept_tag_count"] == 2
    assert ctx["cpp_submission_count"] == 12


def test_cpg_evidence_fills_cpg_block():
    evidence = {
        "node_count": 42,
        "edge_count": 60,
        "max_depth": 5,
        "assign_in_condition_count": 1,
        "assign_feeds_output_count": 1,
        "unguarded_recursion_count": 0,
        "array_write_oob_count": 0,
        "use_before_init_count": 0,
        "decrement_in_loop_count": 0,
        "loop_cond_var_unassigned_count": 1,
        "comparison_count": 3,
        "ast_ref_similarity": 0.71,
    }
    out = extract_features("int main() {}", cpg=evidence)
    cpg = out["cpg"]
    assert cpg["available"] is True
    assert cpg["node_count"] == 42
    assert cpg["loop_cond_var_unassigned_count"] == 1
    assert cpg["ast_ref_similarity"] == pytest.approx(0.71)


def test_semantics_block_computed_from_source():
    """extract_features fills the semantics block from source automatically."""
    source = "int main() { int x = 0; for(int i=0; i<n; i++) x++; return x; }"
    out = extract_features(source)
    sem = out["semantics"]
    assert sem["init_zero"] == 1          # int x = 0
    assert sem["loop_lt"] == 1            # i < n
    assert sem["increment"] >= 1          # i++ and x++
    assert sem["assign_in_cond"] == 0
    assert sem["recursion"] == 0


def test_semantics_block_nan_for_empty_source():
    """Empty source produces NaN semantics, not zeros (no available gate in semantics block)."""
    out = extract_features("")
    sem = out["semantics"]
    assert "available" not in sem
    for key, val in sem.items():
        assert _nan(val), f"semantics.{key} should be NaN for empty source, got {val!r}"


def test_semantics_recursion_and_base_case():
    """Recursive function with base case sets both flags."""
    source = (
        "int fib(int n) {\n"
        "    if (n <= 1) return n;\n"
        "    return fib(n-1) + fib(n-2);\n"
        "}\n"
    )
    out = extract_features(source)
    sem = out["semantics"]
    assert sem["recursion"] == 1
    assert sem["base_case"] == 1
    assert sem["loop_lt"] == 0


def test_semantics_assign_in_cond_and_decrement():
    """assign-in-condition and decrement signals are extracted correctly."""
    source = "int f(int* p) { int n = 10; while(n--) { int x; if(x = *p++) {} } return 0; }"
    out = extract_features(source)
    sem = out["semantics"]
    assert sem["assign_in_cond"] == 1   # if(x = *p++)
    assert sem["decrement"] >= 1        # n--


def test_semantics_idx_offset_features():
    """Array index ±1 accesses are detected."""
    source = "void f(int* a, int i) { int x = a[i-1]; int y = a[i+1]; }"
    out = extract_features(source)
    sem = out["semantics"]
    assert sem["idx_minus1"] == 1
    assert sem["idx_plus1"] == 1


def test_schema_version_and_version_stamp():
    assert SCHEMA_VERSION == "1.1"
    import tracelearn_features

    assert tracelearn_features.__version__
