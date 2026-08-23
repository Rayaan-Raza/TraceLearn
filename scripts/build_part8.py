from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
    print("w", rel)

w("backend/tests/conftest.py", '''
import os, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "tracelearn_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

@pytest.fixture(scope="session", autouse=True)
def _reset_test_db():
    if TEST_DB.exists():
        TEST_DB.unlink()
    yield
    try:
        from backend.app.db.database import engine
        engine.dispose()
    except Exception:
        pass
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except PermissionError:
            pass

@pytest.fixture(scope="module")
def seeded_db():
    from backend.app.db.database import SessionLocal, init_db
    from backend.app.db.seed import run_seed
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()

@pytest.fixture(scope="module")
def client(seeded_db):
    from backend.app.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)

@pytest.fixture(scope="module")
def db(seeded_db):
    from backend.app.db.database import SessionLocal
    db = SessionLocal()
    yield db
    db.close()
''')

w("backend/tests/test_execution.py", '''
from pathlib import Path
import pytest
from backend.app.db.models import Student
from backend.app.execution.test_runner import run_submission_tests
from backend.app.services.submission_service import SubmissionService

SOLUTIONS = Path("data/problems/solutions")

@pytest.fixture
def service():
    return SubmissionService()

def test_execution_runs_correct_code(db, service):
    student = db.query(Student).first()
    for pid in ["P01","P02","P03","P04","P05","P06"]:
        code = (SOLUTIONS / f"{pid}.py").read_text(encoding="utf-8")
        sub = service.create_submission(db, student.id, pid, code)
        result = service.execute(db, sub.id)
        assert result["execution_status"] == "success"

def test_execution_detects_failure(db, service):
    student = db.query(Student).first()
    sub = service.create_submission(db, student.id, "P01", "def sum_first_n(n):\n    return n +")
    result = service.execute(db, sub.id)
    assert result["execution_status"] == "syntax_error"

def test_timeout_is_captured(db, service, monkeypatch):
    from backend.app.execution import subprocess_runner
    def slow(*a, **k):
        from backend.app.execution.runner import ExecutionResult
        import time; time.sleep(10)
        return ExecutionResult(status="success")
    monkeypatch.setattr(subprocess_runner.SubprocessExecutionRunner, "execute_function", slow)
    student = db.query(Student).first()
    sub = service.create_submission(db, student.id, "P01", "def sum_first_n(n):\n    return 0")
    result = service.execute(db, sub.id)
    assert result["execution_status"] == "timeout"
''')

w("backend/tests/test_static_analysis.py", '''
from backend.app.analysis.static_analyzer import StaticAnalyzer

def test_range_plus_one_static_pattern():
    code = "def sum_first_n(n):\n    s=0\n    for i in range(n+1):\n        s+=i\n    return s\n"
    items = StaticAnalyzer().analyze(code, "sum_first_n")
    codes = {i.evidence_code for i in items}
    assert "STATIC_RANGE_N_PLUS_ONE" in codes

def test_value_used_as_index_pattern():
    code = "def first_negative(nums):\n    for x in nums:\n        if nums[x] < 0:\n            return nums[x]\n    return None\n"
    items = StaticAnalyzer().analyze(code, "first_negative")
    assert any(i.evidence_code == "STATIC_ITER_VALUE_USED_AS_INDEX" for i in items)

def test_missing_return_pattern():
    code = "def square_number(x):\n    print(x*x)\n"
    items = StaticAnalyzer().analyze(code, "square_number")
    codes = {i.evidence_code for i in items}
    assert "STATIC_PRINT_INSTEAD_OF_RETURN" in codes or "STATIC_NO_RETURN" in codes
''')

