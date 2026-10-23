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
    bad = "def sum_first_n(n):\n    return n +"
    sub = service.create_submission(db, student.id, "P01", bad)
    result = service.execute(db, sub.id)
    assert result["execution_status"] == "syntax_error"

def test_timeout_is_captured(db, service, monkeypatch):
    class TimeoutRunner:
        def execute_function(self, source_code, function_name, args, timeout_seconds):
            return ExecutionResult(status="timeout", stderr="Execution timed out", error_type="Timeout")
    import backend.app.execution.test_runner as tr
    monkeypatch.setattr(tr, "get_runner", lambda *a, **k: TimeoutRunner())
    student = db.query(Student).first()
    sub = service.create_submission(db, student.id, "P01", "def sum_first_n(n):\n    return 0")
    result = service.execute(db, sub.id)
    assert result["execution_status"] == "timeout"
