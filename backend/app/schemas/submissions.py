from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class SubmissionCreate(BaseModel):
    student_id: int
    problem_id: str
    source_code: str
    attempt_number: int = 1

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

class TestResultRead(BaseModel):
    test_case_id: str
    passed: bool
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