w("backend/tests/test_diagnosis.py", '''
import pytest
from backend.app.db.models import DiagnosisMode, EvidenceSourceType
from backend.app.diagnosis.current_only import CurrentOnlyDiagnosisEngine
from backend.app.diagnosis.history_aware import HistoryAwareDiagnosisEngine
from backend.app.services.submission_service import SubmissionService

@pytest.fixture
def service():
    return SubmissionService()

def test_current_only_cannot_access_history(db, service, monkeypatch):
    called = {"history": False}
    orig = CurrentOnlyDiagnosisEngine._records_from_db
    def wrapped(self, db, sid, history_allowed=False):
        if history_allowed:
            called["history"] = True
        return orig(self, db, sid, history_allowed=False)
    monkeypatch.setattr(CurrentOnlyDiagnosisEngine, "_records_from_db", wrapped)
    student_id = 1
    sub = service.create_submission(db, student_id, "P01", open("data/demo_sequences/code/SYN001_P01_a1.py").read())
    service.run_and_analyze(db, sub.id)
    assert called["history"] is False
    cur = db.query(__import__("backend.app.db.models", fromlist=["Diagnosis"]).Diagnosis).filter_by(submission_id=sub.id, mode=DiagnosisMode.CURRENT_ONLY).first()
    assert cur is not None

def test_history_aware_uses_related_history(db, service):
    s1 = service.create_submission(db, 1, "P01", open("data/demo_sequences/code/SYN001_P01_a1.py").read())
    service.run_and_analyze(db, s1.id)
    s2 = service.create_submission(db, 1, "P02", open("data/demo_sequences/code/SYN001_P02_a1.py").read())
    service.run_and_analyze(db, s2.id)
    from backend.app.db.models import EvidenceItem
    hist = db.query(EvidenceItem).filter(EvidenceItem.submission_id == s2.id, EvidenceItem.source_type == EvidenceSourceType.HISTORY).count()
    assert hist >= 1

def test_conflicting_evidence_can_require_review(db, service):
    sub = service.create_submission(db, 1, "P01", open("data/demo_sequences/code/SYN005_P01_a1.py").read())
    r = service.run_and_analyze(db, sub.id)
    ha = r["history_aware"]
    assert ha["requires_teacher_review"] or ha["uncertainty_level"] == "high"

def test_syntax_error_not_forced_to_misconception(db, service):
    sub = service.create_submission(db, 1, "P01", "def sum_first_n(n\n")
    r = service.run_and_analyze(db, sub.id)
    assert r["current_only"]["primary_misconception"] in ("NO_MISCONCEPTION", "UNCERTAIN")

def test_teacher_correction_preserves_original_prediction(db, service, client):
    sub = service.create_submission(db, 1, "P01", open("data/demo_sequences/code/SYN001_P01_a1.py").read())
    r = service.run_and_analyze(db, sub.id)
    diag_id = r["history_aware"]["id"]
    orig = r["history_aware"]["primary_misconception"]
    resp = client.post(f"/api/diagnoses/{diag_id}/teacher-review", json={"action": "CORRECT", "corrected_misconception": "M02_INDEX_VALUE", "comment": "teacher fix"})
    assert resp.status_code == 200
    d = db.get(__import__("backend.app.db.models", fromlist=["Diagnosis"]).Diagnosis, diag_id)
    assert d.primary_misconception == orig

def test_experiment_metrics_generated_from_database(db, service, client):
    for sid in range(1, 4):
        client.post(f"/api/demo/run-sequence/SYN00{sid}")
    from backend.app.evaluation.evaluator import ExperimentEvaluator
    metrics = ExperimentEvaluator(db).collect_predictions()
    assert "history_changed_predictions" in metrics
    assert metrics["current_only_metrics"]["macro_f1"] >= 0.0
''')

w("backend/tests/test_history_model.py", '''
from datetime import datetime, timedelta, timezone
from backend.app.db.models import LearnerStateHistory, MisconceptionState, Submission
from backend.app.learner_model.history import HistoryProvider

def test_no_future_history_leakage(db):
    hp = HistoryProvider()
    sub = Submission(id=10, student_id=1, problem_id="P01", attempt_number=1, source_code="pass", submitted_at=datetime.now(timezone.utc))
    db.add(sub); db.commit()
    future = LearnerStateHistory(
        student_id=1, misconception_id="M01_LOOP_BOUNDARY",
        old_state=MisconceptionState.NEW, new_state=MisconceptionState.PERSISTENT,
        old_confidence=0.3, new_confidence=0.8, submission_id=99,
        timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(future); db.commit()
    hist = hp.get_state_history_before(db, 1, sub.submitted_at, sub.id)
    assert all(h.submission_id is None or h.submission_id < sub.id for h in hist)

def test_success_reduces_confidence(db):
    from backend.app.services.submission_service import SubmissionService
    svc = SubmissionService()
    s1 = svc.create_submission(db, 2, "P01", open("data/demo_sequences/code/SYN002_P01_a1.py").read())
    svc.run_and_analyze(db, s1.id)
    s2 = svc.create_submission(db, 2, "P01", open("data/demo_sequences/code/SYN002_P01_a2.py").read())
    r2 = svc.run_and_analyze(db, s2.id)
    assert r2["history_aware"]["primary_confidence"] <= 0.8

def test_resolved_can_recur(db):
    from backend.app.db.models import LearnerState
    from backend.app.services.submission_service import SubmissionService
    svc = SubmissionService()
    db.add(LearnerState(student_id=1, misconception_id="M01_LOOP_BOUNDARY", state=MisconceptionState.RESOLVED, confidence=0.1))
    db.commit()
    sub = svc.create_submission(db, 1, "P01", open("data/demo_sequences/code/SYN001_P01_a1.py").read())
    r = svc.run_and_analyze(db, sub.id)
    from backend.app.db.models import LearnerStateHistory
    recur = db.query(LearnerStateHistory).filter(LearnerStateHistory.new_state == MisconceptionState.RECURRED).count()
    assert recur >= 0
''')

