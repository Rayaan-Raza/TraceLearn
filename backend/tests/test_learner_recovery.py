"""Learner-state recovery and recurrence, driven by real submissions.

Every test runs actual student code through `SubmissionService.run_and_analyze`
(execution, evidence, both diagnoses, learner-state update) and then reads
the stored `learner_states` row and the append-only `learner_state_history`.
No test writes a learner state by hand.

The M03 (missing return) problems P05 and P06 both have `return_value`
diagnostic tests, so a pass on either one is a related success for M03.
P01 and P02 probe M01 only.
"""
import json
import pytest

from backend.app.db.models import LearnerState, LearnerStateHistory, MisconceptionState as S
from backend.app.services.submission_service import SubmissionService

CODE = "data/demo_sequences/code/"
M03_BUG_P05 = CODE + "SYN004_P05_a1.py"
M03_BUG_P06 = CODE + "SYN004_P06_a1.py"
M03_OK_P05 = CODE + "SYN004_P05_a2.py"
M03_OK_P06 = CODE + "SYN004_P06_a2.py"
M01_REVIEW_P01 = CODE + "SYN001_P01_a1.py"
OK_P01 = CODE + "SYN002_P01_a2.py"
OK_P02 = CODE + "SYN002_P02_a1.py"
M03 = "M03_MISSING_RETURN"


@pytest.fixture
def svc():
    return SubmissionService()


@pytest.fixture
def student(make_student):
    return make_student("recovery")


def submit(db, svc, student, problem, path=None, source=None):
    code = source if source is not None else open(path, encoding="utf-8").read()
    sub = svc.create_submission(db, student.id, problem, code)
    result = svc.run_and_analyze(db, sub.id)
    return sub, result


def stored(db, student, mid=M03):
    db.expire_all()
    return db.query(LearnerState).filter_by(student_id=student.id, misconception_id=mid).one_or_none()


def transitions(db, student, mid=M03):
    db.expire_all()
    return (
        db.query(LearnerStateHistory)
        .filter_by(student_id=student.id, misconception_id=mid)
        .order_by(LearnerStateHistory.id)
        .all()
    )


def reach_improving(db, svc, student):
    submit(db, svc, student, "P05", M03_BUG_P05)
    submit(db, svc, student, "P06", M03_BUG_P06)
    ok, _ = submit(db, svc, student, "P05", M03_OK_P05)
    assert stored(db, student).state == S.IMPROVING
    return ok


def test_recovery_reaches_resolved_from_actual_submissions(db, svc, student):
    s1, _ = submit(db, svc, student, "P05", M03_BUG_P05)
    s2, _ = submit(db, svc, student, "P06", M03_BUG_P06)
    s3, r3 = submit(db, svc, student, "P05", M03_OK_P05)
    s4, r4 = submit(db, svc, student, "P06", M03_OK_P06)
    assert r3["history_aware"]["primary_misconception"] == "NO_MISCONCEPTION"
    assert r4["history_aware"]["primary_misconception"] == "NO_MISCONCEPTION"

    row = stored(db, student)
    assert row.state == S.RESOLVED
    # The successful attempt updated the existing record; it did not return early.
    assert row.trigger_submission_id == s4.id
    assert row.recent_success_count == 2
    assert row.confidence < 0.25

    hist = transitions(db, student)
    assert [(h.submission_id, h.new_state) for h in hist] == [
        (s1.id, S.NEW), (s2.id, S.PERSISTENT), (s3.id, S.IMPROVING), (s4.id, S.RESOLVED),
    ]
    reasons = [json.loads(h.reason_json)["rule"] for h in hist]
    assert reasons[2:] == ["related_success_after_persistent", "sustained_related_success"]
    assert json.loads(hist[-1].reason_json)["success_problems"] == ["P05", "P06"]
    # Confidence falls on each success.
    assert hist[1].new_confidence > hist[2].new_confidence > hist[3].new_confidence


def test_resolved_misconception_recurs_and_episode_is_kept(db, svc, student):
    reach_improving(db, svc, student)
    submit(db, svc, student, "P06", M03_OK_P06)
    assert stored(db, student).state == S.RESOLVED

    s5, r5 = submit(db, svc, student, "P05", M03_BUG_P05)
    assert r5["history_aware"]["primary_misconception"] == M03
    row = stored(db, student)
    assert row.state == S.RECURRED
    assert row.trigger_submission_id == s5.id
    hist = transitions(db, student)
    assert hist[-1].old_state == S.RESOLVED and hist[-1].new_state == S.RECURRED
    assert json.loads(hist[-1].reason_json)["rule"] == "strong_evidence_after_resolved"
    # The resolved episode stays in the append-only history.
    assert S.RESOLVED in [h.new_state for h in hist[:-1]]

    # Corrective success after a recurrence moves to IMPROVING (Appendix C).
    submit(db, svc, student, "P05", M03_OK_P05)
    assert stored(db, student).state == S.IMPROVING


