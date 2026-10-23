from pydantic import BaseModel, Field


class BankTestCasePublic(BaseModel):
    __test__ = False
    """One test case as the bank returns it.

    Input and expected output are filled only for public tests. Public code
    never receives the input or the expected output of a hidden test.
    """
    index: int
    test_type: str  # "visible", "hidden" or "diagnostic"
    input: str | None = None
    expected_output: str | None = None
    time_limit_ms: int | None = None
    memory_limit_mb: int | None = None


class BankProvenancePublic(BaseModel):
    """Source record. It holds no learner data."""
    dataset_source: str
    source_problem_id: str
    source_url: str = ""
    source_license: str = ""
    license_verified: bool = False
    provenance_ref: str = ""


class BankQualityCheckPublic(BaseModel):
    check_code: str
    passed: bool
    detail: str = ""


class BankProblemSummary(BaseModel):
    id: str
    title: str
    topic: str
    difficulty: str
    language: str
    tags: list[str] = Field(default_factory=list)
    dataset_source: str
    sample_count: int
    hidden_count: int


class BankProblemDetail(BankProblemSummary):
    description: str
    input_spec: str = ""
    output_spec: str = ""
    constraints: str = ""
    starter_code: str = ""
    language_standard: str = "cpp17"
    sample_tests: list[BankTestCasePublic] = Field(default_factory=list)
    # The two fields below are filled only for teachers.
    provenance: BankProvenancePublic | None = None
    quality: list[BankQualityCheckPublic] = Field(default_factory=list)


class BankTagCount(BaseModel):
    tag: str
    problem_count: int


class BankRunRequest(BaseModel):
    source_code: str = Field(min_length=1, max_length=65_536)


class BankRunTestResult(BaseModel):
    index: int
    test_type: str
    passed: bool
    runtime_ms: float | None = None
    # Actual and expected output stay null for every non-public test.
    actual_output: str | None = None
    expected_output: str | None = None


class BankRunResponse(BaseModel):
    problem_id: str
    execution_status: str
    stderr: str | None = None
    passed_count: int
    total_count: int
    results: list[BankRunTestResult] = Field(default_factory=list)


class BankSolutionCreate(BaseModel):
    source_code: str = Field(min_length=1, max_length=65_536)
    license: str = Field(default="", max_length=64)
