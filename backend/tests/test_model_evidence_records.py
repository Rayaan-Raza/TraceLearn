"""Integration tests for model evidence record production (I8-I12).

I8:  map_test_results categorises all error_type values correctly.
I9:  OBSERVED_SOURCES includes MODEL after the B4 change.
I10: model_evidence emits a support record with weight > 0 for a confident,
     mappable prediction.
I11: model_evidence emits a neutral record (weight 0) for CPP_OTHER_ERROR even
     when the classifier did NOT abstain.
I12: InferenceFeatureBuilder with empty source / no stderr / no tests produces a
     complete feature vector (all schema keys present, most NaN).
"""
from __future__ import annotations

import math

import pytest

from backend.app.analysis.model_features import InferenceFeatureBuilder, map_test_results
from backend.app.db.models import EvidenceSourceType
from backend.app.diagnosis.evidence_contract import OBSERVED_SOURCES


# ---------------------------------------------------------------------------
# I8: map_test_results categorisation
# ---------------------------------------------------------------------------

class _TC:
    """Minimal TestCaseResult stand-in."""
    def __init__(self, passed: bool, error_type: str | None = None,
                 expected_output: object = None, actual_output: object = None):
        self.passed = passed
        self.error_type = error_type
        self.expected_output = expected_output
        self.actual_output = actual_output


class TestMapTestResults:
    def test_all_passed_returns_ok_items(self):
        result = map_test_results([_TC(True), _TC(True)])
        assert result is not None
        assert all(r["ok"] for r in result["results"])

    def test_timeout_error_kind(self):
        result = map_test_results([_TC(False, "Timeout")])
        assert result["results"][0]["kind"] == "timeout"

    def test_runtime_error_kind(self):
        result = map_test_results([_TC(False, "RuntimeError")])
        assert result["results"][0]["kind"] == "crash"

    def test_memory_limit_kind(self):
        result = map_test_results([_TC(False, "MemoryLimitExceeded")])
        assert result["results"][0]["kind"] == "crash"

    def test_output_limit_kind(self):
        result = map_test_results([_TC(False, "OutputLimitExceeded")])
        assert result["results"][0]["kind"] == "crash"

    def test_wrong_answer_kind(self):
        result = map_test_results([_TC(False, None, "1", "2")])
        assert result["results"][0]["kind"] == "wrong_answer"

    def test_expected_actual_propagated(self):
        result = map_test_results([_TC(False, None, "42", "0")])
        item = result["results"][0]
        assert item.get("expected") == "42"
        assert item.get("actual") == "0"

    def test_empty_list_returns_none(self):
        assert map_test_results([]) is None


# ---------------------------------------------------------------------------
# I9: OBSERVED_SOURCES includes MODEL
# ---------------------------------------------------------------------------

class TestEvidenceContractIncludesModel:
    def test_model_in_observed_sources(self):
        assert EvidenceSourceType.MODEL in OBSERVED_SOURCES

    def test_model_value_in_string_set(self):
        from backend.app.diagnosis.evidence_contract import OBSERVED_SOURCE_VALUES
        assert "model" in OBSERVED_SOURCE_VALUES


# ---------------------------------------------------------------------------
# I10: confident prediction → support record, weight > 0
# ---------------------------------------------------------------------------

class TestModelEvidenceConfident:
    def test_confident_mappable_gives_support_record(self):
        from backend.app.analysis.model_evidence import model_evidence
        from backend.app.diagnosis.xgb_classifier import ModelPrediction

        pred = ModelPrediction(
            variant="best", model_sha256="abc", top_label="CPP_LOOP_BOUNDARY",
            top_probability=0.80, abstained=False, threshold=0.55, temperature=1.0,
            probabilities={"CPP_LOOP_BOUNDARY": 0.80},
            top_k=(("CPP_LOOP_BOUNDARY", 0.80),),
            n_features=90, n_missing=27,
        )
        rec = model_evidence(pred)
        assert rec.direction == "support"
        assert rec.weight > 0.0
        assert rec.evidence_code == "MODEL_PREDICTION"
        assert rec.misconception_id is not None

    def test_weight_scales_with_probability(self):
        from backend.app.analysis.model_evidence import model_evidence
        from backend.app.diagnosis.xgb_classifier import ModelPrediction

        def _pred(p: float) -> ModelPrediction:
            return ModelPrediction(
                variant="best", model_sha256="x", top_label="CPP_INT_OVERFLOW",
                top_probability=p, abstained=False, threshold=0.55, temperature=1.0,
                probabilities={"CPP_INT_OVERFLOW": p},
                top_k=(("CPP_INT_OVERFLOW", p),),
                n_features=90, n_missing=0,
            )

        rec_low = model_evidence(_pred(0.60))
        rec_high = model_evidence(_pred(0.90))
        assert rec_high.weight > rec_low.weight


# ---------------------------------------------------------------------------
# I11: CPP_OTHER_ERROR → neutral record even without abstain
# ---------------------------------------------------------------------------

class TestModelEvidenceOtherError:
    def test_other_error_gives_neutral_record(self):
        from backend.app.analysis.model_evidence import model_evidence
        from backend.app.diagnosis.xgb_classifier import ModelPrediction

        pred = ModelPrediction(
            variant="best", model_sha256="abc", top_label="CPP_OTHER_ERROR",
            top_probability=0.70, abstained=False, threshold=0.55, temperature=1.0,
            probabilities={"CPP_OTHER_ERROR": 0.70},
            top_k=(("CPP_OTHER_ERROR", 0.70),),
            n_features=90, n_missing=0,
        )
        rec = model_evidence(pred)
        assert rec.direction == "neutral"
        assert rec.weight == 0.0
        assert rec.evidence_code == "MODEL_OTHER_ERROR"
        assert rec.misconception_id is None


# ---------------------------------------------------------------------------
# I12: InferenceFeatureBuilder with no inputs
# ---------------------------------------------------------------------------

class TestBuilderMinimalInputs:
    def test_empty_source_returns_all_schema_keys(self):
        from tracelearn_features.schema import feature_names
        builder = InferenceFeatureBuilder()
        flat = builder.build(source="", compile_stderr="", test_results=None)
        schema_keys = set(feature_names())
        assert schema_keys == set(flat.keys())

    def test_empty_source_has_nan_for_cpg(self):
        builder = InferenceFeatureBuilder()
        flat = builder.build(source="", compile_stderr="", test_results=None)
        # cpg.available is a boolean flag; numeric cpg features should be NaN
        cpg_numeric = [k for k in flat if k.startswith("cpg.") and k != "cpg.available"]
        assert cpg_numeric, "expected numeric cpg block keys"
        assert all(math.isnan(flat[k]) for k in cpg_numeric), "numeric cpg keys should be NaN for empty source"

    def test_no_warnings_produces_zero_warning_flags(self):
        builder = InferenceFeatureBuilder()
        flat = builder.build(source="int main(){return 0;}", compile_stderr="", test_results=None)
        warn_keys = [k for k in flat if k.startswith("warnings.")]
        assert all(flat[k] == 0.0 or math.isnan(flat[k]) for k in warn_keys), \
            "no warnings in stderr → all warning features should be 0 or NaN"
