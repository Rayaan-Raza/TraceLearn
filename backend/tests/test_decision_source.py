"""Every prediction says which stage decided it, and no rule claims certainty (Gate 2, task R3).

Supervisor action plan, 15 Nov 2026: "repair-first selection sets confidence to 1.0 while retaining
the classifier's old probability vector ... Represent the decision source honestly."
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.analysis import model_runner
from backend.app.config import settings
from backend.app.diagnosis.xgb_classifier import (
    DECISION_SOURCES,
    RULE_STAGE_PRECISION,
    ModelPrediction,
    decided_by_rule,
    rule_confidence,
    wilson_lower,
)

REPO = Path(__file__).resolve().parents[2]
SOURCE = "int main() { return 0; }\n"


def _classifier_pred(**kw) -> ModelPrediction:
    """What the classifier says: OFF_BY_ONE at 0.41, then LOOP_BOUNDARY at 0.12."""
    base = dict(
        variant="execution", model_sha256="0" * 64, top_label="CPP_OFF_BY_ONE",
        top_probability=0.41, abstained=True, threshold=0.44, temperature=1.4,
        probabilities={"CPP_OFF_BY_ONE": 0.41, "CPP_OTHER_ERROR": 0.30, "CPP_LOOP_BOUNDARY": 0.12},
        top_k=(("CPP_OFF_BY_ONE", 0.41), ("CPP_OTHER_ERROR", 0.30), ("CPP_LOOP_BOUNDARY", 0.12)),
        n_features=100, n_missing=0,
    )
    base.update(kw)
    return ModelPrediction(**base)


class _FakeClassifier:
    def __init__(self, pred: ModelPrediction):
        self.pred = pred

    def predict(self, features):
        return self.pred


@pytest.fixture
def runner(monkeypatch):
    """predict_source with a fixed feature mapping and a fixed classifier answer."""
    def use(features: dict, pred: ModelPrediction):
        monkeypatch.setattr(model_runner, "code_features", lambda *a, **k: features)
        monkeypatch.setattr(model_runner, "_classifier", lambda *a: _FakeClassifier(pred))
    return use


# ----------------------------------------------------------------- confidence of a rule

def test_wilson_lower_bound_known_values():
    assert wilson_lower(102, 115) == pytest.approx(0.817, abs=0.002)
    assert wilson_lower(2, 2) < 0.5          # two of two is not certainty
    assert wilson_lower(0, 0) == 0.0


@pytest.mark.parametrize("source", sorted(RULE_STAGE_PRECISION))
def test_no_rule_stage_reports_certainty(source):
    assert 0 < rule_confidence(source) < 1.0


def test_every_rule_source_has_a_measured_precision():
    assert set(DECISION_SOURCES) - {"model"} == set(RULE_STAGE_PRECISION)


def test_unknown_decision_source_is_refused():
    with pytest.raises(ValueError):
        _classifier_pred(decision_source="guess")
    with pytest.raises(ValueError):
        decided_by_rule(_classifier_pred(), "CPP_LOOP_BOUNDARY", "model")


# ----------------------------------------------------------------- the two stages

def test_classifier_stage_keeps_its_own_answer(runner):
    pred = _classifier_pred(abstained=False, top_probability=0.81,
                            top_k=(("CPP_OFF_BY_ONE", 0.81), ("CPP_OTHER_ERROR", 0.1)))
    runner({}, pred)
    out = model_runner.predict_source(SOURCE)
    assert out.decision_source == "model"
    assert (out.top_label, out.top_probability, out.abstained) == ("CPP_OFF_BY_ONE", 0.81, False)
    assert (out.classifier_label, out.classifier_probability) == out.top_k[0]


def test_repair_stage_reports_its_precision_and_keeps_the_classifier_answer(runner):
    runner({"repair.loop_boundary_fix_all": 1.0}, _classifier_pred())
    out = model_runner.predict_source(SOURCE)
    assert out.decision_source == "repair"
    assert out.top_label == "CPP_LOOP_BOUNDARY"
    assert out.top_probability == rule_confidence("repair") < 1.0
    assert out.abstained is False
    # The classifier's view is still there, and still says what the classifier said.
    assert (out.classifier_label, out.classifier_probability) == out.top_k[0] == ("CPP_OFF_BY_ONE", 0.41)
    assert out.classifier_abstained is True
    assert out.probabilities["CPP_LOOP_BOUNDARY"] == 0.12


def test_stored_details_carry_the_decision_source(runner):
    runner({"repair.loop_boundary_fix_all": 1.0}, _classifier_pred())
    d = model_runner.predict_source(SOURCE).as_dict()
    assert d["decision_source"] == "repair"
    assert d["classifier_label"] == "CPP_OFF_BY_ONE"
    assert d["top_probability"] < 1.0


# ----------------------------------------------------------------- missing features

def test_missing_features_make_the_classifier_abstain(monkeypatch, runner):
    monkeypatch.setattr(settings, "model_diagnosis", "on")
    monkeypatch.setattr(model_runner, "compiler_warnings", lambda source: {})
    runner({}, _classifier_pred(abstained=False, top_probability=0.9, n_missing=60))
    assert model_runner.model_records(SOURCE)[0].evidence_code == "MODEL_ABSTAINED"


def test_missing_features_do_not_cancel_a_repair_decision(monkeypatch, runner):
    """A repair that passes every test is its own evidence; the classifier's gaps do not undo it."""
    monkeypatch.setattr(settings, "model_diagnosis", "on")
    monkeypatch.setattr(model_runner, "compiler_warnings", lambda source: {})
    runner({"repair.loop_boundary_fix_all": 1.0}, _classifier_pred(n_missing=60))
    rec = model_runner.model_records(SOURCE)[0]
    assert rec.evidence_code == "MODEL_PREDICTION"
    assert rec.details["decision_source"] == "repair"


# ----------------------------------------------------------------- no certainty in the code

def test_no_hard_coded_certainty_left_in_the_backend():
    hits = [str(p.relative_to(REPO)) for p in (REPO / "backend" / "app").rglob("*.py")
            if "top_probability=1.0" in p.read_text(encoding="utf-8")]
    assert hits == []
