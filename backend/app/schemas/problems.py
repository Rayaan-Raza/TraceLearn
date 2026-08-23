from typing import Any

from pydantic import BaseModel, Field


class TestCasePublic(BaseModel):
    id: str
    name: str
    test_type: str
    input_json: Any | None = None


class ProblemSummary(BaseModel):
    id: str
    title: str
    function_name: str
    concept_tags: list[str] = Field(default_factory=list)


class ProblemDetail(ProblemSummary):
    slug: str
    description: str
    prerequisite_tags: list[str] = Field(default_factory=list)
    starter_code: str
    test_cases: list[TestCasePublic] = Field(default_factory=list)