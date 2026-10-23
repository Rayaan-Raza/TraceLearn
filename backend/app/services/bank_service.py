"""Run student code against problem bank test cases.

The service compiles the source once. Then it runs the binary against every
test case. Each test case can set its own time and memory limits. The
service returns results without the input or the expected output of a hidden
test case. Students never receive hidden grading data.
"""
from __future__ import annotations

from backend.app.config import settings
from backend.app.db.models import TestCase, TestType
from backend.app.execution.cpp_runner import compile_cpp
from backend.app.execution.sandbox import SandboxUnavailable, check_cpp_source, execution_slot
from backend.app.execution.test_runner import _tokens


class BankRunError(Exception):
    """Raised when the request cannot run at all, for example a bad source."""


def _timeout_seconds(tc: TestCase) -> float:
    if tc.time_limit_ms:
        return max(0.1, tc.time_limit_ms / 1000)
    return float(settings.execution_timeout_seconds)


def run_bank_problem(problem_id: str, source_code: str, cases: list[TestCase]) -> dict:
    """Compile `source_code` and run it against `cases`.

    Return a result dictionary. Hidden test cases keep their input and their
    expected output out of the result.
    """
    if not source_code.strip():
        raise BankRunError("The source code is empty.")
    if len(source_code.encode("utf-8")) > settings.max_source_bytes:
        raise BankRunError("The source code is too large.")

    results: list[dict] = []
    status = "success"
    stderr_parts: list[str] = []

    try:
        with execution_slot():
            rejected = check_cpp_source(source_code)
            if rejected:
                return {
                    "problem_id": problem_id,
                    "execution_status": "syntax_error",
                    "stderr": rejected,
                    "passed_count": 0,
                    "total_count": len(cases),
                    "results": [
                        {"index": i + 1, "test_type": tc.test_type.value, "passed": False}
                        for i, tc in enumerate(cases)
                    ],
                }
            session, compile_err = compile_cpp(source_code)
            if compile_err is not None:
                return {
                    "problem_id": problem_id,
                    "execution_status": "syntax_error",
                    "stderr": compile_err.stderr,
                    "passed_count": 0,
                    "total_count": len(cases),
                    "results": [
                        {"index": i + 1, "test_type": tc.test_type.value, "passed": False}
                        for i, tc in enumerate(cases)
                    ],
                }
            try:
                for i, tc in enumerate(cases, start=1):
                    import json as _json
                    payload = _json.loads(tc.input_json or "{}")
                    stdin_data = payload.get("stdin", "") or ""
                    expected = _json.loads(tc.expected_output_json or "null")
                    expected_text = expected if isinstance(expected, str) else str(expected).strip()
                    visible = tc.test_type == TestType.VISIBLE
                    exec_result = session.run(
                        stdin_data, _timeout_seconds(tc), tc.memory_limit_mb,
                    )
                    if exec_result.stderr:
                        stderr_parts.append(exec_result.stderr)
                    passed = (
                        exec_result.status == "success"
                        and _tokens(exec_result.return_value or "") == _tokens(expected_text)
                    )
                    if exec_result.status != "success" and status == "success":
                        status = exec_result.status
                    item = {
                        "index": i,
                        "test_type": tc.test_type.value,
                        "passed": passed,
                        "runtime_ms": exec_result.runtime_ms,
                        "actual_output": exec_result.return_value if visible else None,
                        "expected_output": expected_text if visible else None,
                    }
                    results.append(item)
            finally:
                session.cleanup()
    except SandboxUnavailable as exc:
        return {
            "problem_id": problem_id,
            "execution_status": "system_error",
            "stderr": str(exc),
            "passed_count": 0,
            "total_count": len(cases),
            "results": [],
        }

    if status == "success" and any(not r["passed"] for r in results):
        status = "wrong_answer"
    return {
        "problem_id": problem_id,
        "execution_status": status,
        "stderr": "\n".join(p for p in stderr_parts if p)[:8192] or None,
        "passed_count": sum(1 for r in results if r["passed"]),
        "total_count": len(results),
        "results": results,
    }
