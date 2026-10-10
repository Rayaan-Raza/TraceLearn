"""Verify the unified C++ diagnostic bank.

This script is the quality gate for `data/cpp_diagnostics`. It answers three
questions for every problem:

1. Does the reference solution pass every test case?
2. Does the misconception variant fail at least one test case?
3. Do the sandbox limits stop a runaway program?

The script performs these checks:

1. COMPILE. It compiles each reference solution with `g++ -O2 -Wall -Wextra
   -std=c++17`. The compile must exit 0 and emit no warning.
2. RUN. It runs every test case in a limited child process. The wall-clock
   limit is 2000 ms. The memory limit is 256 MB of address space. It uses
   `backend.app.execution.sandbox.run_in_sandbox` when that module is
   importable. Otherwise it uses an equivalent mirror of `sandbox._limits`.
3. COMPARE. It compares the captured stdout with the expected output token by
   token. It uses the same rule as `backend/app/execution/test_runner.py`.
4. DETERMINISM. It runs every test case three times. All three outputs must be
   identical.
5. SANITIZE. It compiles each solution with `-fsanitize=address,undefined` and
   runs every test case. No run may report a sanitizer error.
6. VARIANTS. It compiles each misconception variant. A variant must fail at
   least one test case, or it must time out, or the compiler must reject it.
7. LIMITS. It runs two probe programs. One asks for 512 MB and must be stopped
   by the 256 MB limit. One loops forever and must be stopped by the 2000 ms
   wall-clock limit.
8. EXAMPLES. The public examples in `problems.json` must match the visible
   test cases.

Every check prints one line that starts with PASS or FAIL. The script exits 1
when any check fails. It writes a machine-readable copy of the results to
`data/cpp_diagnostics/exports/verification_report.json`.

Usage (from the repository root):

    python scripts/verify_cpp_diagnostics.py
    python scripts/verify_cpp_diagnostics.py --no-sanitize
    python scripts/verify_cpp_diagnostics.py --only CP25

On Windows the script re-executes itself inside WSL. It needs a Linux
distribution with `g++` and `python3`.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK_DIR = ROOT / "data" / "cpp_diagnostics"
EXPORT_DIR = BANK_DIR / "exports"

TIME_LIMIT_MS = 2000
MEMORY_LIMIT_MB = 256
COMPILE_FLAGS = ["-std=c++17", "-O2", "-Wall", "-Wextra"]
BACKEND_FLAGS = ["-std=c++17", "-O2", "-Wall"]
SANITIZE_FLAGS = ["-std=c++17", "-O1", "-g", "-fsanitize=address,undefined",
                  "-fno-omit-frame-pointer"]
UBSAN_FLAGS = ["-std=c++17", "-O1", "-g", "-fsanitize=undefined",
               "-fno-omit-frame-pointer"]
COMPILE_TIMEOUT_S = 30
COMPILE_MEMORY_MB = 2048
DETERMINISM_RUNS = 3


# ---------------------------------------------------------------------------
# result containers
# ---------------------------------------------------------------------------
@dataclass
class RunResult:
    """One child-process run. It mirrors `sandbox.SandboxResult`."""
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    output_limit_hit: bool = False
    memory_limit_hit: bool = False


@dataclass
class Check:
    """One printed check result."""
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Report:
    """Everything the script observed."""
    checks: list[Check] = field(default_factory=list)
    problems: dict = field(default_factory=dict)
    environment: dict = field(default_factory=dict)
    limit_probes: dict = field(default_factory=dict)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(Check(name, passed, detail))

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]


# ---------------------------------------------------------------------------
# sandbox engine
# ---------------------------------------------------------------------------
def _project_engine():
    """Return the project sandbox runner, or None when it cannot be imported."""
    if os.name != "posix":
        return None
    os.environ.setdefault("SANDBOX_MODE", "none")
    os.environ.setdefault("REQUIRE_SANDBOX", "false")
    os.environ.setdefault("APP_ENV", "development")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from backend.app.execution.sandbox import run_in_sandbox  # type: ignore
        return run_in_sandbox
    except Exception:
        return None


def _mirror_run(argv, workdir, *, stdin_data="", timeout, memory_mb,
                output_bytes=None) -> RunResult:
    """Run argv with resource limits. It mirrors `sandbox._limits()`."""
    import resource
    import signal

    out_path = workdir / ".stdout"
    err_path = workdir / ".stderr"
    output_bytes = output_bytes or 64 * 1024

    def apply() -> None:  # runs in the child between fork and exec
        resource.setrlimit(resource.RLIMIT_CPU, (int(timeout) + 1, int(timeout) + 2))
        if memory_mb:  # None means no address-space cap
            mem = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_FSIZE, (output_bytes + 1024, output_bytes + 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    timed_out = False
    with open(out_path, "wb") as out_fh, open(err_path, "wb") as err_fh:
        proc = subprocess.Popen(
            [str(a) for a in argv], cwd=str(workdir),
            stdin=subprocess.PIPE, stdout=out_fh, stderr=err_fh,
            start_new_session=True, preexec_fn=apply,
        )
        try:
            proc.communicate(input=stdin_data.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

    def read_capped(path: Path) -> tuple[str, bool]:
        try:
            with open(path, "rb") as fh:
                data = fh.read(output_bytes + 1)
        except FileNotFoundError:
            return "", False
        return (data[:output_bytes].decode("utf-8", errors="replace"),
                len(data) > output_bytes)

    stdout, out_hit = read_capped(out_path)
    stderr, _ = read_capped(err_path)
    rc = proc.returncode if proc.returncode is not None else -9
    sig = -rc if rc < 0 else 0
    out_hit = out_hit or sig == getattr(signal, "SIGXFSZ", -1)
    mem_hit = "MemoryError" in stderr or "std::bad_alloc" in stderr
    return RunResult(rc, stdout, stderr, timed_out=timed_out,
                     output_limit_hit=out_hit, memory_limit_hit=mem_hit)


class Sandbox:
    """A thin wrapper that normalizes both engines to one call shape."""

    def __init__(self) -> None:
        self._runner = None
        self.engine = "none"

    def start(self) -> None:
        runner = _project_engine()
        if runner is not None:
            self._runner = runner
            self.engine = "backend.app.execution.sandbox.run_in_sandbox"
            return
        if os.name == "posix":
            self._runner = _mirror_run
            self.engine = "mirror of sandbox._limits()"
            return
        raise RuntimeError("This host is not POSIX. Re-run inside WSL.")

    def status(self) -> dict:
        try:
            from backend.app.execution import sandbox as s
            return s.sandbox_status()
        except Exception:
            return {"mode": "unknown", "isolated": False, "required": False}

    def run(self, argv, workdir, *, stdin_data="", timeout, memory_mb,
            output_bytes=None, apply_memory_limit=True) -> RunResult:
        assert self._runner is not None, "call Sandbox.start() first"
        if apply_memory_limit:
            res = self._runner(
                [str(a) for a in argv], workdir, stdin_data=stdin_data,
                timeout=timeout, memory_mb=memory_mb, output_bytes=output_bytes,
            )
        else:
            # AddressSanitizer reserves about 16 TB of virtual address space for
            # its shadow. Any RLIMIT_AS below that size stops it from starting.
            # A sanitizer run is a quality check, not the judged run, so it runs
            # without the memory cap. The judged runs keep the 256 MB cap.
            res = _mirror_run([str(a) for a in argv], workdir, stdin_data=stdin_data,
                              timeout=timeout, memory_mb=None, output_bytes=output_bytes)
        return RunResult(
            returncode=getattr(res, "returncode", 0),
            stdout=getattr(res, "stdout", ""),
            stderr=getattr(res, "stderr", ""),
            timed_out=getattr(res, "timed_out", False),
            output_limit_hit=getattr(res, "output_limit_hit", False),
            memory_limit_hit=getattr(res, "memory_limit_hit", False),
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def tokens(text: str) -> list[str]:
    """Judge-style comparison. Whitespace and line breaks do not change it."""
    return str(text).split()


def compiler_version() -> str:
    try:
        out = subprocess.run(["g++", "--version"], capture_output=True, text=True, timeout=20)
        return out.stdout.splitlines()[0].strip()
    except Exception as exc:
        return f"unknown ({exc})"


def compile_source(sandbox: Sandbox, workdir: Path, source: Path, binary: Path,
                   flags: list[str]) -> tuple[bool, str, float]:
    """Compile source into binary. Return (ok, diagnostics, elapsed_ms)."""
    argv = ["g++", *flags, source.name, "-o", binary.name]
    start = time.perf_counter()
    res = sandbox.run(argv, workdir, timeout=COMPILE_TIMEOUT_S,
                      memory_mb=COMPILE_MEMORY_MB, output_bytes=8 * 1024 * 1024)
    elapsed = (time.perf_counter() - start) * 1000
    ok = res.returncode == 0 and binary.exists()
    diag = (res.stderr or "").replace(str(workdir) + os.sep, "").strip()
    return ok, diag, elapsed


def _child_peak_rss_kb() -> int | None:
    """Return the largest child peak RSS seen so far, in kilobytes.

    `getrusage(RUSAGE_CHILDREN).ru_maxrss` is a running maximum over all
    waited-for children. Only one child runs at a time, so the value after a
    run is that run's peak, unless an earlier child used more memory.
    """
    if os.name != "posix":
        return None
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    except Exception:
        return None
    return int(value) if value else None


def read_problems() -> list[dict]:
    path = BANK_DIR / "problems.json"
    return json.loads(path.read_text(encoding="utf-8"))["problems"]


def list_wsl_distros() -> list[str]:
    """Return the installed WSL distribution names, with no stray characters."""
    if not shutil.which("wsl"):
        return []
    try:
        out = subprocess.run(["wsl", "-l", "-q"], capture_output=True, timeout=30).stdout
    except Exception:
        return []
    text = out.decode("utf-16-le", errors="replace") if b"\x00" in out else out.decode(
        "utf-8", errors="replace")
    names = []
    for line in text.replace("\x00", "").splitlines():
        name = line.strip().strip("\ufeff")
        if name:
            names.append(name)
    return names


def pick_wsl_distro(names: list[str]) -> str | None:
    """Pick a WSL distribution that can build C++.

    `TRACELEARN_WSL_DISTRO` wins. Docker Desktop's utility distributions have
    no bash or g++, so they are skipped; the first one with g++ is chosen.
    """
    wanted = os.environ.get("TRACELEARN_WSL_DISTRO")
    if wanted:
        return wanted
    for name in names:
        if name.lower().startswith("docker-desktop"):
            continue
        try:
            probe = subprocess.run(["wsl", "-d", name, "--", "sh", "-c", "command -v g++"],
                                   capture_output=True, timeout=60)
        except Exception:
            continue
        if probe.returncode == 0:
            return name
    return None


# ---------------------------------------------------------------------------
# limit probes
# ---------------------------------------------------------------------------
MEMORY_PROBE = r"""
#include <iostream>
#include <vector>
int main() {
    // Ask for 512 MB. The sandbox limit is 256 MB.
    std::vector<char> block(512ULL * 1024 * 1024, 1);
    // Read every page, so the optimiser cannot delete the allocation.
    unsigned long long sum = 0;
    for (std::size_t i = 0; i < block.size(); i += 4096) sum += block[i];
    std::cout << sum << "\n";
    return 0;
}
"""

LOOP_PROBE = r"""
#include <iostream>
int main() {
    // This loop never terminates. The wall-clock limit must stop it.
    unsigned long long counter = 0;
    while (true) { ++counter; }
    return 0;
}
"""


def run_limit_probes(sandbox: Sandbox, report: Report, workdir: Path) -> None:
    """Prove that the 256 MB limit and the 2000 ms wall clock actually fire."""
    # --- memory probe ---
    src = workdir / "mem_probe.cpp"
    src.write_text(MEMORY_PROBE, encoding="utf-8")
    ok, diag, _ = compile_source(sandbox, workdir, src, workdir / "mem_probe", COMPILE_FLAGS)
    report.add("probe memory compiles", ok, diag[:200])
    if ok:
        start = time.perf_counter()
        res = sandbox.run(["./mem_probe"], workdir, timeout=TIME_LIMIT_MS / 1000,
                          memory_mb=MEMORY_LIMIT_MB)
        elapsed = (time.perf_counter() - start) * 1000
        stopped = res.returncode != 0 or res.timed_out or res.memory_limit_hit
        report.add("probe 512MB allocation is stopped by the 256MB limit", stopped,
                   f"returncode={res.returncode} timed_out={res.timed_out} "
                   f"memory_limit_hit={res.memory_limit_hit} elapsed_ms={elapsed:.0f}")
        report.limit_probes["memory"] = {
            "requested_mb": 512, "limit_mb": MEMORY_LIMIT_MB,
            "returncode": res.returncode, "timed_out": res.timed_out,
            "memory_limit_hit": res.memory_limit_hit,
            "elapsed_ms": round(elapsed, 1),
            "stderr_tail": (res.stderr or "")[-300:],
        }

    # --- wall-clock probe ---
    src = workdir / "loop_probe.cpp"
    src.write_text(LOOP_PROBE, encoding="utf-8")
    ok, diag, _ = compile_source(sandbox, workdir, src, workdir / "loop_probe", COMPILE_FLAGS)
    report.add("probe infinite loop compiles", ok, diag[:200])
    if ok:
        start = time.perf_counter()
        res = sandbox.run(["./loop_probe"], workdir, timeout=TIME_LIMIT_MS / 1000,
                          memory_mb=MEMORY_LIMIT_MB)
        elapsed = (time.perf_counter() - start) * 1000
        report.add(
            "probe infinite loop is stopped at the 2000ms wall clock",
            res.timed_out and elapsed < 3500,
            f"timed_out={res.timed_out} elapsed_ms={elapsed:.0f} returncode={res.returncode}",
        )
        report.limit_probes["wall_clock"] = {
            "limit_ms": TIME_LIMIT_MS, "timed_out": res.timed_out,
            "elapsed_ms": round(elapsed, 1), "returncode": res.returncode,
        }


# ---------------------------------------------------------------------------
# per-problem verification
# ---------------------------------------------------------------------------
def verify_problem(sandbox: Sandbox, report: Report, problem: dict, *,
                   sanitize: bool) -> dict:
    pid = problem["id"]
    entry: dict = {
        "problem_id": pid,
        "misconception": problem["primary_misconception_id"],
        "title": problem["title"],
        "difficulty": problem["difficulty"],
        "tests": [],
        "variant": {},
        "compile": {},
        "sanitizer": {},
        "examples": [],
    }
    with tempfile.TemporaryDirectory(prefix=f"tl-{pid}-") as tmp_name:
        workdir = Path(tmp_name)
        src = workdir / f"{pid}.cpp"
        src.write_text(problem["reference_solution_source"], encoding="utf-8")
        binary = workdir / pid

        # 1. compile with the mandated flags
        ok, diag, ms = compile_source(sandbox, workdir, src, binary, COMPILE_FLAGS)
        entry["compile"] = {"flags": COMPILE_FLAGS, "ok": ok, "diagnostics": diag,
                            "elapsed_ms": round(ms, 1)}
        report.add(f"{pid} compiles with -O2 -Wall -Wextra", ok, diag[:200])
        report.add(f"{pid} compiles without warnings", ok and not diag.strip(),
                   (diag.strip().splitlines() or ["no warnings"])[0][:160])

        # compile with the backend flags, to prove the two flag sets agree
        ok_b, diag_b, _ = compile_source(sandbox, workdir, src, workdir / f"{pid}_backend",
                                         BACKEND_FLAGS)
        entry["compile"]["backend_flags_ok"] = ok_b
        entry["compile"]["backend_flag_diagnostics"] = diag_b
        report.add(f"{pid} compiles with the backend flags too", ok_b, diag_b[:160])

        if not ok:
            return entry

        # 2-4. run, compare, repeat
        for tc in problem["test_cases"]:
            stdin_data = tc["stdin"]
            expected = tc["expected_output"]
            limit_ms = tc.get("time_limit_ms") or TIME_LIMIT_MS
            memory_mb = tc.get("memory_limit_mb") or MEMORY_LIMIT_MB
            runs = []
            started = time.perf_counter()
            for _ in range(DETERMINISM_RUNS):
                res = sandbox.run([f"./{pid}"], workdir, stdin_data=stdin_data,
                                  timeout=limit_ms / 1000, memory_mb=memory_mb)
                runs.append(res)
            elapsed_ms = (time.perf_counter() - started) * 1000 / DETERMINISM_RUNS
            first = runs[0]
            passed = (first.returncode == 0 and not first.timed_out
                      and tokens(first.stdout) == tokens(expected))
            stable = all(tokens(r.stdout) == tokens(first.stdout) for r in runs)
            report.add(
                f"{tc['id']} {tc['db_type']} {tc['name']} passes and is deterministic",
                passed and stable,
                f"expected={expected!r} actual={first.stdout.strip()!r} "
                f"rc={first.returncode} timed_out={first.timed_out} stable={stable} "
                f"runtime_ms={elapsed_ms:.1f} peak_rss_kb={_child_peak_rss_kb()}")
            entry["tests"].append({
                "id": tc["id"], "test_type": tc["db_type"],
                "diagnostic_tag": tc.get("diagnostic_tag"),
                "diagnostic_trait": tc.get("diagnostic_trait"),
                "is_boundary": bool(tc.get("is_boundary", False)),
                "passed": bool(passed and stable),
                "expected": expected, "actual": first.stdout.strip(),
                "returncode": first.returncode, "timed_out": first.timed_out,
                "runtime_ms": round(elapsed_ms, 2), "stable": stable,
                "peak_child_rss_kb": _child_peak_rss_kb(),
            })

        # 5. sanitizer build
        if sanitize:
            ok_s, diag_s, _ = compile_source(sandbox, workdir, src, workdir / f"{pid}_asan",
                                             SANITIZE_FLAGS)
            ok_u, diag_u, _ = compile_source(sandbox, workdir, src, workdir / f"{pid}_ubsan",
                                             UBSAN_FLAGS)
            clean = True
            details = []
            if ok_s:
                for tc in problem["test_cases"]:
                    stdin_data = tc["stdin"]
                    res = sandbox.run([f"./{pid}_asan"], workdir, stdin_data=stdin_data,
                                      timeout=TIME_LIMIT_MS / 1000, memory_mb=None,
                                      apply_memory_limit=False)
                    bad = ("ERROR: AddressSanitizer" in (res.stderr or "")
                           or "runtime error:" in (res.stderr or "")
                           or "ERROR: LeakSanitizer" in (res.stderr or ""))
                    if bad:
                        clean = False
                        details.append(f"{tc['id']}: {(res.stderr or '')[:200]}")
            else:
                clean = False
                details.append(diag_s[:200])
            entry["sanitizer"] = {"built": ok_s, "clean": clean, "details": details}
            report.add(f"{pid} runs clean under AddressSanitizer and UBSan", clean,
                       "; ".join(details)[:200])

            ub_clean = True
            ub_details = []
            if ok_u:
                for tc in problem["test_cases"]:
                    stdin_data = tc["stdin"]
                    res = sandbox.run([f"./{pid}_ubsan"], workdir, stdin_data=stdin_data,
                                      timeout=TIME_LIMIT_MS / 1000,
                                      memory_mb=MEMORY_LIMIT_MB)
                    if "runtime error:" in (res.stderr or ""):
                        ub_clean = False
                        ub_details.append(f"{tc['id']}: {(res.stderr or '')[:200]}")
            else:
                ub_clean = False
                ub_details.append(diag_u[:200])
            entry["sanitizer"]["ubsan_under_judged_limit"] = {
                "built": ok_u, "clean": ub_clean, "details": ub_details}
            report.add(f"{pid} runs clean under UBSan at the 256MB judged limit",
                       ub_clean, "; ".join(ub_details)[:200])

    # 6. misconception variant
    entry["variant"] = _verify_variant(sandbox, report, problem)

    # 8. examples must match the visible test cases
    examples_ok, detail = _check_examples(problem)
    report.add(f"{pid} public examples match the visible test cases", examples_ok, detail)
    entry["examples"] = {"passed": examples_ok, "detail": detail}
    return entry


def _check_examples(problem: dict) -> tuple[bool, str]:
    """Check that each public example equals the visible test case."""
    visible = [c for c in problem["test_cases"] if c["db_type"] == "visible"]
    problems = []
    for example in problem["examples"]:
        match = None
        for case in visible:
            if case["stdin"] == example["input"]:
                match = case
                break
        if match is None:
            problems.append(f"no visible test holds the input of example {example['example_number']}")
            continue
        if match["expected_output"] != example["expected_output"]:
            problems.append(
                f"example {example['example_number']} output differs from {match['id']}")
    return (not problems), "; ".join(problems)[:200]


def _verify_variant(sandbox: Sandbox, report: Report, problem: dict) -> dict:
    """Compile and run the misconception variant. It must fail somewhere."""
    name = problem.get("misconception_variant_id")
    source = problem.get("misconception_variant_source")
    result: dict = {"variant": name, "misconception": problem["primary_misconception_id"],
                    "compiled": False, "failed_tests": [], "timed_out_tests": [],
                    "outcome": "not_run"}
    if not name or not source:
        result["outcome"] = "no_variant"
        return result

    with tempfile.TemporaryDirectory(prefix="tl-var-") as tmp_name:
        workdir = Path(tmp_name)
        src = workdir / name
        src.write_text(source, encoding="utf-8")
        binary = workdir / "variant"
        ok, diag, _ = compile_source(sandbox, workdir, src, binary, COMPILE_FLAGS)
        result["compiled"] = ok
        result["compile_diagnostics"] = diag[:600]
        if not ok:
            result["outcome"] = "compile_error"
            report.add(f"{name} is rejected by the compiler (compile_error)", True,
                       (diag.strip().splitlines() or [""])[0][:170])
            return result

        timed_out_any = False
        for tc in problem["test_cases"]:
            stdin_data = tc["stdin"]
            expected = tc["expected_output"]
            res = sandbox.run(["./variant"], workdir, stdin_data=stdin_data,
                              timeout=TIME_LIMIT_MS / 1000, memory_mb=MEMORY_LIMIT_MB)
            failed = (res.returncode != 0 or res.timed_out
                      or tokens(res.stdout) != tokens(expected))
            if failed:
                result["failed_tests"].append(tc["id"])
                if "first_failure" not in result:
                    result["first_failure"] = {
                        "test_case_id": tc["id"],
                        "diagnostic_trait": tc.get("diagnostic_trait"),
                        "expected": expected,
                        "actual": res.stdout.strip(),
                        "returncode": res.returncode,
                        "timed_out": res.timed_out,
                    }
                if res.timed_out:
                    timed_out_any = True
                    result["timed_out_tests"].append(tc["id"])

        failed_variant = bool(result["failed_tests"])
        result["outcome"] = ("timeout" if timed_out_any and failed_variant
                             else ("wrong_output" if failed_variant else "passed_unexpectedly"))
        report.add(f"{name} fails the tests for {problem['primary_misconception_id']}",
                   failed_variant,
                   f"failed {len(result['failed_tests'])} of "
                   f"{len(problem['test_cases'])}: "
                   f"{','.join(result['failed_tests'][:6])} "
                   f"outcome={result['outcome']}")
    return result


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run_all(sandbox: Sandbox, report: Report, *, sanitize: bool, only: str | None) -> None:
    problems = read_problems()
    if only:
        problems = [p for p in problems if p["id"] == only.upper()]
        if not problems:
            raise SystemExit(f"No problem with id {only}")
    with tempfile.TemporaryDirectory(prefix="tl-probes-") as tmp_name:
        run_limit_probes(sandbox, report, Path(tmp_name))
    for problem in problems:
        report.problems[problem["id"]] = verify_problem(
            sandbox, report, problem, sanitize=sanitize)


def build_environment(sandbox: Sandbox) -> dict:
    return {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "compiler": compiler_version(),
        "sandbox_engine": sandbox.engine,
        "sandbox_status": sandbox.status(),
        "compile_flags": COMPILE_FLAGS,
        "sanitize_flags": SANITIZE_FLAGS,
        "ubsan_flags": UBSAN_FLAGS,
        "time_limit_ms": TIME_LIMIT_MS,
        "memory_limit_mb": MEMORY_LIMIT_MB,
        "determinism_runs": DETERMINISM_RUNS,
        "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def write_export(report: Report) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "environment": report.environment,
        "summary": {
            "checks": len(report.checks),
            "passed": sum(1 for c in report.checks if c.passed),
            "failed": len(report.failures),
        },
        "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail}
                   for c in report.checks],
        "problems": report.problems,
        "limit_probes": report.limit_probes,
    }
    path = EXPORT_DIR / "verification_report.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-sanitize", action="store_true",
                        help="Skip the AddressSanitizer and UBSan build.")
    parser.add_argument("--only", default="", help="Verify one problem id, for example CP25.")
    parser.add_argument("--linux", action="store_true",
                        help="Internal. Run in a POSIX environment.")
    args = parser.parse_args(argv)

    # On a non-POSIX host, hand the work to WSL, where g++ and prlimit exist.
    if os.name != "posix" and not args.linux:
        names = list_wsl_distros()
        if not names:
            print("FAIL: no g++ on PATH and no WSL distribution. Install a C++ toolchain.")
            return 1
        distro = pick_wsl_distro(names)
        if distro is None:
            print("FAIL: no WSL distribution with g++. Set TRACELEARN_WSL_DISTRO.")
            return 1
        drive, _, rest = str(ROOT).partition(":")
        wsl_root = f"/mnt/{drive.lower()}{rest.replace(chr(92), '/')}"
        inner = ["python3", f"{wsl_root}/scripts/verify_cpp_diagnostics.py", "--linux"]
        if args.no_sanitize:
            inner.append("--no-sanitize")
        if args.only:
            inner += ["--only", args.only]
        script = " ".join(f"'{p}'" for p in inner)
        proc = subprocess.run(["wsl", "-d", distro, "--", "bash", "-lc", script])
        return proc.returncode

    sandbox = Sandbox()
    try:
        sandbox.start()
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    report = Report()
    report.environment = build_environment(sandbox)
    print(f"compiler      : {report.environment['compiler']}")
    print(f"sandbox engine: {sandbox.engine}  {report.environment['sandbox_status']}")
    print(f"limits        : {TIME_LIMIT_MS} ms wall clock, {MEMORY_LIMIT_MB} MB memory")
    print()

    run_all(sandbox, report, sanitize=not args.no_sanitize, only=args.only)

    print("\n=== RESULT ===")
    for check in report.checks:
        if not check.passed:
            print(f"FAIL  {check.name}  {check.detail}")
    passed = sum(1 for c in report.checks if c.passed)
    print(f"checks: {passed} passed, {len(report.failures)} failed, {len(report.checks)} total")
    export = write_export(report)
    print(f"report: {export.relative_to(ROOT)}")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
