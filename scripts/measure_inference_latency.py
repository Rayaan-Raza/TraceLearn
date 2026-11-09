"""Measure what each way of getting model features costs per submission.

    python scripts/measure_inference_latency.py --raw <Datasets_RAW> [--n 40] [--seed 20261108]

Feeds the runtime-features decision (docs/decisions/inference_runtime_features.md).
On a seeded sample of failing CodeStream C/C++ submissions it times, with no
cache:

* sandbox_runner in four configurations: full (warnings, tests twice,
  ASan/UBSan, Valgrind), without Valgrind, compile + tests + warnings only,
  and that with a single test run;
* one warnings-only g++ call with the training flags (``WARNING_FLAGS``,
  which include ``-O2``: ``-Wmaybe-uninitialized`` only fires with the
  optimizer on, so ``-fsyntax-only`` would miss it);
* the backend's current warnings call (``-fsyntax-only -Wall -Wextra``);
* static + semantics feature extraction from the source.

Writes ``reports/inference_latency.json``. Numbers depend on the machine,
which the report records.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from codestream_common import DATASET_DIR, find_raw, load_problems, load_submissions  # noqa: E402

from sandbox_runner import RunConfig, run_submission  # noqa: E402
from sandbox_runner.config import WARNING_FLAGS  # noqa: E402
from tracelearn_features.extractor import _compute_semantics, _compute_static  # noqa: E402

EXEC_PATH = DATASET_DIR / "cache" / "codestream_exec.jsonl"
OUT = DATASET_DIR / "reports" / "inference_latency.json"

CONFIGS = {
    "sandbox_runner_full": RunConfig(),
    "sandbox_runner_no_valgrind": RunConfig(valgrind_pass=False),
    "sandbox_runner_compile_tests_warnings": RunConfig(sanitizer_pass=False, valgrind_pass=False),
    "sandbox_runner_compile_tests_warnings_single_run": RunConfig(sanitizer_pass=False, valgrind_pass=False,
                                                                  double_run=False),
}


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def summary(xs: list[float]) -> dict:
    return {"n": len(xs), "p50_s": round(pct(xs, 50), 3), "p95_s": round(pct(xs, 95), 3),
            "max_s": round(max(xs), 3), "mean_s": round(statistics.mean(xs), 3)}


def time_gcc(code: str, lang: str, flags: list[str], syntax_only: bool) -> float:
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "m.cpp" if lang == "cpp" else "m.c")
        Path(src).write_text(code, encoding="utf-8")
        cmd = ["g++" if lang == "cpp" else "gcc", *flags, src]
        cmd += ["-fsyntax-only"] if syntax_only else ["-c", "-o", os.devnull]
        t = time.perf_counter()
        subprocess.run(cmd, capture_output=True, timeout=60)
        return time.perf_counter() - t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261108)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    raw = find_raw(a.raw)
    probs = load_problems(raw)
    subs = {s.submission_id: s for s in load_submissions(raw)}
    rows = [json.loads(line) for line in open(EXEC_PATH, encoding="utf-8")]
    failing = sorted(r["submission_id"] for r in rows
                     if r["result"]["compile"]["ok"] and not r["result"]["tests"]["all_passed"])
    sample = random.Random(a.seed).sample(failing, min(a.n, len(failing)))
    times: dict[str, list[float]] = {k: [] for k in CONFIGS}
    times |= {"warnings_compile_training_flags": [], "warnings_backend_fsyntax_only": [],
              "static_semantics_extraction": []}
    for sid in sample:
        s = subs[sid]
        tests = probs[s.problem_id].tests
        for k, cfg in CONFIGS.items():
            t = time.perf_counter()
            run_submission(s.code, s.lang, tests, cfg)
            times[k].append(time.perf_counter() - t)
        times["warnings_compile_training_flags"].append(time_gcc(s.code, s.lang, WARNING_FLAGS, False))
        times["warnings_backend_fsyntax_only"].append(time_gcc(s.code, s.lang, ["-Wall", "-Wextra"], True))
        t = time.perf_counter()
        _compute_static(s.code, s.lang)
        _compute_semantics(s.code)
        times["static_semantics_extraction"].append(time.perf_counter() - t)
    report = {"sample": {"source": "CodeStream failing C/C++ (compiled, >=1 test failed)", "n": len(sample),
                         "seed": a.seed, "pool": len(failing)},
              "machine": {"cpus": os.cpu_count(), "processor": platform.processor() or platform.machine(),
                          "python": platform.python_version()},
              "results": {k: summary(v) for k, v in times.items()}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["results"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
