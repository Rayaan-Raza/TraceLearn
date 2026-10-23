from backend.app.db.models import LearnerState, MisconceptionState, Student
from backend.app.services.submission_service import SubmissionService

def _student(db):
    return db.query(Student).filter(Student.display_name == "SYN005").first()

def test_single_failure_not_automatically_persistent(db):
    svc = SubmissionService()
    st = _student(db)
    db.query(LearnerState).filter(LearnerState.student_id == st.id).delete(); db.commit()
    sub = svc.create_submission(db, st.id, "P01", open("data/demo_sequences/code/SYN002_P01_a1.py").read())
    svc.run_and_analyze(db, sub.id)
    ls = db.query(LearnerState).filter(LearnerState.student_id == st.id, LearnerState.misconception_id == "M01_LOOP_BOUNDARY").first()
    assert ls is None or ls.state != MisconceptionState.PERSISTENT

def test_cross_problem_recurrence_can_raise_persistence(db):
    svc = SubmissionService()
    s1 = svc.create_submission(db, 1, "P01", open("data/demo_sequences/code/SYN001_P01_a1.py").read())
    svc.run_and_analyze(db, s1.id)
    s2 = svc.create_submission(db, 1, "P02", open("data/demo_sequences/code/SYN001_P02_a1.py").read())
    svc.run_and_analyze(db, s2.id)
    ls = db.query(LearnerState).filter(LearnerState.student_id == 1, LearnerState.misconception_id == "M01_LOOP_BOUNDARY").first()
    assert ls is not None
    assert ls.cross_problem_support_count >= 2
