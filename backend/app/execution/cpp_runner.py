"""C++ execution pipeline: compile with g++, run with stdin/stdout paradigm."""
from __future__ import annotations
import subprocess
import tempfile
import time
from pathlib import Path
from backend.app.execution.runner import ExecutionResult, ExecutionRunner

CPP_STANDARD = "c++17"
COMPILE_TIMEOUT = 60  # generous to account for AV scans on Windows


class CppCompileSession:
    """Holds a compiled binary so we can run it multiple times without recompiling."""

    def __init__(self, binary_path: Path, tmp_dir: tempfile.TemporaryDirectory):
        self._binary = binary_path
        self._tmp = tmp_dir  # kept alive to prevent cleanup until session is done

    def run(self, stdin_data: str, timeout_seconds: int) -> ExecutionResult:
        start = time.perf_counter()
        try:
            run_result = subprocess.run(
                [str(self._binary)],
                input=stdin_data,
                capture_output=True, text=True,
                timeout=timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
        except subprocess.TimeoutExpired:
            return ExecutionResult(status="timeout", stderr="Execution timed out", error_type="Timeout")
        except Exception as exc:
            return ExecutionResult(status="system_error", stderr=str(exc), error_type="SystemError")

        if run_result.returncode != 0:
            return ExecutionResult(
                status="runtime_error",
                stdout=run_result.stdout, stderr=run_result.stderr,
                runtime_ms=(time.perf_counter() - start) * 1000,
                error_type="RuntimeError",
            )
        return ExecutionResult(
            status="success",
            stdout=run_result.stdout, stderr=run_result.stderr,
            runtime_ms=elapsed_ms,
            return_value=run_result.stdout.strip(),
        )

    def cleanup(self) -> None:
        try:
            self._tmp.cleanup()
        except Exception:
            pass


def compile_cpp(source_code: str) -> "tuple[CppCompileSession | None, ExecutionResult | None]":
    """Compile C++ source. Returns (session, None) on success or (None, error_result) on failure."""
    tmp = tempfile.TemporaryDirectory()
    src = Path(tmp.name) / "solution.cpp"
    binary = Path(tmp.name) / "solution.exe"
    src.write_text(source_code, encoding="utf-8")
    try:
        result = subprocess.run(
            ["g++", f"-std={CPP_STANDARD}", "-O2", "-Wall", str(src), "-o", str(binary)],
            capture_output=True, text=True, timeout=COMPILE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        tmp.cleanup()
        return None, ExecutionResult(status="timeout", stderr="Compilation timed out", error_type="CompileTimeout")
    except Exception as exc:
        tmp.cleanup()
        return None, ExecutionResult(status="system_error", stderr=str(exc), error_type="SystemError")

    if result.returncode != 0:
        tmp.cleanup()
        return None, ExecutionResult(status="syntax_error", stderr=result.stderr, error_type="CompileError")

    return CppCompileSession(binary, tmp), None


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
