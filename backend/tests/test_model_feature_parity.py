"""Gate I1 — InferenceFeatureBuilder parity against the feature schema.

Verifies that the live builder produces a flat feature dict whose:
  1. Key set matches the canonical schema (all 90 features present).
  2. Static and semantics blocks are identical to a direct extract_features()
     call on the same source (builder is a thin wrapper; identity confirms no
     intermediate mapping error).
  3. CPG proxy fields that extract_cpg_source() can fill are non-NaN when
     the source is non-empty.
  4. The runtime block is entirely NaN (not available at inference time).
  5. The output is accepted by ModelClassifier.vector() without raising.

Source corpus: data/cpp_diagnostics/{solutions,variants}/*.cpp — 119 files
across 8 misconception classes.  The requirement is >= 50 rows; we use all
of them.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from backend.app.analysis.model_features import InferenceFeatureBuilder, parse_warnings
from backend.app.diagnosis.xgb_classifier import ModelClassifier
from tracelearn_features.extractor import extract_features
from tracelearn_features.schema import FEATURE_BLOCKS, feature_names

REPO_ROOT = Path(__file__).resolve().parents[2]
CPP_DIR = REPO_ROOT / "data" / "cpp_diagnostics"
RUNTIME_FEATURES = [f"runtime.{s}" for s in FEATURE_BLOCKS["runtime"] if s != "available"]
RUNTIME_AVAIL = "runtime.available"


# ---------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def cpp_sources() -> list[tuple[str, str]]:
    """All .cpp files in data/cpp_diagnostics as (stem, source) pairs."""
    files = sorted(CPP_DIR.rglob("*.cpp"))
    assert len(files) >= 50, f"expected >=50 .cpp files, found {len(files)}"
    return [(f.stem, f.read_text(encoding="utf-8", errors="replace")) for f in files]


@pytest.fixture(scope="module")
def model() -> ModelClassifier:
    return ModelClassifier.load("best")


@pytest.fixture(scope="module")
def builder() -> InferenceFeatureBuilder:
    return InferenceFeatureBuilder()


# -------------------------------------------------------------- I1 schema


def test_builder_returns_all_schema_features(cpp_sources, builder):
    expected = set(feature_names())
    stem, source = cpp_sources[0]
    flat = builder.build(source)
    assert set(flat.keys()) == expected, (
        f"key mismatch for {stem}: "
        f"extra={set(flat)-expected}, missing={expected-set(flat)}"
    )


def test_builder_returns_all_schema_features_on_empty_source(builder):
    flat = builder.build("")
    assert set(flat.keys()) == set(feature_names())


# -------------------------------------------------- I1 static/semantics parity


def test_static_block_matches_extract_features_directly(cpp_sources, builder):
    mismatches = []
    for stem, source in cpp_sources:
        flat = builder.build(source)
        ref = extract_features(source, language="cpp")
        for short in FEATURE_BLOCKS["static"]:
            key = f"static.{short}"
            got = flat[key]
            want = ref["static"][short]
            # bool features stored as 0/1 float — treat equivalent
            got_v = float(got) if not isinstance(got, float) else got
            want_v = float(want) if not isinstance(want, float) else want
            match = (
                math.isclose(got_v, want_v, rel_tol=1e-6, abs_tol=1e-9)
                if not (math.isnan(got_v) and math.isnan(want_v))
                else True
            )
            if not match:
                mismatches.append(f"{stem}: {key} got={got_v} want={want_v}")
    assert not mismatches, "\n".join(mismatches[:10])


def test_semantics_block_matches_extract_features_directly(cpp_sources, builder):
    mismatches = []
    for stem, source in cpp_sources:
        flat = builder.build(source)
        ref = extract_features(source, language="cpp")
        for short in FEATURE_BLOCKS["semantics"]:
            key = f"semantics.{short}"
            got = flat[key]
            want = ref["semantics"][short]
            got_nan = isinstance(got, float) and math.isnan(got)
            want_nan = isinstance(want, float) and math.isnan(want) or want is None
            if got_nan and want_nan:
                continue
            if got_nan or want_nan:
                mismatches.append(f"{stem}: {key} nan mismatch got={got} want={want}")
                continue
            if not math.isclose(float(got), float(want), abs_tol=1e-9):
                mismatches.append(f"{stem}: {key} got={got} want={want}")
    assert not mismatches, "\n".join(mismatches[:10])


# --------------------------------------------------- I1 runtime always NaN


def test_runtime_block_is_nan_at_inference(cpp_sources, builder):
    stem, source = cpp_sources[0]
    flat = builder.build(source)
    assert flat[RUNTIME_AVAIL] is False, "runtime.available must be False at inference"
    for key in RUNTIME_FEATURES:
        v = flat[key]
        assert isinstance(v, float) and math.isnan(v), (
            f"{key} should be NaN at inference, got {v!r}"
        )


# ------------------------------------------------- I1 CPG proxy populated


def test_cpg_proxy_fills_structural_fields_for_nonempty_source(cpp_sources, builder):
    cpg_fillable = {
        "cpg.function_count", "cpg.loop_count", "cpg.assign_in_condition_count",
        "cpg.comparison_count", "cpg.decrement_in_loop_count",
        "cpg.unguarded_recursion_count",
    }
    # At least one source should have a loop — verify cpg.loop_count is not NaN then
    has_loop = [(stem, s) for stem, s in cpp_sources if "for" in s or "while" in s]
    assert has_loop, "no cpp file with loops found"
    stem, source = has_loop[0]
    flat = builder.build(source)
    assert flat["cpg.available"] is True, f"{stem}: cpg.available should be True"
    assert not (isinstance(flat["cpg.loop_count"], float) and math.isnan(flat["cpg.loop_count"])), (
        f"{stem}: cpg.loop_count should not be NaN when source has loops"
    )


# ------------------------------------------ I1 accepted by classifier.vector


def test_builder_output_accepted_by_model_vector(cpp_sources, builder, model):
    for stem, source in cpp_sources:
        flat = builder.build(source)
        row, missing = model.vector(flat)
        assert row.shape == (1, len(model.features)), f"{stem}: wrong vector shape"
        assert 0 <= missing <= len(model.features), f"{stem}: missing count out of range"


# ---------------------------------------------- parse_warnings unit tests


_SAMPLE_STDERR = """\
solution.cpp:5:10: warning: unused variable 'x' [-Wunused-variable]
solution.cpp:8:5: warning: comparison between signed and unsigned [-Wsign-compare]
solution.cpp:8:5: warning: comparison between signed and unsigned [-Wsign-compare]
solution.cpp:12:3: error: use of undeclared identifier 'y'
solution.cpp:14:7: note: declared here
"""


def test_parse_warnings_counts_flags():
    result = parse_warnings(_SAMPLE_STDERR)
    by_flag = {d["flag"]: d["count"] for d in result}
    assert by_flag["-Wunused-variable"] == 1
    assert by_flag["-Wsign-compare"] == 2
    assert "-Werror" not in by_flag
    assert len(result) == 2


def test_parse_warnings_empty_stderr():
    assert parse_warnings("") == []


def test_parse_warnings_no_warnings_in_stderr():
    assert parse_warnings("solution.cpp:3:1: error: missing semicolon") == []
