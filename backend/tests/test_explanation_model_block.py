"""A9: explanation_json model block tests.

Verifies that after run_and_analyze the Diagnosis records produced by both
engines carry a "model" key in their explanation_json when a prediction is
available, and that the key is absent (or null) when the model is off.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.app.execution.runner import SubmissionExecutionResult, TestCaseResult


def _exec(status: str, results: list) -> SubmissionExecutionResult:
    return SubmissionExecutionResult(execution_status=status, test_results=results)


def _tc(passed: bool, error_type: str | None = None) -> TestCaseResult:
    return TestCaseResult(test_case_id="t1", passed=passed, error_type=error_type)


def _make_pred(top_label="CPP_LOOP_BOUNDARY", top_prob=0.82, abstained=False):
    ns = SimpleNamespace(
        variant="best", model_sha256="abc", top_label=top_label,
        top_probability=top_prob, abstained=abstained, threshold=0.55,
        temperature=1.0, probabilities={top_label: top_prob},
        top_k=((top_label, top_prob),), n_features=90, n_missing=10,
    )
    ns.as_dict = lambda: {
        "variant": ns.variant, "top_label": ns.top_label,
        "top_probability": ns.top_probability, "abstained": ns.abstained,
        "threshold": ns.threshold, "temperature": ns.temperature,
    }
    return ns


class TestExplanationJsonModelBlock:
    def _run(self, diagnosis_on: bool, prediction_present: bool):
        from backend.app.services.submission_service import SubmissionService

        fake_pred = _make_pred() if prediction_present else None
        fake_clf = MagicMock()
        if fake_pred:
            fake_clf.predict.return_value = fake_pred

        # Minimal Diagnosis stubs with mutable explanation_json
        def _diag(mode_val):
            d = MagicMock()
            d.id = 1
            d.mode.value = mode_val
            d.primary_misconception = "CPP_LOOP_BOUNDARY"
            d.primary_confidence = 0.75
            d.alternative_misconception = None
            d.alternative_confidence = None
            d.uncertainty_level.value = "low"
            d.requires_teacher_review = False
            d.explanation_json = json.dumps({"scores": {}, "supporting": [], "conflicting": []})
            return d

        db_mock = MagicMock()
        fake_sub = MagicMock()
        fake_sub.id = 7
        fake_sub.source_code = "int main(){return 0;}"

        exec_res = _exec("failed", [_tc(False)])

        svc = SubmissionService()
        if prediction_present:
            svc._classifier = fake_clf

        current_diag = _diag("current_only")
        history_diag = _diag("history_aware")

        with (
            patch("backend.app.services.submission_service.settings") as ms,
            patch("backend.app.services.submission_service.run_submission_tests", return_value=exec_res),
            patch.object(svc, "current_engine") as ce,
            patch.object(svc, "history_engine") as he,
            patch.object(svc, "hint_policy") as hp,
        ):
            ms.model_diagnosis = "on" if diagnosis_on else "off"
            ms.model_variant = "best"
            ms.model_evidence_weight = 0.40
            ce.diagnose.return_value = current_diag
            he.diagnose.return_value = history_diag
            hp.select_hint.return_value = None

            db_mock.get.return_value = fake_sub

            # Need to mock pipeline too
            with patch("backend.app.services.submission_service.AnalysisPipeline") as ap:
                ap.return_value.analyze_submission.return_value = []
                svc.run_and_analyze(db_mock, 7)

        return current_diag, history_diag

    def test_model_block_present_in_both_diagnoses(self):
        current, history = self._run(diagnosis_on=True, prediction_present=True)
        cur_exp = json.loads(current.explanation_json)
        his_exp = json.loads(history.explanation_json)
        assert "model" in cur_exp, "current_only explanation_json missing 'model' key"
        assert "model" in his_exp, "history_aware explanation_json missing 'model' key"

    def test_model_block_has_expected_keys(self):
        current, _ = self._run(diagnosis_on=True, prediction_present=True)
        model_block = json.loads(current.explanation_json)["model"]
        for key in ("top_label", "top_probability", "abstained"):
            assert key in model_block, f"model block missing key: {key}"

    def test_model_block_absent_when_no_prediction(self):
        current, history = self._run(diagnosis_on=False, prediction_present=False)
        cur_exp = json.loads(current.explanation_json)
        his_exp = json.loads(history.explanation_json)
        assert "model" not in cur_exp
        assert "model" not in his_exp