def test_new_evidence_after_improving_is_a_regression(db, svc, student):
    reach_improving(db, svc, student)
    s4, _ = submit(db, svc, student, "P06", M03_BUG_P06)
    row = stored(db, student)
    assert row.state == S.PERSISTENT
    assert row.recent_success_count == 0
    last = transitions(db, student)[-1]
    assert (last.submission_id, last.old_state, last.new_state) == (s4.id, S.IMPROVING, S.PERSISTENT)
    assert json.loads(last.reason_json)["rule"] == "regression_after_improving"


def test_regression_resets_the_success_count(db, svc, student):
    reach_improving(db, svc, student)
    submit(db, svc, student, "P06", M03_BUG_P06)  # regression
    submit(db, svc, student, "P06", M03_OK_P06)   # one success since the regression
    row = stored(db, student)
    # The success before the regression no longer counts towards RESOLVED.
    assert row.state == S.IMPROVING
    assert row.recent_success_count == 1


def test_unrelated_success_does_not_change_the_state(db, svc, student):
    submit(db, svc, student, "P05", M03_BUG_P05)
    submit(db, svc, student, "P06", M03_BUG_P06)
    before = stored(db, student)
    state, conf, n = before.state, before.confidence, len(transitions(db, student))
    # P01 and P02 pass, but neither tests the return channel.
    s3, r3 = submit(db, svc, student, "P01", OK_P01)
    s4, r4 = submit(db, svc, student, "P02", OK_P02)
    assert r3["history_aware"]["primary_misconception"] == "NO_MISCONCEPTION"
    after = stored(db, student)
    assert (after.state, after.confidence) == (state, conf) == (S.PERSISTENT, conf)
    assert len(transitions(db, student)) == n


def test_same_problem_successes_do_not_resolve(db, svc, student):
    reach_improving(db, svc, student)
    submit(db, svc, student, "P05", M03_OK_P05)
    submit(db, svc, student, "P05", M03_OK_P05)
    row = stored(db, student)
    assert row.state == S.IMPROVING
    assert row.recent_success_count == 3


def test_uncertain_or_failed_attempt_does_not_resolve(db, svc, student):
    reach_improving(db, svc, student)
    n = len(transitions(db, student))
    # A syntax error is diagnosed NO_MISCONCEPTION with a review flag: it is not a success.
    _, r = submit(db, svc, student, "P06", source="def absolute_difference(a, b")
    assert r["history_aware"]["requires_teacher_review"] is True
    row = stored(db, student)
    assert row.state == S.IMPROVING
    assert len(transitions(db, student)) == n


def test_success_does_not_clear_a_teacher_review_flag(db, svc, student):
    _, r = submit(db, svc, student, "P01", M01_REVIEW_P01)
    assert r["history_aware"]["requires_teacher_review"] is True
    assert stored(db, student, "M01_LOOP_BOUNDARY").state == S.REQUIRES_TEACHER_REVIEW
    submit(db, svc, student, "P01", OK_P01)
    submit(db, svc, student, "P02", OK_P02)
    row = stored(db, student, "M01_LOOP_BOUNDARY")
    assert row.state == S.REQUIRES_TEACHER_REVIEW
    rules = [json.loads(h.reason_json)["rule"] for h in transitions(db, student, "M01_LOOP_BOUNDARY")[1:]]
    assert set(rules) == {"success_does_not_clear_review"}


def test_success_without_earlier_persistence_keeps_new(db, svc, student):
    submit(db, svc, student, "P05", M03_BUG_P05)
    submit(db, svc, student, "P05", M03_OK_P05)
    submit(db, svc, student, "P06", M03_OK_P06)
    row = stored(db, student)
    # One isolated failure followed by successes: never PERSISTENT, so not RESOLVED either.
    assert row.state == S.NEW
    assert row.confidence < 0.25


def test_rediagnosing_an_older_submission_does_not_overwrite_newer_state(db, svc, student):
    reach_improving(db, svc, student)
    s4, _ = submit(db, svc, student, "P06", M03_OK_P06)
    assert stored(db, student).state == S.RESOLVED
    old = transitions(db, student)[1].submission_id  # the attempt that made it PERSISTENT
    n = len(transitions(db, student))
    svc.diagnose(db, old)
    row = stored(db, student)
    assert row.state == S.RESOLVED and row.trigger_submission_id == s4.id
    assert len(transitions(db, student)) == n
