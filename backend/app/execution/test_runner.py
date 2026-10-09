from __future__ import annotations
import json, time
from typing import Any
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db.models import ExecutionStatus, Problem, Submission, TestCase, TestResult, TestType
from backend.app.execution.runner import ExecutionResult, SubmissionExecutionResult, TestCaseResult
from backend.app.execution.subprocess_runner import SubprocessExecutionRunner
from backend.app.execution.cpp_runner import CppExecutionRunner, compile_cpp


def _is_cpp_code(source_code: str) -> bool:
    return "#include" in source_code or "int main" in source_code


def get_runner(source_code: str = "", language: str = "python"):
    if language == "cpp" or _is_cpp_code(source_code):
        return CppExecutionRunner()
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
    language = getattr(problem, "language", "python") or "python"
    runner = get_runner(submission.source_code, language)
    use_cpp = language == "cpp" or _is_cpp_code(submission.source_code)
    db.query(TestResult).filter(TestResult.submission_id == submission.id).delete()
    results: list[TestCaseResult] = []
    overall_status = "success"
    total_ms = 0.0
    stderr_parts: list[str] = []
    # For C++: compile once, then run binary for each test case
    cpp_session = None
    if use_cpp:
        cpp_session, compile_err = compile_cpp(submission.source_code)
        if compile_err:
            # Compilation failed — mark all test cases as failed and return early
            submission.execution_status = ExecutionStatus.SYNTAX_ERROR
            submission.stderr = compile_err.stderr
            db.commit()
            return SubmissionExecutionResult(
                execution_status="syntax_error",
                stderr=compile_err.stderr,
                test_results=[],
            )

    try:
        for tc in test_cases:
            payload = _parse_json(tc.input_json) or {}
            expected = _parse_json(tc.expected_output_json)
            if use_cpp:
                stdin_data = payload.get("stdin", "")
                if not stdin_data and payload.get("args"):
                    stdin_data = " ".join(str(a) for a in payload["args"]) + "\n"
                exec_result = cpp_session.run(stdin_data, settings.execution_timeout_seconds)
                if not isinstance(expected, str):
                    expected = str(expected).strip()
            else:
                args = payload.get("args", [])
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
            actual_val = exec_result.return_value
            if use_cpp and exec_result.status == "success":
                actual_val = exec_result.stdout.strip()
            passed = exec_result.status == "success" and actual_val == expected
            error_type = None if passed else exec_result.error_type or ("AssertionError" if exec_result.status == "success" else exec_result.status)
            tr = TestCaseResult(
                test_case_id=tc.id,
                passed=passed,
                actual_output=actual_val if exec_result.status == "success" else None,
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
    finally:
        if cpp_session:
            cpp_session.cleanup()

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
