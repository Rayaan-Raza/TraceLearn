"""Build execution, analysis, diagnosis modules."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
    print("w", rel)

# execution
w("backend/app/execution/runner.py", '''
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
''')

w("backend/app/execution/subprocess_runner.py", '''
"""Subprocess execution for TRUSTED synthetic POC code only — NOT a secure sandbox."""
from __future__ import annotations
import json, multiprocessing, textwrap, time
from typing import Any
from backend.app.execution.runner import ExecutionResult, ExecutionRunner

def _worker(source: str, function_name: str, args: list[Any], q: multiprocessing.Queue) -> None:
    try:
        ns: dict[str, Any] = {}
        exec(source, ns)
        fn = ns.get(function_name)
        if fn is None:
            q.put({"status": "runtime_error", "stderr": f"Function {function_name} not found", "error_type": "NameError"})
            return
        start = time.perf_counter()
        result = fn(*args)
        elapsed = (time.perf_counter() - start) * 1000
        q.put({"status": "success", "return_value": result, "runtime_ms": elapsed})
    except SyntaxError as e:
        q.put({"status": "syntax_error", "stderr": str(e), "error_type": "SyntaxError"})
    except Exception as e:
        q.put({"status": "runtime_error", "stderr": str(e), "error_type": type(e).__name__})

class SubprocessExecutionRunner(ExecutionRunner):
    def execute_function(self, source_code: str, function_name: str, args: list[Any], timeout_seconds: int) -> ExecutionResult:
        q: multiprocessing.Queue = multiprocessing.Queue()
        p = multiprocessing.Process(target=_worker, args=(source_code, function_name, args, q))
        p.start()
        p.join(timeout_seconds)
        if p.is_alive():
            p.terminate()
            p.join(1)
            return ExecutionResult(status="timeout", stderr="Execution timed out", error_type="Timeout")
        if q.empty():
            return ExecutionResult(status="system_error", stderr="No result from worker", error_type="SystemError")
        data = q.get()
        return ExecutionResult(
            status=data.get("status", "system_error"),
            stderr=data.get("stderr", ""),
            runtime_ms=data.get("runtime_ms"),
            return_value=data.get("return_value"),
            error_type=data.get("error_type"),
        )
''')

w("backend/app/execution/docker_runner.py", '''
from __future__ import annotations
from typing import Any
from backend.app.execution.runner import ExecutionResult, ExecutionRunner

class DockerNotConfiguredError(RuntimeError):
    pass

class DockerExecutionRunner(ExecutionRunner):
    def execute_function(self, source_code: str, function_name: str, args: list[Any], timeout_seconds: int) -> ExecutionResult:
        raise DockerNotConfiguredError("Docker execution is not configured for this POC environment")
''')

w("backend/app/execution/test_runner.py", '''
from __future__ import annotations
import json, time
from typing import Any
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db.models import ExecutionStatus, Problem, Submission, TestCase, TestResult, TestType
from backend.app.execution.runner import SubmissionExecutionResult, TestCaseResult
from backend.app.execution.subprocess_runner import SubprocessExecutionRunner

def get_runner():
    if settings.execution_mode == "docker":
        from backend.app.execution.docker_runner import DockerExecutionRunner
        return DockerExecutionRunner()
    return SubprocessExecutionRunner()

def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def run_submission_tests(db: Session, submission: Submission) -> SubmissionExecutionResult:
    problem = db.get(Problem, submission.problem_id)
    if problem is None:
        return SubmissionExecutionResult(execution_status="system_error", stderr="Problem not found")
    test_cases = db.query(TestCase).filter(TestCase.problem_id == problem.id).order_by(TestCase.id).all()
    runner = get_runner()
    db.query(TestResult).filter(TestResult.submission_id == submission.id).delete()
    results: list[TestCaseResult] = []
    overall_status = "success"
    total_ms = 0.0
    stderr_parts: list[str] = []
    for tc in test_cases:
        payload = _parse_json(tc.input_json) or {}
        args = payload.get("args", [])
        expected = _parse_json(tc.expected_output_json)
        exec_result = runner.execute_function(
            submission.source_code, problem.function_name, args, settings.execution_timeout_seconds
        )
        if exec_result.status == "syntax_error" and overall_status == "success":
            overall_status = "syntax_error"
        elif exec_result.status == "timeout" and overall_status in ("success", "syntax_error"):
            overall_status = "timeout"
        elif exec_result.status == "runtime_error" and overall_status == "success":
            overall_status = "runtime_error"
        elif exec_result.status == "system_error":
            overall_status = "system_error"
        if exec_result.stderr:
            stderr_parts.append(exec_result.stderr)
        if exec_result.runtime_ms:
            total_ms += exec_result.runtime_ms
        passed = exec_result.status == "success" and exec_result.return_value == expected
        error_type = None if passed else exec_result.error_type or ("AssertionError" if exec_result.status == "success" else exec_result.status)
        tr = TestCaseResult(
            test_case_id=tc.id,
            passed=passed,
            actual_output=exec_result.return_value if exec_result.status == "success" else None,
            expected_output=expected,
            error_type=error_type,
            runtime_ms=exec_result.runtime_ms,
        )
        results.append(tr)
        db.add(TestResult(
            submission_id=submission.id,
            test_case_id=tc.id,
            passed=passed,
            actual_output_json=json.dumps(tr.actual_output),
            expected_output_json=json.dumps(expected),
            error_type=error_type,
            runtime_ms=exec_result.runtime_ms,
        ))
        if exec_result.status in ("syntax_error", "timeout", "system_error"):
            break
    if overall_status == "success" and any(not r.passed for r in results):
        overall_status = "runtime_error"
    submission.execution_status = ExecutionStatus(overall_status)
    submission.stderr = chr(10).join(stderr_parts)
    submission.runtime_ms = total_ms or None
    db.commit()
    return SubmissionExecutionResult(
        execution_status=overall_status,
        stderr=submission.stderr,
        runtime_ms=submission.runtime_ms,
        test_results=results,
    )
''')

w("backend/app/execution/__init__.py", '''from backend.app.execution.test_runner import run_submission_tests\n''')

# analysis
w("backend/app/analysis/evidence_models.py", '''
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class EvidenceRecord:
    source_type: str
    evidence_code: str
    direction: str
    weight: float
    description: str
    misconception_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
''')

w("backend/app/analysis/static_analyzer.py", '''
from __future__ import annotations
import ast
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.diagnosis.taxonomy import M01_LOOP_BOUNDARY, M02_INDEX_VALUE, M03_MISSING_RETURN

class StaticAnalyzer:
    def analyze(self, source_code: str, function_name: str) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return items
        items.extend(self._detect_m01(tree))
        items.extend(self._detect_m02(tree))
        items.extend(self._detect_m03(tree, function_name))
        return items

    def _detect_m01(self, tree: ast.AST) -> list[EvidenceRecord]:
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
                if len(node.args) >= 1:
                    arg = node.args[-1]
                    if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
                        if isinstance(arg.left, ast.Name) or isinstance(arg.left, ast.Constant):
                            if isinstance(arg.right, ast.Constant) and arg.right.value == 1:
                                found = True
        if found:
            return [EvidenceRecord(
                source_type="static", evidence_code="STATIC_RANGE_N_PLUS_ONE",
                misconception_id=M01_LOOP_BOUNDARY, direction="support", weight=0.0,
                description="range upper bound uses n + 1",
            )]
        return []

    def _detect_m02(self, tree: ast.AST) -> list[EvidenceRecord]:
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                target_names = []
                if isinstance(node.target, ast.Name):
                    target_names.append(node.target.id)
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Subscript) and isinstance(inner.slice, ast.Name):
                        if inner.slice.id in target_names:
                            return [EvidenceRecord(
                                source_type="static", evidence_code="STATIC_ITER_VALUE_USED_AS_INDEX",
                                misconception_id=M02_INDEX_VALUE, direction="support", weight=0.0,
                                description="loop variable used as collection index",
                            )]
        return []

    def _detect_m03(self, tree: ast.AST, function_name: str) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                has_return = any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(node))
                has_print = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print" for n in ast.walk(node))
                if has_print:
                    items.append(EvidenceRecord(
                        source_type="static", evidence_code="STATIC_PRINT_INSTEAD_OF_RETURN",
                        misconception_id=M03_MISSING_RETURN, direction="support", weight=0.0,
                        description="print() used where return expected",
                    ))
                if not has_return:
                    items.append(EvidenceRecord(
                        source_type="static", evidence_code="STATIC_NO_RETURN",
                        misconception_id=M03_MISSING_RETURN, direction="support", weight=0.0,
                        description="function lacks return statement",
                    ))
        return items
''')

print("execution+static done")
