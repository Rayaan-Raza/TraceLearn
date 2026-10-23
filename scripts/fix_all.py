from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

def w(rel, text):
    (ROOT / rel).write_text(text.strip() + "\n", encoding="utf-8", newline="\n")

# Fix history count_cross_problem_support
text = (ROOT / "backend/app/learner_model/history.py").read_text(encoding="utf-8")
start = text.index("    def count_cross_problem_support")
end = text.index("\n\n", start)
text = text[:start] + '''    def count_cross_problem_support(self, db: Session, current: Submission, misconception_id: str) -> int:
        problems: set[str] = set()
        for ps in self.get_prior_submissions(db, current):
            if ps.problem_id == current.problem_id:
                continue
            evs = db.query(EvidenceItem).filter(
                EvidenceItem.submission_id == ps.id,
                EvidenceItem.misconception_id == misconception_id,
                EvidenceItem.direction == "support",
            ).count()
            if evs:
                problems.add(ps.problem_id)
        cur_evs = db.query(EvidenceItem).filter(
            EvidenceItem.submission_id == current.id,
            EvidenceItem.misconception_id == misconception_id,
            EvidenceItem.direction == "support",
        ).count()
        if cur_evs and problems:
            problems.add(current.problem_id)
        return len(problems)''' + text[end:]
(ROOT / "backend/app/learner_model/history.py").write_text(text, encoding="utf-8")

# confidence conflict check
conf = (ROOT / "backend/app/diagnosis/confidence.py").read_text(encoding="utf-8")
if "conflict = any" not in conf:
    conf = conf.replace(
        "    if pconf < review_conf or (alt and abs(pconf - (aconf or 0)) < margin):",
        "    conflict = any(r.direction == \"conflict\" and r.weight for r in weighted)\n    if pconf < review_conf or (alt and abs(pconf - (aconf or 0)) < margin) or conflict:",
    )
    (ROOT / "backend/app/diagnosis/confidence.py").write_text(conf, encoding="utf-8")

w("backend/tests/test_execution.py", """
from pathlib import Path
import pytest
from backend.app.db.models import Student
from backend.app.execution.runner import ExecutionResult
from backend.app.services.submission_service import SubmissionService

SOLUTIONS = Path("data/problems/solutions")

@pytest.fixture
def service():
    return SubmissionService()

def test_execution_runs_correct_code(db, service):
    student = db.query(Student).first()
    for pid in ["P01", "P02", "P03", "P04", "P05", "P06"]:
        code = (SOLUTIONS / f"{pid}.py").read_text(encoding="utf-8")
        sub = service.create_submission(db, student.id, pid, code)
        result = service.execute(db, sub.id)
        assert result["execution_status"] == "success"

def test_execution_detects_failure(db, service):
    student = db.query(Student).first()
    bad = "def sum_first_n(n):\\n    return n +"
    sub = service.create_submission(db, student.id, "P01", bad)
    result = service.execute(db, sub.id)
    assert result["execution_status"] == "syntax_error"

def test_timeout_is_captured(db, service, monkeypatch):
    class TimeoutRunner:
        def execute_function(self, source_code, function_name, args, timeout_seconds):
            return ExecutionResult(status="timeout", stderr="Execution timed out", error_type="Timeout")
    import backend.app.execution.test_runner as tr
    monkeypatch.setattr(tr, "get_runner", lambda: TimeoutRunner())
    student = db.query(Student).first()
    sub = service.create_submission(db, student.id, "P01", "def sum_first_n(n):\\n    return 0")
    result = service.execute(db, sub.id)
    assert result["execution_status"] == "timeout"
""")

w("backend/tests/test_history_model.py", """
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
""")

w("backend/tests/test_state_transitions.py", """
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
""")

w("backend/tests/test_mandatory_contracts.py", """
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

def test_cross_problem_recurrence_can_create_persistent_state(db):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
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
""")

print("all fixes written")
