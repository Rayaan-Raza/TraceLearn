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
