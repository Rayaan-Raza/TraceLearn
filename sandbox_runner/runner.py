"""The one execution contract every lane imports:

    run_submission(code, lang, tests) -> {"compile", "warnings", "tests", "runtime", ...}

``tests`` is a list of ``{"input": str, "output": str}`` dicts (or ``TestCase``).
The result is plain JSON. Field meanings are documented in
``sandbox_runner/README.md``; ``null`` means "not measured", never 0.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from . import parsers
from .compare import compare_output
from .config import (
    ASAN_OPTIONS, LANG_COMPILER, LANG_STD, SANDBOX_VERSION, SANITIZER_FLAGS,
    UBSAN_OPTIONS, VALGRIND_EXIT_CODE, VALGRIND_FLAGS, WARNING_FLAGS, RunConfig,
    normalize_lang,
)
from .pch import pch_include_dir
from .process import run_process
from .toolchain import toolchain_id


@dataclass(frozen=True)
class TestCase:
    input: str
    output: str


def _as_tests(tests) -> list[dict]:
    out = []
    for t in tests:
        if isinstance(t, TestCase):
            out.append({"input": t.input, "output": t.output})
        else:
            out.append({"input": t["input"], "output": t["output"]})
    return out


def cache_key(code: str, lang: str, tests: list[dict], cfg: RunConfig) -> str:
    h = hashlib.sha256()
    h.update(json.dumps([normalize_lang(lang), code, tests, cfg.fingerprint(), toolchain_id()],
                        sort_keys=True).encode())
    return h.hexdigest()


# ------------------------------------------------------------------ compile --

def _compile(lang: str, src: str, out: str, flags: list[str], workdir: str, cfg: RunConfig,
             tag: str) -> dict:
    cc = LANG_COMPILER[lang]
    extra = []
    if lang == "cpp" and cfg.use_pch:
        with open(src, encoding="utf-8", errors="replace") as f:
            if "bits/stdc++.h" in f.read():
                inc = pch_include_dir(LANG_STD[lang], flags)
                if inc:
                    extra = ["-I", inc]
    argv = [cc, f"-std={LANG_STD[lang]}", *flags, *extra, src, "-o", out, "-lm"]
    limits = dataclasses.replace(cfg.limits, memory_mb=max(cfg.limits.memory_mb, 2048))
    r = run_process(argv, stdin_path=None, workdir=workdir, timeout_s=cfg.limits.compile_time_s,
                    limits=limits, cap_memory=True, isolate_network=cfg.network_isolation,
                    tag=tag)
    ok = r["rc"] == 0 and os.path.exists(out)
    return {"ok": ok, "rc": r["rc"], "timed_out": r["timed_out"], "seconds": r["seconds"],
            "stderr": r["stderr"]}


# -------------------------------------------------------------------- tests --

def _write_inputs(tests: list[dict], workdir: str) -> list[str]:
    paths = []
    for i, t in enumerate(tests):
        p = os.path.join(workdir, f"in{i}.txt")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(t["input"])
        paths.append(p)
    return paths


def _classify(r: dict, cmp: dict | None) -> str:
    if r["timed_out"]:
        return "timeout"
    if r["output_limit"]:
        return "output_limit"
    if r["signal"] is not None or (r["rc"] not in (0, None) and cmp is None):
        return "crash"
    if r["rc"] != 0:
        # non-zero exit with output: judge the output, but remember the exit code
        return cmp["status"] if cmp and cmp["status"] != "pass" else "nonzero_exit"
    return cmp["status"] if cmp else "crash"


def _run_tests(binary: str, tests: list[dict], inputs: list[str], workdir: str,
               cfg: RunConfig) -> list[dict]:
    results = []
    timeouts = 0
    for i, t in enumerate(tests):
        if timeouts >= cfg.stop_after_timeouts:
            results.append({"idx": i, "status": "skipped"})
            continue
        r = run_process([binary], stdin_path=inputs[i], workdir=workdir,
                        timeout_s=cfg.limits.time_s, limits=cfg.limits,
                        isolate_network=cfg.network_isolation, tag=f"t{i}")
        crashed = r["signal"] is not None or r["timed_out"]
        cmp = None if crashed else compare_output(r["stdout"], t["output"])
        status = _classify(r, cmp)
        if status == "timeout":
            timeouts += 1
        item = {"idx": i, "status": status, "rc": r["rc"], "signal": r["signal"],
                "seconds": r["seconds"], "stdout_head": r["stdout"][: cfg.keep_stdout_bytes],
                "stderr_head": r["stderr"][:500], "flaky": False}
        if cmp and status != "pass":
            item["diff"] = {k: v for k, v in cmp.items() if k != "status"}
        if cfg.double_run and status not in ("timeout", "skipped"):
            r2 = run_process([binary], stdin_path=inputs[i], workdir=workdir,
                             timeout_s=cfg.limits.time_s, limits=cfg.limits,
                             isolate_network=cfg.network_isolation, tag=f"t{i}b")
            if r2["stdout"] != r["stdout"] or r2["signal"] != r["signal"] or r2["timed_out"]:
                item["flaky"] = True
        results.append(item)
    return results


# ---------------------------------------------------------------- sanitizer --

def _pick(tests_results: list[dict], mode: str) -> list[int]:
    failing = [r["idx"] for r in tests_results if r.get("status") not in ("pass", "skipped")]
    if mode == "all":
        return [r["idx"] for r in tests_results if r.get("status") != "skipped"] or [0]
    if mode == "failing":
        return failing
    # first_failing
    if failing:
        return failing[:1]
    return [0] if tests_results else []


def _sanitizer_pass(lang, src, workdir, tests, inputs, plain_results, cfg) -> dict:
    out = os.path.join(workdir, "prog_san")
    c = _compile(lang, src, out, SANITIZER_FLAGS, workdir, cfg, "csan")
    block = {"ran": False, "compiled": c["ok"], "tests_run": 0, "reports": [],
             "kinds": {}, "first_report": None, "complete": False}
    if not c["ok"]:
        block["compile_stderr"] = c["stderr"][:500]
        return block
    block["ran"] = True
    env = {"ASAN_OPTIONS": ASAN_OPTIONS, "UBSAN_OPTIONS": UBSAN_OPTIONS}
    timeout = cfg.limits.time_s * cfg.limits.sanitizer_time_factor
    with_reports = 0
    for i in _pick(plain_results, cfg.sanitizer_tests):
        r = run_process([out], stdin_path=inputs[i], workdir=workdir, timeout_s=timeout,
                        limits=cfg.limits, cap_memory=False, env=env,
                        isolate_network=cfg.network_isolation, tag=f"s{i}")
        block["tests_run"] += 1
        asan = parsers.parse_asan(r["stderr"])
        ub = parsers.parse_ubsan(r["stderr"])
        reps = ([asan] if asan else []) + ub
        for rep in reps:
            rep["test_idx"] = i
        if reps:
            with_reports += 1
            block["reports"].extend(reps)
        if r["timed_out"]:
            block.setdefault("timeouts", []).append(i)
        if with_reports >= cfg.sanitizer_stop_after_reports:
            break
    block["kinds"] = dict(Counter(f"{x['tool']}:{x['kind']}" for x in block["reports"]))
    block["first_report"] = block["reports"][0] if block["reports"] else None
    block["complete"] = True
    return block


def _valgrind_pass(lang, src, workdir, inputs, plain_results, cfg) -> dict:
    block = {"ran": False, "available": shutil.which("valgrind") is not None,
             "complete": False}
    if not block["available"]:
        return block
    out = os.path.join(workdir, "prog_vg")
    c = _compile(lang, src, out, VALGRIND_FLAGS, workdir, cfg, "cvg")
    if not c["ok"]:
        block["compile_ok"] = False
        return block
    idxs = _pick(plain_results, cfg.valgrind_tests)
    kinds: dict = {}
    errors = 0
    timeouts = []
    for i in idxs:
        log = os.path.join(workdir, f"vg{i}.log")
        argv = ["valgrind", "--tool=memcheck", f"--error-exitcode={VALGRIND_EXIT_CODE}",
                "--track-origins=yes", "--leak-check=no", f"--log-file={log}",
                f"--main-stacksize={cfg.limits.stack_mb * 1024 * 1024}", out]
        r = run_process(argv, stdin_path=inputs[i], workdir=workdir,
                        timeout_s=cfg.limits.time_s * cfg.limits.valgrind_time_factor,
                        limits=cfg.limits, cap_memory=False,
                        isolate_network=cfg.network_isolation, tag=f"v{i}")
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                text = f.read(cfg.limits.output_bytes)
        except FileNotFoundError:
            text = ""
        if r["timed_out"]:
            timeouts.append(i)
        rep = parsers.parse_valgrind(text)
        errors += rep["error_count"] or 0
        for k, v in rep["kinds"].items():
            e = kinds.setdefault(k, {"count": 0, "line": v["line"], "test_idx": i})
            e["count"] += v["count"]
    block.update({"ran": True, "tests_run": len(idxs), "tests": idxs, "kinds": kinds,
                  "error_count": errors,
                  "uninit": any(k.startswith("uninit") for k in kinds),
                  "timeouts": timeouts, "complete": not timeouts})
    return block


# --------------------------------------------------------------------- main --

def _summarize_tests(results: list[dict]) -> dict:
    counted = [r for r in results if not r.get("flaky") and r["status"] != "skipped"]
    statuses = Counter(r["status"] for r in counted)
    passed = statuses.get("pass", 0)
    lenient = passed + statuses.get("presentation", 0)
    first_failed = next((r["idx"] for r in counted if r["status"] != "pass"), None)
    return {
        "total": len(counted),
        "passed": passed,
        "passed_lenient": lenient,
        "failed": len(counted) - passed,
        "status_counts": dict(statuses),
        "flaky": [r["idx"] for r in results if r.get("flaky")],
        "skipped": [r["idx"] for r in results if r["status"] == "skipped"],
        "first_failed": first_failed,
        "all_passed": len(counted) > 0 and passed == len(counted),
        "results": results,
    }


def run_submission(code: str, lang: str, tests, cfg: RunConfig | None = None, *,
                   cache_dir: str | None = None, backend: str = "local",
                   image: str | None = None) -> dict:
    """Compile ``code`` and run it against ``tests``. See module docstring."""
    cfg = cfg or RunConfig()
    lang = normalize_lang(lang)
    tests = _as_tests(tests)
    key = cache_key(code, lang, tests, cfg)
    if cache_dir:
        cpath = os.path.join(cache_dir, key[:2], key + ".json")
        if os.path.exists(cpath):
            with open(cpath, encoding="utf-8") as f:
                res = json.load(f)
            res["cache_hit"] = True
            return res
    if backend == "docker":
        from .docker_backend import run_in_docker
        res = run_in_docker(code, lang, tests, cfg, image=image)
    elif backend == "local":
        res = _run_local(code, lang, tests, cfg)
    else:
        raise ValueError(f"unknown backend {backend!r}")
    res["cache_key"] = key
    res["backend"] = backend
    if cache_dir:
        os.makedirs(os.path.dirname(cpath), exist_ok=True)
        tmp = cpath + f".tmp{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(res, f)
        os.replace(tmp, cpath)
    res["cache_hit"] = False
    return res


def _run_local(code: str, lang: str, tests: list[dict], cfg: RunConfig) -> dict:
    t0 = time.monotonic()
    workdir = tempfile.mkdtemp(prefix="sbx-")
    os.chmod(workdir, 0o777)
    try:
        src_name = "main.cpp" if lang == "cpp" else "main.c"
        src = os.path.join(workdir, src_name)
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)
        os.chmod(src, 0o644)
        prog = os.path.join(workdir, "prog")
        comp = _compile(lang, src, prog, WARNING_FLAGS, workdir, cfg, "cplain")
        diag = parsers.parse_compiler_output(comp["stderr"], src_name)
        result = {
            "sandbox_version": SANDBOX_VERSION,
            "toolchain": toolchain_id(),
            "config_fingerprint": cfg.fingerprint(),
            "lang": lang,
            "compile": {"ok": comp["ok"], "rc": comp["rc"], "timed_out": comp["timed_out"],
                        "seconds": comp["seconds"], "errors": diag["errors"][:20],
                        "stderr_head": comp["stderr"][:2000]},
            "warnings": {"count_by_flag": diag["count_by_flag"],
                         "items": diag["warnings"][:50], "total": len(diag["warnings"])},
            "tests": None,
            "runtime": None,
        }
        if not comp["ok"]:
            result["branch"] = "compile_error"
            return result
        inputs = _write_inputs(tests, workdir)
        plain = _run_tests(prog, tests, inputs, workdir, cfg)
        tsum = _summarize_tests(plain)
        result["tests"] = tsum
        san = (_sanitizer_pass(lang, src, workdir, tests, inputs, plain, cfg)
               if cfg.sanitizer_pass else {"ran": False, "complete": False})
        vg = (_valgrind_pass(lang, src, workdir, inputs, plain, cfg)
              if cfg.valgrind_pass else {"ran": False, "complete": False})
        statuses = tsum["status_counts"]
        signals = sorted({r["signal"] for r in plain if r.get("signal")})
        first_asan = next((x for x in san.get("reports", []) if x["tool"] == "asan"), None)
        any_crash = statuses.get("crash", 0) > 0
        any_timeout = statuses.get("timeout", 0) > 0
        result["runtime"] = {
            "any_crash": any_crash,
            "any_timeout": any_timeout,
            "signals": signals,
            "max_seconds": max((r.get("seconds") or 0) for r in plain) if plain else None,
            "stack_overflow": parsers.looks_like_stack_overflow(None, first_asan, vg),
            "sanitizer": san,
            "valgrind": vg,
        }
        if tsum["all_passed"]:
            branch = "all_pass"
        elif any_timeout and not any_crash and tsum["passed"] == 0 and not san.get("reports"):
            branch = "timeout_only"
        else:
            branch = "failing"
        result["branch"] = branch
        result["seconds_total"] = round(time.monotonic() - t0, 3)
        return result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _job(args):
    code, lang, tests, cfg, cache_dir, backend, image = args
    try:
        return run_submission(code, lang, tests, cfg, cache_dir=cache_dir, backend=backend,
                              image=image)
    except Exception as exc:  # one bad row must not kill a bulk run
        return {"error": f"{type(exc).__name__}: {exc}"}


def run_many(jobs, cfg: RunConfig | None = None, *, workers: int | None = None,
             cache_dir: str | None = None, backend: str = "local", image: str | None = None):
    """Run ``jobs`` = iterable of (code, lang, tests) in parallel; yields results in order."""
    cfg = cfg or RunConfig()
    workers = workers or max(1, (os.cpu_count() or 2))
    args = [(c, l, t, cfg, cache_dir, backend, image) for c, l, t in jobs]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        yield from ex.map(_job, args, chunksize=1)
