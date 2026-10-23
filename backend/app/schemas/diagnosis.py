"""Diagnosis API schemas.

DiagnosisContext intentionally excludes ground-truth labels. Evaluation-only
labels are loaded through the dedicated evaluation labels module (not imported here).
"""
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
