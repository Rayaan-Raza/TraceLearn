from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ExecutionResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    runtime_ms: float | None = None
    return_value: Any = None
    error_type: str | None = None

@dataclass
class TestCaseResult:
    test_case_id: str
    passed: bool
    actual_output: Any = None
    expected_output: Any = None
    error_type: str | None = None
    runtime_ms: float | None = None

@dataclass
class SubmissionExecutionResult:
    execution_status: str
    stdout: str = ""
    stderr: str = ""
    runtime_ms: float | None = None
    test_results: list[TestCaseResult] = field(default_factory=list)

class ExecutionRunner(ABC):
    @abstractmethod
    def execute_function(self, source_code: str, function_name: str, args: list[Any], timeout_seconds: int) -> ExecutionResult:
        raise NotImplementedError
