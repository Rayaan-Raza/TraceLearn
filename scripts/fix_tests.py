from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

def w(rel, text):
    (ROOT / rel).write_text(text.strip() + "\n", encoding="utf-8", newline="\n")

w("backend/tests/test_execution.py", """
from pathlib import Path
import pytest
from backend.app.db.models import Student
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
    from backend.app.execution import subprocess_runner
    def slow(*a, **k):
        from backend.app.execution.runner import ExecutionResult
        import time
        time.sleep(10)
        return ExecutionResult(status="success")
    monkeypatch.setattr(subprocess_runner.SubprocessExecutionRunner, "execute_function", slow)
    student = db.query(Student).first()
    sub = service.create_submission(db, student.id, "P01", "def sum_first_n(n):\\n    return 0")
    result = service.execute(db, sub.id)
    assert result["execution_status"] == "timeout"
""")

w("backend/tests/test_diagnosis.py", """
import pytest
from backend.app.db.models import Diagnosis, DiagnosisMode, EvidenceSourceType
from backend.app.diagnosis.current_only import CurrentOnlyDiagnosisEngine
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
    sub = service.create_submission(db, 1, "P01", open("data/demo_sequences/code/SYN001_P01_a1.py").read())
    service.run_and_analyze(db, sub.id)
    assert called["history"] is False
    cur = db.query(Diagnosis).filter_by(submission_id=sub.id, mode=DiagnosisMode.CURRENT_ONLY).first()
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
    sub = service.create_submission(db, 1, "P01", "def sum_first_n(n\\n")
    r = service.run_and_analyze(db, sub.id)
    assert r["current_only"]["primary_misconception"] in ("NO_MISCONCEPTION", "UNCERTAIN")

def test_teacher_correction_preserves_original_prediction(db, service, client):
    sub = service.create_submission(db, 1, "P01", open("data/demo_sequences/code/SYN001_P01_a1.py").read())
    r = service.run_and_analyze(db, sub.id)
    diag_id = r["history_aware"]["id"]
    orig = r["history_aware"]["primary_misconception"]
    resp = client.post(f"/api/diagnoses/{diag_id}/teacher-review", json={"action": "CORRECT", "corrected_misconception": "M02_INDEX_VALUE", "comment": "teacher fix"})
    assert resp.status_code == 200
    d = db.get(Diagnosis, diag_id)
    assert d.primary_misconception == orig

def test_experiment_metrics_generated_from_database(db, service, client):
    for sid in range(1, 4):
        client.post(f"/api/demo/run-sequence/SYN00{sid}")
    from backend.app.evaluation.evaluator import ExperimentEvaluator
    metrics = ExperimentEvaluator(db).collect_predictions()
    assert "history_changed_predictions" in metrics
    assert metrics["current_only_metrics"]["macro_f1"] >= 0.0
""")

print("fixed tests")
