"""The hint a real submission receives follows the model prediction stored for it (task E2).

`test_hint_model_band.py` hands `select_hint` a prediction itself, so it passes while
`SubmissionService.diagnose` never supplies one. These tests go through `diagnose`, with the model
settings the product ships with, and read the stored `HintEvent` back from the database.

Fast cases store the model's evidence record by hand. The slow case sends a failing C++ program
through `run_and_analyze` with the background worker on and checks the hint against whatever the
model stored.
"""
from __future__ import annotations

import json
import platform
import shutil
import uuid

import pytest

from backend.app.analysis import async_diagnosis
from backend.app.config import settings
from backend.app.db.models import (
    EvidenceDirection, EvidenceItem, EvidenceSourceType, ExecutionStatus, HintEvent, Student, Submission,
)
from backend.app.db.models import TestResult as TestResultModel
from backend.app.diagnosis.xgb_classifier import ModelPrediction
from backend.app.services.submission_service import SubmissionService
from backend.tests.test_cpp_end_to_end import EXAMPLE_PROBLEM, _problem, _remove_cpp_problem, _seed_cpp_problem

# CP09's diagnostic tests fail on its misconception variant, so the rules diagnose this class.
DIAGNOSED = "CPP_LOOP_BOUNDARY"
OTHER_CLASS = "CPP_OFF_BY_ONE"


@pytest.fixture(autouse=True)
def _shipped_model_settings(monkeypatch):
    """Override the suite's rule-engine default: the model on, as shipped."""
    monkeypatch.setattr(settings, "model_diagnosis", "on")
    monkeypatch.setattr(settings, "model_variant", "execution")
    monkeypatch.setattr(settings, "model_run_records", "on")
    monkeypatch.setattr(settings, "model_fusion", "model_first")
    monkeypatch.setattr(settings, "model_async", False)


@pytest.fixture
def cpp_submission(db):
    """A failing C++ submission on CP09 with the rule evidence already analysed (model off for that step)."""
    problem = _problem(EXAMPLE_PROBLEM)
    student = Student(display_name=f"hint-int-{uuid.uuid4().hex[:6]}")
    db.add(student)
    db.commit()
    db.refresh(student)
    inserted = _seed_cpp_problem(db, problem)
    sub = Submission(student_id=student.id, problem_id=problem["id"],
                     source_code=problem["misconception_variant_source"],
                     execution_status=ExecutionStatus.RUNTIME_ERROR, stderr="")
    db.add(sub)
    db.commit()
    db.refresh(sub)
    for case in problem["test_cases"]:
        db.add(TestResultModel(
            submission_id=sub.id, test_case_id=case["id"], passed=case["db_type"] != "diagnostic",
            actual_output_json="null", expected_output_json=json.dumps(case["expected_output"])))
    db.commit()
    rules_only = settings.model_diagnosis
    settings.model_diagnosis = "off"
    try:
        SubmissionService().analyze(db, sub.id)
    finally:
        settings.model_diagnosis = rules_only
    try:
        yield sub
    finally:
        _remove_cpp_problem(db, problem["id"], student.id, drop_problem=inserted)


def _prediction(label: str, probability: float, *, abstained: bool = False, source: str | None = None) -> dict:
    details = ModelPrediction(
        variant="execution", model_sha256="0" * 64, top_label=label, top_probability=probability,
        abstained=abstained, threshold=0.44, temperature=1.4,
        probabilities={label: probability, "CPP_OTHER_ERROR": round(1 - probability, 3)},
        top_k=((label, probability), ("CPP_OTHER_ERROR", round(1 - probability, 3))),
        n_features=100, n_missing=0,
    ).as_dict()
    if source:
        details["decision_source"] = source
    return details


def _store(db, sub, code: str, details: dict, misconception_id: str | None = None) -> None:
    """One model evidence record, as `model_evidence` writes it. Weight is small so the rules still diagnose."""
    named = code == "MODEL_PREDICTION"
    db.add(EvidenceItem(
        submission_id=sub.id, source_type=EvidenceSourceType.MODEL, evidence_code=code,
        misconception_id=misconception_id if named else None,
        direction=EvidenceDirection.SUPPORT if named else EvidenceDirection.NEUTRAL,
        weight=0.05 if named else 0.0, description="stored by the test", details_json=json.dumps(details)))
    db.commit()


def _diagnose_and_read_hint(db, sub, diagnosed: str = DIAGNOSED) -> HintEvent:
    """Run the real `diagnose`, then read what it stored. Asserting on the row, not the return value."""
    result = SubmissionService().diagnose(db, sub.id)
    assert result["history_aware"]["primary_misconception"] == diagnosed, result["history_aware"]
    db.expire_all()
    events = db.query(HintEvent).filter(HintEvent.submission_id == sub.id).order_by(HintEvent.id).all()
    assert len(events) == 1, "diagnose must store exactly one hint event"
    assert events[0].misconception_id == ("GENERIC" if diagnosed == "UNCERTAIN" else diagnosed)
    return events[0]


