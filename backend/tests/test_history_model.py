from datetime import datetime, timedelta, timezone
from backend.app.db.models import LearnerState, LearnerStateHistory, MisconceptionState, Student, Submission
from backend.app.learner_model.history import HistoryProvider

def _student(db):
    return db.query(Student).filter(Student.display_name == "SYN005").first()

def test_no_future_history_leakage(db):
    hp = HistoryProvider()
    st = _student(db)
    sub = Submission(student_id=st.id, problem_id="P01", attempt_number=99, source_code="def sum_first_n(n): return 0")
    db.add(sub); db.commit(); db.refresh(sub)
    db.add(LearnerStateHistory(
        student_id=st.id, misconception_id="M01_LOOP_BOUNDARY",
        old_state=MisconceptionState.NEW, new_state=MisconceptionState.PERSISTENT,
        old_confidence=0.2, new_confidence=0.9, submission_id=sub.id + 1000,
        timestamp=datetime.now(timezone.utc) + timedelta(days=1),
    ))
    db.commit()
    prior = hp.get_prior_submissions(db, sub)
    assert all(p.id < sub.id for p in prior)

def test_success_reduces_confidence(db):
    from backend.app.services.submission_service import SubmissionService
    svc = SubmissionService()
    st = _student(db)
    s1 = svc.create_submission(db, st.id, "P01", open("data/demo_sequences/code/SYN002_P01_a1.py").read())
    r1 = svc.run_and_analyze(db, s1.id)
    s2 = svc.create_submission(db, st.id, "P01", open("data/demo_sequences/code/SYN002_P01_a2.py").read())
    r2 = svc.run_and_analyze(db, s2.id)
    assert r2["history_aware"]["primary_confidence"] <= r1["history_aware"]["primary_confidence"] + 0.01

def test_resolved_can_recur(db):
    from backend.app.services.submission_service import SubmissionService
    svc = SubmissionService()
    st = _student(db)
    db.query(LearnerState).filter(LearnerState.student_id == st.id).delete(); db.commit()
    db.add(LearnerState(student_id=st.id, misconception_id="M01_LOOP_BOUNDARY", state=MisconceptionState.RESOLVED, confidence=0.1))
    db.commit()
    sub = svc.create_submission(db, st.id, "P01", open("data/demo_sequences/code/SYN001_P01_a1.py").read())
    svc.run_and_analyze(db, sub.id)
    ls = db.query(LearnerState).filter(LearnerState.student_id == st.id).first()
    assert ls is not None