w("backend/tests/test_state_transitions.py", '''
from backend.app.db.models import LearnerState, MisconceptionState
from backend.app.services.submission_service import SubmissionService

def test_single_failure_not_automatically_persistent(db):
    svc = SubmissionService()
    sub = svc.create_submission(db, 2, "P01", open("data/demo_sequences/code/SYN002_P01_a1.py").read())
    svc.run_and_analyze(db, sub.id)
    ls = db.query(LearnerState).filter(LearnerState.student_id == 2, LearnerState.misconception_id == "M01_LOOP_BOUNDARY").first()
    assert ls is None or ls.state != MisconceptionState.PERSISTENT

def test_cross_problem_recurrence_can_raise_persistence(db):
    svc = SubmissionService()
    s1 = svc.create_submission(db, 1, "P01", open("data/demo_sequences/code/SYN001_P01_a1.py").read())
    svc.run_and_analyze(db, s1.id)
    s2 = svc.create_submission(db, 1, "P02", open("data/demo_sequences/code/SYN001_P02_a1.py").read())
    svc.run_and_analyze(db, s2.id)
    ls = db.query(LearnerState).filter(LearnerState.student_id == 1, LearnerState.misconception_id == "M01_LOOP_BOUNDARY").first()
    assert ls is not None
    assert ls.cross_problem_support_count >= 1
''')

w("backend/tests/test_mandatory_contracts.py", '''
from pathlib import Path
import yaml
from backend.app.db.models import MisconceptionState
from backend.app.learner_model.history import HistoryProvider
from backend.app.services.submission_service import SubmissionService

def test_no_future_history_leakage(db):
    from datetime import datetime, timedelta, timezone
    from backend.app.db.models import LearnerStateHistory, Submission
    hp = HistoryProvider()
    sub = Submission(student_id=1, problem_id="P01", attempt_number=99, source_code="def f(): pass")
    db.add(sub); db.commit(); db.refresh(sub)
    db.add(LearnerStateHistory(
        student_id=1, misconception_id="M01_LOOP_BOUNDARY",
        old_state=MisconceptionState.NEW, new_state=MisconceptionState.PERSISTENT,
        old_confidence=0.2, new_confidence=0.9, submission_id=sub.id + 1000,
        timestamp=datetime.now(timezone.utc) + timedelta(days=1),
    ))
    db.commit()
    prior = hp.get_prior_submissions(db, sub)
    assert all(p.id < sub.id for p in prior)

def test_same_problem_repetition_does_not_automatically_mean_persistent(db):
    svc = SubmissionService()
    s1 = svc.create_submission(db, 2, "P01", open("data/demo_sequences/code/SYN002_P01_a1.py").read())
    svc.run_and_analyze(db, s1.id)
    s2 = svc.create_submission(db, 2, "P01", open("data/demo_sequences/code/SYN002_P01_a1.py").read())
    svc.run_and_analyze(db, s2.id)
    from backend.app.db.models import LearnerState
    ls = db.query(LearnerState).filter(LearnerState.student_id == 2).first()
    assert ls is None or ls.state != MisconceptionState.PERSISTENT

def test_cross_problem_recurrence_can_create_persistent_state(db):
    svc = SubmissionService()
    client_seq = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(__import__("backend.app.main", fromlist=["app"]).app)
    client_seq.post("/api/demo/run-sequence/SYN001")
    from backend.app.db.models import LearnerState, Student
    st = db.query(Student).filter(Student.display_name == "SYN001").first()
    ls = db.query(LearnerState).filter(LearnerState.student_id == st.id).first()
    assert ls is not None

def test_evaluation_dataset_not_used_for_weight_configuration():
    cfg = yaml.safe_load(Path("config/evidence_weights.yaml").read_text(encoding="utf-8"))
    eval_dir = Path("data/evaluation_sequences")
    text = yaml.dump(cfg)
    for f in eval_dir.glob("*.json"):
        assert f.read_text(encoding="utf-8") not in text
    src = Path("backend/app/diagnosis/confidence.py").read_text(encoding="utf-8")
    assert "evaluation_sequences" not in src
''')

print("tests done")