# ----------------------------------------------------------------- the six cases of the plan

def test_confident_prediction_that_matches_the_diagnosis_starts_at_level_2(db, cpp_submission):
    _store(db, cpp_submission, "MODEL_PREDICTION", _prediction(DIAGNOSED, 0.82), DIAGNOSED)
    assert _diagnose_and_read_hint(db, cpp_submission).hint_level == 2


def test_abstained_prediction_starts_at_level_1(db, cpp_submission):
    _store(db, cpp_submission, "MODEL_ABSTAINED", _prediction(DIAGNOSED, 0.41, abstained=True))
    assert _diagnose_and_read_hint(db, cpp_submission).hint_level == 1


def test_confident_other_error_gets_the_generic_hint_at_level_1(db, cpp_submission):
    """With model_first fusion a confident OTHER_ERROR makes the diagnosis UNCERTAIN, so the hint is the generic one."""
    _store(db, cpp_submission, "MODEL_OTHER_ERROR", _prediction("CPP_OTHER_ERROR", 0.93))
    assert _diagnose_and_read_hint(db, cpp_submission, diagnosed="UNCERTAIN").hint_level == 1


def test_confident_prediction_of_a_different_class_starts_at_level_1(db, cpp_submission, monkeypatch):
    """Under model_first the diagnosis follows a confident model, so a mismatch only arises when the rules decide.

    `points` fusion keeps the rules' class (the prediction is one weak piece of evidence), which is
    the case the guard in `select_hint` exists for.
    """
    monkeypatch.setattr(settings, "model_fusion", "points")
    _store(db, cpp_submission, "MODEL_PREDICTION", _prediction(OTHER_CLASS, 0.93), OTHER_CLASS)
    assert _diagnose_and_read_hint(db, cpp_submission).hint_level == 1


def test_under_model_first_a_confident_prediction_of_another_class_also_moves_the_diagnosis(db, cpp_submission):
    """The hint stays consistent with the diagnosis: both follow the model, so the shortcut applies to that class."""
    _store(db, cpp_submission, "MODEL_PREDICTION", _prediction(OTHER_CLASS, 0.93), OTHER_CLASS)
    assert _diagnose_and_read_hint(db, cpp_submission, diagnosed=OTHER_CLASS).hint_level == 2


def test_shadow_record_never_changes_the_hint(db, cpp_submission):
    _store(db, cpp_submission, "MODEL_SHADOW", _prediction(DIAGNOSED, 0.95))
    assert _diagnose_and_read_hint(db, cpp_submission).hint_level == 1


@pytest.mark.parametrize("precision, level", [(0.817, 2), (0.60, 1)])
def test_repair_decision_follows_its_measured_precision_not_certainty(db, cpp_submission, precision, level):
    """A repair decision reports the measured precision of the repair-first rule (102/115, lower 95% bound 0.817)."""
    _store(db, cpp_submission, "MODEL_PREDICTION", _prediction(DIAGNOSED, precision, source="repair"), DIAGNOSED)
    assert _diagnose_and_read_hint(db, cpp_submission).hint_level == level


# ----------------------------------------------------------------- the real path, with the worker

needs_toolchain = pytest.mark.skipif(
    shutil.which("g++") is None or shutil.which("bwrap") is None or platform.system() != "Linux",
    reason="needs g++ and bubblewrap on Linux (CI has both)")


@pytest.mark.slow
@needs_toolchain
def test_real_failing_program_through_the_worker_gets_the_hint_its_stored_prediction_allows(db, cpp_submission, monkeypatch):
    monkeypatch.setattr(settings, "model_async", True)
    out = SubmissionService().run_and_analyze(db, cpp_submission.id)
    assert out["diagnosis_pending"] is True
    async_diagnosis.wait_idle()
    db.expire_all()

    record = (db.query(EvidenceItem)
              .filter(EvidenceItem.submission_id == cpp_submission.id,
                      EvidenceItem.source_type == EvidenceSourceType.MODEL,
                      EvidenceItem.evidence_code == "MODEL_PREDICTION")
              .order_by(EvidenceItem.id.desc()).first())
    event = (db.query(HintEvent).filter(HintEvent.submission_id == cpp_submission.id)
             .order_by(HintEvent.id.desc()).first())
    assert event is not None, "the worker must store a hint"

    # The policy, restated from the stored rows only: level 2 when the stored prediction names the
    # hint's own misconception at 0.75 or more, level 1 otherwise.
    expected = 1
    if record is not None:
        stored = json.loads(record.details_json)
        if (not stored["abstained"] and stored["top_probability"] >= 0.75
                and record.misconception_id == event.misconception_id):
            expected = 2
    assert event.hint_level == expected, (event.hint_level, record and record.details_json)
