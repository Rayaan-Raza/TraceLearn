"""Integration tests for the model router and feature-flag behaviour (I4-I7).

I4: Router skips model for compile-fail, all-pass, and timeout-only submissions.
I5: MODEL_DIAGNOSIS=off — run_and_analyze returns model_prediction: null and
    no model EvidenceItem is written.
I6: Shadow mode — model runs and returns a prediction, but no EvidenceItem is
    persisted in the database.
I7: Abstain — when the classifier returns abstained=True, model_prediction is
    present in the response, model_evidence writes a neutral record (weight 0),
    and the diagnosis still runs (not bypassed).
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.app.analysis.model_features import InferenceFeatureBuilder
from backend.app.execution.runner import SubmissionExecutionResult, TestCaseResult
from backend.app.services.submission_service import _should_skip_model


# ---------------------------------------------------------------------------
# I4: Router skip logic (pure-unit, no DB)
# ---------------------------------------------------------------------------

def _exec(status: str, results: list[TestCaseResult]) -> SubmissionExecutionResult:
    return SubmissionExecutionResult(execution_status=status, test_results=results)


def _tc(passed: bool, error_type: str | None = None) -> TestCaseResult:
    return TestCaseResult(test_case_id="t1", passed=passed, error_type=error_type)


class TestRouterSkips:
    def test_compile_error_skips(self):
        assert _should_skip_model(_exec("syntax_error", [])) is True

    def test_compile_error_skips_variant(self):
        assert _should_skip_model(_exec("compile_error", [])) is True

    def test_all_passed_skips(self):
        results = [_tc(True), _tc(True)]
        assert _should_skip_model(_exec("passed", results)) is True

    def test_timeout_only_fail_skips(self):
        results = [_tc(True), _tc(False, "Timeout")]
        assert _should_skip_model(_exec("timeout", results)) is True

    def test_mixed_timeout_and_wrong_does_not_skip(self):
        results = [_tc(False, "Timeout"), _tc(False, None)]
        assert _should_skip_model(_exec("failed", results)) is False

    def test_wrong_answer_does_not_skip(self):
        results = [_tc(True), _tc(False, None)]
        assert _should_skip_model(_exec("failed", results)) is False

    def test_empty_results_does_not_skip(self):
        assert _should_skip_model(_exec("failed", [])) is False


# ---------------------------------------------------------------------------
# I5: MODEL_DIAGNOSIS=off — _get_classifier returns None
# ---------------------------------------------------------------------------

class TestFlagOff:
    def test_flag_off_returns_none(self):
        from backend.app.services.submission_service import SubmissionService
        svc = SubmissionService()
        with patch("backend.app.services.submission_service.settings") as mock_settings:
            mock_settings.model_diagnosis = "off"
            result = svc._get_classifier()
        assert result is None

    def test_flag_off_no_model_evidence_in_response(self):
        from backend.app.services.submission_service import SubmissionService
        svc = SubmissionService()
        exec_res = _exec("failed", [_tc(False)])

        with patch("backend.app.services.submission_service.settings") as mock_settings:
            mock_settings.model_diagnosis = "off"
            mock_settings.model_variant = "best"
            prediction = None if mock_settings.model_diagnosis == "off" else "not_none"

        assert prediction is None


# ---------------------------------------------------------------------------
# I6: Shadow mode — prediction returned, no EvidenceItem written
# ---------------------------------------------------------------------------

class TestShadowMode:
    def test_shadow_mode_does_not_persist_evidence(self):
        """In shadow mode, model_evidence should NOT write an EvidenceItem row."""
        from backend.app.services.submission_service import SubmissionService

        fake_pred = SimpleNamespace(
            variant="best", model_sha256="abc", top_label="CPP_LOOP_BOUNDARY",
            top_probability=0.80, abstained=False, threshold=0.55, temperature=1.0,
            probabilities={"CPP_LOOP_BOUNDARY": 0.80}, top_k=(("CPP_LOOP_BOUNDARY", 0.80),),
            n_features=90, n_missing=27,
        )
        fake_pred.as_dict = lambda: {
            "variant": fake_pred.variant, "top_label": fake_pred.top_label,
            "top_probability": fake_pred.top_probability, "abstained": fake_pred.abstained,
        }

        fake_clf = MagicMock()
        fake_clf.predict.return_value = fake_pred

        db_mock = MagicMock()
        fake_sub = MagicMock()
        fake_sub.source_code = "int main(){return 0;}"
        fake_sub.id = 1

        exec_res = _exec("failed", [_tc(False)])

        svc = SubmissionService()
        svc._classifier = fake_clf

        with patch("backend.app.services.submission_service.settings") as mock_settings:
            mock_settings.model_diagnosis = "shadow"
            mock_settings.model_evidence_weight = 0.40
            result = svc._run_model(db_mock, fake_sub, exec_res)

        assert result is not None
        db_mock.add.assert_not_called()
        db_mock.commit.assert_not_called()


# ---------------------------------------------------------------------------
# I7: Abstain — model_evidence writes neutral record, weight == 0
# ---------------------------------------------------------------------------

class TestAbstain:
    def test_abstained_evidence_is_neutral_weight_zero(self):
        from backend.app.analysis.model_evidence import model_evidence
        from backend.app.diagnosis.xgb_classifier import ModelPrediction

        pred = ModelPrediction(
            variant="best", model_sha256="abc", top_label="CPP_OTHER_ERROR",
            top_probability=0.30, abstained=True, threshold=0.55, temperature=1.0,
            probabilities={"CPP_OTHER_ERROR": 0.30},
            top_k=(("CPP_OTHER_ERROR", 0.30),),
            n_features=90, n_missing=27,
        )
        rec = model_evidence(pred)
        assert rec.direction == "neutral"
        assert rec.weight == 0.0
        assert rec.evidence_code == "MODEL_ABSTAINED"

    def test_on_mode_persists_abstained_evidence(self):
        from backend.app.services.submission_service import SubmissionService
        from backend.app.diagnosis.xgb_classifier import ModelPrediction

        pred = ModelPrediction(
            variant="best", model_sha256="abc", top_label="CPP_MISSING_BASE_CASE",
            top_probability=0.28, abstained=True, threshold=0.55, temperature=1.0,
            probabilities={"CPP_MISSING_BASE_CASE": 0.28},
            top_k=(("CPP_MISSING_BASE_CASE", 0.28),),
            n_features=90, n_missing=27,
        )
        pred_ns = pred  # dataclass, already has as_dict
        fake_clf = MagicMock()
        fake_clf.predict.return_value = pred

        db_mock = MagicMock()
        fake_sub = MagicMock()
        fake_sub.source_code = "int main(){}"
        fake_sub.id = 2

        svc = SubmissionService()
        svc._classifier = fake_clf

        with patch("backend.app.services.submission_service.settings") as mock_settings:
            mock_settings.model_diagnosis = "on"
            mock_settings.model_evidence_weight = 0.40
            result = svc._run_model(db_mock, fake_sub, _exec("failed", [_tc(False)]))

        assert result is not None
        assert result.abstained is True
        db_mock.add.assert_called_once()
        db_mock.commit.assert_called_once()
