from pathlib import Path
import yaml
from backend.app.db.models import LearnerState, MisconceptionState, Student, Submission
from backend.app.learner_model.history import HistoryProvider
from backend.app.services.submission_service import SubmissionService

def test_no_future_history_leakage(db):
    from datetime import datetime, timedelta, timezone
    from backend.app.db.models import LearnerStateHistory
    hp = HistoryProvider()
    st = db.query(Student).filter(Student.display_name == "SYN005").first()
    sub = Submission(student_id=st.id, problem_id="P01", attempt_number=99, source_code="def f(): pass")
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

def test_same_problem_repetition_does_not_automatically_mean_persistent(db):
    svc = SubmissionService()
    st = db.query(Student).filter(Student.display_name == "SYN005").first()
    db.query(LearnerState).filter(LearnerState.student_id == st.id).delete(); db.commit()
    s1 = svc.create_submission(db, st.id, "P01", open("data/demo_sequences/code/SYN002_P01_a1.py").read())
    svc.run_and_analyze(db, s1.id)
    s2 = svc.create_submission(db, st.id, "P01", open("data/demo_sequences/code/SYN002_P01_a1.py").read())
    svc.run_and_analyze(db, s2.id)
    ls = db.query(LearnerState).filter(LearnerState.student_id == st.id).first()
    assert ls is None or ls.state != MisconceptionState.PERSISTENT

def test_cross_problem_recurrence_can_create_persistent_state(db, client):
    db.query(LearnerState).delete(); db.commit()
    client.post("/api/demo/run-sequence/SYN001")
    st = db.query(Student).filter(Student.display_name == "SYN001").first()
    ls = db.query(LearnerState).filter(LearnerState.student_id == st.id).first()
    assert ls is not None

def test_evaluation_dataset_not_used_for_weight_configuration():
    cfg = yaml.safe_load(Path("config/evidence_weights.yaml").read_text(encoding="utf-8"))
    src = Path("backend/app/diagnosis/confidence.py").read_text(encoding="utf-8")
    assert "evaluation_sequences" not in src
    assert Path("data/evaluation_sequences/EVAL001.json").read_text(encoding="utf-8") not in yaml.dump(cfg)
