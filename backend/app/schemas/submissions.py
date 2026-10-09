from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.app.config import settings


class SubmissionCreate(BaseModel):
    problem_id: str = Field(min_length=1, max_length=8, pattern=r"^[A-Za-z0-9_-]+$")
    source_code: str
    # Accepted for backwards compatibility only; must equal the caller's own
    # student id if sent. The server always uses the authenticated student.
    student_id: int | None = None

    @field_validator("source_code")
    @classmethod
    def _size(cls, v: str) -> str:
        if len(v.encode("utf-8")) > settings.max_source_bytes:
            raise ValueError(f"Source code must be at most {settings.max_source_bytes // 1024} KB")
        if "\x00" in v:
            raise ValueError("Source code contains a NUL byte")
        return v


class SubmissionRead(BaseModel):
    id: int
    student_id: int
    problem_id: str
    attempt_number: int
    source_code: str
    submitted_at: datetime
    execution_status: str | None = None
    runtime_ms: float | None = None
    model_config = {"from_attributes": True}


class SubmissionSummary(BaseModel):
    id: int
    student_id: int
    problem_id: str
    problem_title: str
    attempt_number: int
    submitted_at: datetime
    execution_status: str | None = None
    passed: bool
    tests_passed: int
    tests_total: int
    primary_misconception: str | None = None
    primary_confidence: float | None = None
    requires_teacher_review: bool = False


class TestResultRead(BaseModel):
    __test__ = False
    test_case_id: str
    passed: bool
    test_type: str | None = None
    name: str | None = None
    actual_output_json: Any = None
    expected_output_json: Any = None
    error_type: str | None = None
    runtime_ms: float | None = None


class ExecutionResponse(BaseModel):
    submission_id: int
    execution_status: str
    runtime_ms: float | None = None
    stderr: str = ""
    test_results: list[TestResultRead] = Field(default_factory=list)


class DiagnosisBrief(BaseModel):
    id: int
    mode: str
    primary_misconception: str
    primary_confidence: float
    alternative_misconception: str | None = None
    alternative_confidence: float | None = None
    uncertainty_level: str
    requires_teacher_review: bool
    explanation: dict = Field(default_factory=dict)


class RunAndAnalyzeResponse(BaseModel):
    submission_id: int
    execution_status: str
    runtime_ms: float | None = None
    stderr: str = ""
    test_results: list[TestResultRead] = Field(default_factory=list)
    evidence_count: int = 0
    current_only: DiagnosisBrief | None = None
    history_aware: DiagnosisBrief | None = None
    hint: dict | None = None


class HintRead(BaseModel):
    level: int
    max_level: int
    text: str
    misconception_id: str
