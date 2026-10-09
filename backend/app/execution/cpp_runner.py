"""C++ execution pipeline: compile with g++, run with stdin/stdout paradigm.

Both compilation and execution happen inside the sandbox (see sandbox.py).
"""
from __future__ import annotations

import time
from pathlib import Path

from backend.app.config import settings
from backend.app.execution.runner import ExecutionResult, ExecutionRunner
from backend.app.execution.sandbox import (
    SandboxUnavailable,
    check_cpp_source,
    clean_compiler_output,
    new_workdir,
    run_in_sandbox,
)

CPP_STANDARD = "c++17"
COMPILER_MEMORY_MB = 2048
BINARY_NAME = "solution.exe"  # name is fine on POSIX too


class CppCompileSession:
    """Holds a compiled binary so we can run it multiple times without recompiling."""

    def __init__(self, workdir: Path, tmp):
        self._workdir = workdir
        self._tmp = tmp  # kept alive to prevent cleanup until session is done

    def run(self, stdin_data: str, timeout_seconds: int, memory_mb: int | None = None) -> ExecutionResult:
        start = time.perf_counter()
        try:
            res = run_in_sandbox(
                [f"./{BINARY_NAME}"], self._workdir, stdin_data=stdin_data,
                timeout=timeout_seconds, memory_mb=memory_mb,
            )
        except SandboxUnavailable as exc:
            return ExecutionResult(status="system_error", stderr=str(exc), error_type="SandboxUnavailable")
        except Exception:
            return ExecutionResult(status="system_error", stderr="Execution failed to start", error_type="SystemError")
        elapsed_ms = (time.perf_counter() - start) * 1000

        if res.timed_out:
            return ExecutionResult(status="timeout", stderr="Execution timed out", error_type="Timeout")
        if res.output_limit_hit:
            return ExecutionResult(
                status="runtime_error", stdout=res.stdout, stderr="Output limit exceeded",
                runtime_ms=elapsed_ms, error_type="OutputLimitExceeded",
            )
        if res.returncode != 0:
            err = res.stderr[:4096]
            if res.returncode < 0:
                err = (err + f"\nProcess terminated by signal {-res.returncode}").strip()
            return ExecutionResult(
                status="runtime_error", stdout=res.stdout, stderr=err,
                runtime_ms=elapsed_ms, error_type="MemoryLimitExceeded" if res.memory_limit_hit else "RuntimeError",
            )
        return ExecutionResult(
            status="success", stdout=res.stdout, stderr=res.stderr[:4096],
            runtime_ms=elapsed_ms, return_value=res.stdout.strip(),
        )

    def cleanup(self) -> None:
        try:
            self._tmp.cleanup()
        except Exception:
            pass


def compile_cpp(source_code: str) -> "tuple[CppCompileSession | None, ExecutionResult | None]":
    """Compile C++ source. Returns (session, None) on success or (None, error_result) on failure."""
    rejected = check_cpp_source(source_code)
    if rejected:
        return None, ExecutionResult(status="syntax_error", stderr=rejected, error_type="DisallowedDirective")

    tmp = new_workdir()
    workdir = Path(tmp.name)
    (workdir / "solution.cpp").write_text(source_code, encoding="utf-8")
    try:
        res = run_in_sandbox(
            ["g++", f"-std={CPP_STANDARD}", "-O2", "-Wall", "solution.cpp", "-o", BINARY_NAME],
            workdir,
            timeout=settings.compile_timeout_seconds,
            memory_mb=COMPILER_MEMORY_MB,
            output_bytes=8 * 1024 * 1024,  # the binary itself is written under this file-size cap
        )
    except SandboxUnavailable as exc:
        tmp.cleanup()
        return None, ExecutionResult(status="system_error", stderr=str(exc), error_type="SandboxUnavailable")
    except Exception:
        tmp.cleanup()
        return None, ExecutionResult(status="system_error", stderr="Compiler failed to start", error_type="SystemError")

    if res.timed_out:
        tmp.cleanup()
        return None, ExecutionResult(status="timeout", stderr="Compilation timed out", error_type="CompileTimeout")
    if res.returncode != 0 or not (workdir / BINARY_NAME).exists():
        msg = clean_compiler_output(res.stderr, workdir) or "Compilation failed"
        tmp.cleanup()
        return None, ExecutionResult(status="syntax_error", stderr=msg, error_type="CompileError")

    return CppCompileSession(workdir, tmp), None


class CppExecutionRunner(ExecutionRunner):
    """Compiles C++ source with g++ and runs the binary against stdin input."""

    def execute_function(self, source_code: str, function_name: str, args: list, timeout_seconds: int) -> ExecutionResult:
        # function_name and args are ignored — use stdin-based I/O
        return self.execute_with_stdin(source_code, "", timeout_seconds)

    def execute_with_stdin(self, source_code: str, stdin_data: str, timeout_seconds: int) -> ExecutionResult:
        session, err = compile_cpp(source_code)
        if err:
            return err
        try:
            return session.run(stdin_data, timeout_seconds)
        finally:
            session.cleanup()
