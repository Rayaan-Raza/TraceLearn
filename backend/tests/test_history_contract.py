"""The evidence contract between the two diagnosis modes, and history ageing.

* Mode A (current-only) reads observed sources only: no `sequence`, no `history`.
* History evidence is built from earlier submissions only, carries its
  attempt age, and keeps that age when the engines read it back, so the
  documented decay `base * decay_factor ** age` applies.
"""
import json
import pytest

from backend.app.analysis.pipeline import AnalysisPipeline
from backend.app.db.models import (
    Diagnosis, DiagnosisMode, EvidenceDirection, EvidenceItem, EvidenceSourceType, LearnerState,
)
from backend.app.diagnosis.confidence import load_weights
from backend.app.diagnosis.current_only import CurrentOnlyDiagnosisEngine
from backend.app.diagnosis.evidence_contract import (
    CURRENT_ONLY_SOURCES, LONGITUDINAL_SOURCES, OBSERVED_SOURCES, records_from_items,
)
from backend.app.diagnosis.history_aware import HistoryAwareDiagnosisEngine
from backend.app.services.submission_service import SubmissionService

CODE = "data/demo_sequences/code/"
M01_BUG_P01 = CODE + "SYN001_P01_a1.py"
M01_BUG_P02 = CODE + "SYN001_P02_a1.py"
M03_BUG_P05 = CODE + "SYN004_P05_a1.py"
M03_BUG_P06 = CODE + "SYN004_P06_a1.py"
M03_OK_P05 = CODE + "SYN004_P05_a2.py"
M03_OK_P06 = CODE + "SYN004_P06_a2.py"


@pytest.fixture
def svc():
    return SubmissionService()


@pytest.fixture
def student(make_student):
    return make_student("history")


def submit(db, svc, student, problem, path):
    sub = svc.create_submission(db, student.id, problem, open(path, encoding="utf-8").read())
    svc.run_and_analyze(db, sub.id)
    return sub


def history_items(db, sub_id, code=None):
    q = db.query(EvidenceItem).filter(
        EvidenceItem.submission_id == sub_id, EvidenceItem.source_type == EvidenceSourceType.HISTORY,
    )
    if code:
        q = q.filter(EvidenceItem.evidence_code == code)
    return q.all()


def diag(db, sub_id, mode):
    return (
        db.query(Diagnosis).filter_by(submission_id=sub_id, mode=mode).order_by(Diagnosis.id.desc()).first()
    )


# --- the contract itself -------------------------------------------------

def test_contract_partitions_every_source_type():
    assert OBSERVED_SOURCES.isdisjoint(LONGITUDINAL_SOURCES)
    assert OBSERVED_SOURCES | LONGITUDINAL_SOURCES == set(EvidenceSourceType)
    assert CURRENT_ONLY_SOURCES == OBSERVED_SOURCES
    assert EvidenceSourceType.SEQUENCE not in CURRENT_ONLY_SOURCES
    assert EvidenceSourceType.HISTORY not in CURRENT_ONLY_SOURCES


def test_current_only_ignores_sequence_and_history_evidence(db, svc, student):
    # A passing first attempt has no misconception evidence of its own.
    sub = submit(db, svc, student, "P05", M03_OK_P05)
    # Plant strong M03 support under the two longitudinal sources.
    for source in (EvidenceSourceType.SEQUENCE, EvidenceSourceType.HISTORY):
        db.add(EvidenceItem(
            submission_id=sub.id, source_type=source, evidence_code="DIAGNOSTIC_RETURN_VALUE_FAIL",
            misconception_id="M03_MISSING_RETURN", direction=EvidenceDirection.SUPPORT, weight=0.35,
            description="planted", details_json="{}",
        ))
    db.commit()
    records = CurrentOnlyDiagnosisEngine()._records_from_db(db, sub.id, history_allowed=True)
    assert {r.source_type for r in records} <= {s.value for s in OBSERVED_SOURCES}
    cur = CurrentOnlyDiagnosisEngine().diagnose(db, sub)
    assert json.loads(cur.explanation_json)["scores"]["M03_MISSING_RETURN"] == 0.0
    # Mode B does see them.
    items = db.query(EvidenceItem).filter_by(submission_id=sub.id).all()
    seen = {r.source_type for r in records_from_items(items, OBSERVED_SOURCES | LONGITUDINAL_SOURCES)}
    assert {"sequence", "history"} <= seen


def test_sequence_evidence_reaches_history_aware_only(db, svc, student):
    submit(db, svc, student, "P05", M03_BUG_P05)
    s2 = submit(db, svc, student, "P05", M03_OK_P05)
    seq = db.query(EvidenceItem).filter_by(submission_id=s2.id, source_type=EvidenceSourceType.SEQUENCE).all()
    assert seq, "the second attempt on a problem must record sequence evidence"
    cur = CurrentOnlyDiagnosisEngine()._records_from_db(db, s2.id, history_allowed=False)
    assert all(r.source_type != "sequence" for r in cur)


# --- ageing --------------------------------------------------------------

