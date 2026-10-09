"""Python execution for student submissions.

Each call runs a fresh, isolated ``python3 -I`` interpreter inside the
sandbox (see sandbox.py). Student code never runs inside the server process,
so it cannot read the server's memory, environment (secrets) or database.
"""
from __future__ import annotations

import json
import secrets
import sys
import os
from pathlib import Path
from typing import Any

from backend.app.execution.runner import ExecutionResult, ExecutionRunner
from backend.app.execution.sandbox import SandboxUnavailable, new_workdir, run_in_sandbox

# Executed inside the sandbox. Reads {"args": [...], "nonce": "..."} on stdin,
# loads solution.py, calls the function, writes the outcome to result_<nonce>.json.
HARNESS = r'''
import json, sys, time, traceback

def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        return {"__unserializable_repr__": repr(v)[:500]}

def main():
    payload = json.loads(sys.stdin.read())
    out_name = "result_%s.json" % payload["nonce"]
    fn_name = payload["function_name"]
    def finish(obj):
        with open(out_name, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
    with open("solution.py", encoding="utf-8") as fh:
        src = fh.read()
    try:
        code = compile(src, "solution.py", "exec")
    except SyntaxError as e:
        finish({"status": "syntax_error", "stderr": str(e), "error_type": "SyntaxError"})
        return
    ns = {"__name__": "__solution__"}
    try:
        exec(code, ns)
        fn = ns.get(fn_name)
        if fn is None:
            finish({"status": "runtime_error", "stderr": "Function %s not found" % fn_name, "error_type": "NameError"})
            return
        start = time.perf_counter()
        result = fn(*payload["args"])
        elapsed = (time.perf_counter() - start) * 1000
        finish({"status": "success", "return_value": _jsonable(result), "runtime_ms": elapsed})
    except MemoryError:
        finish({"status": "runtime_error", "stderr": "Memory limit exceeded", "error_type": "MemoryError"})
    except RecursionError as e:
        finish({"status": "runtime_error", "stderr": str(e)[:2000], "error_type": "RecursionError"})
    except BaseException as e:
        finish({"status": "runtime_error", "stderr": str(e)[:2000], "error_type": type(e).__name__})

main()
'''


def _python_executable() -> str:
    """The real interpreter binary (not a venv shim), visible inside the sandbox."""
    return os.path.realpath(getattr(sys, "_base_executable", None) or sys.executable)


class SubprocessExecutionRunner(ExecutionRunner):
    def execute_function(self, source_code: str, function_name: str, args: list[Any], timeout_seconds: int) -> ExecutionResult:
        tmp = new_workdir()
        try:
            workdir = Path(tmp.name)
            (workdir / "solution.py").write_text(source_code, encoding="utf-8")
            (workdir / "harness.py").write_text(HARNESS, encoding="utf-8")
            nonce = secrets.token_hex(16)
            payload = json.dumps({"args": args, "function_name": function_name, "nonce": nonce})
            try:
                res = run_in_sandbox(
                    [_python_executable(), "-I", "-S", "harness.py"], workdir,
                    stdin_data=payload, timeout=timeout_seconds,
                )
            except SandboxUnavailable as exc:
                return ExecutionResult(status="system_error", stderr=str(exc), error_type="SandboxUnavailable")
            except Exception:
                return ExecutionResult(status="system_error", stderr="Execution failed to start", error_type="SystemError")

            if res.timed_out:
                return ExecutionResult(status="timeout", stderr="Execution timed out", error_type="Timeout")
            result_file = workdir / f"result_{nonce}.json"
            if not result_file.exists():
                if res.output_limit_hit:
                    return ExecutionResult(status="runtime_error", stderr="Output limit exceeded", error_type="OutputLimitExceeded")
                return ExecutionResult(status="system_error", stderr="No result from worker", error_type="SystemError")
            try:
                data = json.loads(result_file.read_text(encoding="utf-8")[: 1024 * 1024])
            except (ValueError, OSError):
                return ExecutionResult(status="system_error", stderr="Malformed result from worker", error_type="SystemError")
            return ExecutionResult(
                status=data.get("status", "system_error"),
                stdout=res.stdout,
                stderr=str(data.get("stderr", ""))[:4096],
                runtime_ms=data.get("runtime_ms"),
                return_value=data.get("return_value"),
                error_type=data.get("error_type"),
            )
        finally:
            tmp.cleanup()
