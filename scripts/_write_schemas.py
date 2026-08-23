from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

def w(rel, text):
    (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / rel).write_text(text.strip() + "\n", encoding="utf-8", newline="\n")

w("backend/app/schemas/problems.py", """
from pydantic import BaseModel, Field


class TestCasePublic(BaseModel):
    id: str
    name: str
    visibility: str
    sort_order: int = 0
    stdin: str = ""
    expected_stdout: str | None = None


class ProblemSummary(BaseModel):
    id: str
    title: str
    difficulty: str
    taxonomy_tags: list[str] = Field(default_factory=list)


class ProblemDetail(ProblemSummary):
    description: str
    starter_code: str
    test_cases: list[TestCasePublic] = Field(default_factory=list)
""")

w("backend/app/schemas/submissions.py", """
from datetime import datetime

from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    student_external_id: str
    problem_id: str
    code: str


class SubmissionRead(BaseModel):
    id: int
    student_id: int
    problem_id: str
    attempt_number: int
    submitted_at: datetime

    model_config = {"from_attributes": True}
""")

w("backend/app/schemas/evidence.py", """
from pydantic import BaseModel


class EvidenceItemRead(BaseModel):
    id: int
    submission_id: int
    evidence_type: str
    payload_json: str
    weight: float

    model_config = {"from_attributes": True}
""")

w("backend/app/schemas/learners.py", """
from datetime import datetime

from pydantic import BaseModel


class LearnerStateRead(BaseModel):
    id: int
    student_id: int
    misconception_id: str
    state: str
    updated_at: datetime

    model_config = {"from_attributes": True}
""")

w("backend/app/schemas/diagnosis.py", """
\"\"\"Diagnosis API schemas.

DiagnosisContext intentionally excludes ground-truth labels. Evaluation labels
are loaded only via backend.app.evaluation.labels.GroundTruthRepository.
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
""")

w("backend/app/evaluation/labels.py", """
\"\"\"Holdout ground truth — not imported by diagnosis modules.\"\"\"
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_LABELS_PATH = Path("data/annotations/ground_truth.json")


class GroundTruthRepository:
    \"\"\"Loads misconception labels for evaluation only.\"\"\"

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_LABELS_PATH
        self._by_submission: dict[str, list[str]] = {}
        if self._path.is_file():
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for row in raw.get("submissions", []):
                sid = str(row["submission_id"])
                self._by_submission[sid] = list(row.get("misconception_ids", []))

    def get_misconceptions(self, submission_id: int | str) -> list[str]:
        return list(self._by_submission.get(str(submission_id), []))

    def has_label(self, submission_id: int | str) -> bool:
        return str(submission_id) in self._by_submission
""")

print("schemas+labels ok")