def test_history_age_is_stored_and_decays_the_weight(db, svc, student):
    submit(db, svc, student, "P01", M01_BUG_P01)          # M01 observed on P01
    submit(db, svc, student, "P05", M03_OK_P05)           # two unrelated attempts in between
    submit(db, svc, student, "P06", M03_OK_P06)
    s4 = submit(db, svc, student, "P02", M01_BUG_P02)     # M01 again, three attempts later
    cfg = load_weights()
    decay = cfg["history"]["decay_factor"]
    base = cfg["weights"]["cross_problem_recurrence"]
    [rec] = history_items(db, s4.id, "CROSS_PROBLEM_RECURRENCE")
    details = json.loads(rec.details_json)
    assert details["age"] == 2 and details["problems"] == ["P01"]
    assert rec.weight == pytest.approx(base * decay ** 2)

    # The history-aware engine reads the age back: the weight it fuses is the
    # decayed one, not the undecayed base.
    ha = json.loads(diag(db, s4.id, DiagnosisMode.HISTORY_AWARE).explanation_json)
    used = [r for r in ha["supporting"] if r["evidence_code"] == "CROSS_PROBLEM_RECURRENCE"]
    assert used and used[0]["weight"] == pytest.approx(base * decay ** 2)
    assert used[0]["details"]["age"] == 2


def test_older_evidence_weighs_less_than_recent_evidence(db, svc, make_student):
    def run(gap):
        st = make_student("age")
        submit(db, svc, st, "P01", M01_BUG_P01)
        for _ in range(gap):
            submit(db, svc, st, "P05", M03_OK_P05)
        last = submit(db, svc, st, "P02", M01_BUG_P02)
        [rec] = history_items(db, last.id, "CROSS_PROBLEM_RECURRENCE")
        return rec.weight
    assert run(0) > run(3) > 0


def test_records_from_items_restores_details():
    item = EvidenceItem(
        submission_id=1, source_type=EvidenceSourceType.HISTORY, evidence_code="CROSS_PROBLEM_RECURRENCE",
        misconception_id="M01_LOOP_BOUNDARY", direction=EvidenceDirection.SUPPORT, weight=0.1,
        description="", details_json=json.dumps({"age": 4}),
    )
    [rec] = records_from_items([item], OBSERVED_SOURCES | LONGITUDINAL_SOURCES)
    assert rec.details == {"age": 4}
    assert records_from_items([item], CURRENT_ONLY_SOURCES) == []


# --- filtering -----------------------------------------------------------

def test_same_problem_repetition_is_not_cross_problem_recurrence(db, svc, student):
    submit(db, svc, student, "P05", M03_BUG_P05)
    s2 = submit(db, svc, student, "P05", M03_BUG_P05)
    assert history_items(db, s2.id, "CROSS_PROBLEM_RECURRENCE") == []


def test_history_records_are_not_counted_as_observed_support(db, svc, student):
    submit(db, svc, student, "P01", M01_BUG_P01)
    s2 = submit(db, svc, student, "P05", M03_OK_P05)
    # The passing P05 attempt carries M01 *history* evidence about P01 ...
    assert history_items(db, s2.id, "CROSS_PROBLEM_RECURRENCE")
    submit(db, svc, student, "P02", M01_BUG_P02)
    db.expire_all()
    ls = db.query(LearnerState).filter_by(student_id=student.id, misconception_id="M01_LOOP_BOUNDARY").one()
    # ... but P05 is not a problem where M01 was observed: P01 and P02 only.
    assert ls.cross_problem_support_count == 2


def test_related_success_is_per_misconception(db, svc, student):
    submit(db, svc, student, "P05", M03_BUG_P05)
    submit(db, svc, student, "P01", CODE + "SYN002_P01_a2.py")   # passes, but probes M01 only
    s3 = submit(db, svc, student, "P06", M03_BUG_P06)
    assert history_items(db, s3.id, "RELATED_SUCCESS_AFTER_MISCONCEPTION") == []
    s4 = submit(db, svc, student, "P05", M03_OK_P05)
    s5 = submit(db, svc, student, "P06", M03_BUG_P06)
    [rec] = history_items(db, s5.id, "RELATED_SUCCESS_AFTER_MISCONCEPTION")
    details = json.loads(rec.details_json)
    assert rec.misconception_id == "M03_MISSING_RETURN"
    assert details["source_submission_ids"] == [s4.id] and details["age"] == 0
    # A prior success lowers the score but is not a reason to withhold the diagnosis.
    ha = diag(db, s5.id, DiagnosisMode.HISTORY_AWARE)
    assert ha.primary_misconception == "M03_MISSING_RETURN" and not ha.requires_teacher_review


def test_reanalysing_an_older_submission_uses_no_future_attempts(db, svc, student):
    s1 = submit(db, svc, student, "P05", M03_BUG_P05)
    s2 = submit(db, svc, student, "P06", M03_BUG_P06)
    s3 = submit(db, svc, student, "P05", M03_OK_P05)
    s4 = submit(db, svc, student, "P06", M03_OK_P06)
    db.expire_all()
    live = db.query(LearnerState).filter_by(student_id=student.id, misconception_id="M03_MISSING_RETURN").one()
    assert live.state.value == "RESOLVED"

    AnalysisPipeline().analyze_submission(db, s2, include_history=True)
    hist = history_items(db, s2.id)
    for rec in hist:
        d = json.loads(rec.details_json)
        for key in ("source_submission_ids",):
            assert all(i < s2.id for i in d.get(key, []))
        for key in ("latest_submission_id", "source_submission_id"):
            if key in d:
                assert d[key] < s2.id
    codes = {r.evidence_code for r in hist}
    # The later successes s3 and s4 are invisible from s2.
    assert "RELATED_SUCCESS_AFTER_MISCONCEPTION" not in codes
    [state] = [r for r in hist if r.evidence_code == "PREVIOUS_LEARNER_STATE"]
    # The prior state comes from the stored history before s2 (NEW after s1),
    # not from the live row, which is RESOLVED after s4.
    assert json.loads(state.details_json)["state"] == "NEW"
    assert json.loads(state.details_json)["source_submission_id"] == s1.id
    assert {s3.id, s4.id}.isdisjoint({json.loads(r.details_json).get("latest_submission_id") for r in hist})
