from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class TestCasePublic(BaseModel):
    __test__ = False
    id: str
    name: str
    test_type: str
    # Inputs and expected outputs are only ever filled in for VISIBLE tests.
    input_json: Any | None = None
    expected_output: Any | None = None


class ProblemSummary(BaseModel):
    id: str
    title: str
    function_name: str
    concept_tags: list[str] = Field(default_factory=list)
    language: str = "python"
    topic: str = ""
    difficulty: str = "Easy"
    source: Literal["dataset", "custom"] = "dataset"


class ProblemDetail(ProblemSummary):
    slug: str
    description: str
    prerequisite_tags: list[str] = Field(default_factory=list)
    starter_code: str
    test_cases: list[TestCasePublic] = Field(default_factory=list)


class NewTestCase(BaseModel):
    __test__ = False
    input: str = Field(default="", max_length=4000)
    expected: str = Field(max_length=4000)
    visible: bool = True


class ProblemCreate(BaseModel):
    """Teacher-authored C++ problem with stdin/stdout tests."""
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    topic: str = Field(default="General", max_length=48)
    difficulty: Literal["Easy", "Medium", "Hard"] = "Easy"
    starter_code: str = Field(default="", max_length=16_000)
    concept_tags: list[str] = Field(default_factory=list, max_length=8)
    test_cases: list[NewTestCase] = Field(min_length=1, max_length=20)

    @field_validator("title", "topic")
    @classmethod
    def _single_line(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("concept_tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out = []
        for t in v:
            t = t.strip().lower()[:32]
            if t and all(c.isalnum() or c in "_-" for c in t):
                out.append(t)
        return out
