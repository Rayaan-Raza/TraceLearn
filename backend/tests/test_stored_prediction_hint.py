"""The stored model prediction reaches hint selection (Gate 2, task R4).

Supervisor action plan, 15 Nov 2026: "A real stored prediction reaches hint selection; selected
hint agrees with the actual policy." Before this, `SubmissionService.diagnose` called
`select_hint` without a prediction, so the confidence band never applied to a real submission.
The end-to-end check with the model on is Eman's integration test (task E2).
"""
from __future__ import annotations

import json

import pytest

from backend.app.analysis.model_evidence import stored_model_prediction
from backend.app.db.models import EvidenceDirection, EvidenceItem, EvidenceSourceType
from backend.app.diagnosis.xgb_classifier import ModelPrediction, decided_by_rule
from backend.app.services.submission_service import SubmissionService

CODE = "#include <iostream>\nint main() { std::cout << 1; }\n"


def _pred(**kw) -> ModelPrediction:
    base = dict(
        variant="execution", model_sha256="0" * 64, top_label="CPP_LOOP_BOUNDARY",
        top_probability=0.8, abstained=False, threshold=0.44, temperature=1.4,
        probabilities={"CPP_LOOP_BOUNDARY": 0.8, "CPP_OTHER_ERROR": 0.2},
        top_k=(("CPP_LOOP_BOUNDARY", 0.8), ("CPP_OTHER_ERROR", 0.2)),
        n_features=100, n_missing=3, ruled_out=(("CPP_INT_OVERFLOW", "no wide arithmetic"),),
    )
    base.update(kw)
    return ModelPrediction(**base)


@pytest.fixture
def sub(db, make_student):
    svc = SubmissionService()
    return svc.create_submission(db, make_student("hintpath").id, "P05", CODE)


def _store(db, sub, code: str, details: dict | str) -> None:
    named = code == "MODEL_PREDICTION"   # as `model_evidence` writes it: support for one misconception
    db.add(EvidenceItem(
        submission_id=sub.id, source_type=EvidenceSourceType.MODEL, evidence_code=code,
        misconception_id="CPP_LOOP_BOUNDARY" if named else None,
        direction=EvidenceDirection.SUPPORT if named else EvidenceDirection.NEUTRAL,
        weight=0.32 if named else 0.0, description="test",
        details_json=details if isinstance(details, str) else json.dumps(details),
    ))
    db.commit()


# ----------------------------------------------------------------- round trip

def test_as_dict_round_trips():
    for p in (_pred(), decided_by_rule(_pred(top_label="CPP_OFF_BY_ONE", abstained=True),
                                       "CPP_LOOP_BOUNDARY", "repair")):
        assert ModelPrediction.from_dict(p.as_dict()) == p


def test_a_record_from_before_decision_source_reads_as_a_classifier_decision():
    d = _pred().as_dict()
    for key in ("decision_source", "classifier_label", "classifier_probability", "classifier_abstained"):
        d.pop(key)
    back = ModelPrediction.from_dict(d)
    assert back.decision_source == "model"
    assert back.classifier_label == "CPP_LOOP_BOUNDARY"


# ----------------------------------------------------------------- reading what was stored

def test_no_model_record_means_no_prediction(db, sub):
    assert stored_model_prediction(db, sub.id) is None


@pytest.mark.parametrize("code", ["MODEL_SHADOW", "MODEL_ABSTAINED", "MODEL_OTHER_ERROR"])
def test_records_that_name_no_misconception_are_ignored(db, sub, code):
    _store(db, sub, code, _pred().as_dict())
    assert stored_model_prediction(db, sub.id) is None


def test_the_named_prediction_is_read_back(db, sub):
    _store(db, sub, "MODEL_SHADOW", _pred(top_label="CPP_OFF_BY_ONE").as_dict())
    _store(db, sub, "MODEL_PREDICTION", _pred().as_dict())
    got = stored_model_prediction(db, sub.id)
    assert got == _pred()


def test_an_unreadable_record_is_ignored(db, sub):
    _store(db, sub, "MODEL_PREDICTION", "{not json")
    assert stored_model_prediction(db, sub.id) is None
    _store(db, sub, "MODEL_PREDICTION", {"top_label": "CPP_LOOP_BOUNDARY"})   # fields missing
    assert stored_model_prediction(db, sub.id) is None


# ----------------------------------------------------------------- the service passes it on

def test_diagnose_hands_the_stored_prediction_to_hint_selection(db, sub, monkeypatch):
    _store(db, sub, "MODEL_PREDICTION", _pred().as_dict())
    svc = SubmissionService()
    seen = {}

    def spy(db_, sub_, diagnosis, model_prediction=None):
        seen["prediction"] = model_prediction
        return None

    monkeypatch.setattr(svc.hint_policy, "select_hint", spy)
    svc.diagnose(db, sub.id)
    assert seen["prediction"] == _pred()


def test_diagnose_without_a_model_record_passes_none(db, sub, monkeypatch):
    svc = SubmissionService()
    seen = {}
    monkeypatch.setattr(svc.hint_policy, "select_hint",
                        lambda d, s, diag, model_prediction=None: seen.setdefault("p", model_prediction))
    svc.diagnose(db, sub.id)
    assert seen["p"] is None
