from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")
(ROOT / "backend/app/schemas/diagnosis.py").write_text("""
\"\"\"Diagnosis API schemas.

DiagnosisContext intentionally excludes ground-truth labels. Evaluation-only
labels are loaded through the dedicated evaluation labels module (not imported here).
\"\"\"
from pydantic import BaseModel, Field


class TestResultSummary(BaseModel):
    test_case_id: str
    passed: bool
    stdout: str = ""
    stderr: str = ""


class DiagnosisContext(BaseModel):
    submission_id: int
    student_id: int
    problem_id: str
    code: str
    attempt_number: int = 1
    test_results: list[TestResultSummary] = Field(default_factory=list)


class DiagnosisHypothesis(BaseModel):
    misconception_id: str
    confidence: float
    rank: int = 1
""".strip() + "\n", encoding="utf-8", newline="\n")

(ROOT / "backend/tests/conftest.py").write_text("""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "tracelearn_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"


@pytest.fixture(scope="session", autouse=True)
def _reset_test_db() -> None:
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
""".strip() + "\n", encoding="utf-8", newline="\n")
print("fixed")
