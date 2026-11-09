"""Build execution-verified student-style synthetic rows for the C++ bank problems.

    wsl python3 scripts/build_student_synthetic.py [--workers 8]

Reads `student_specs_a.py` / `student_specs_b.py` (two beginner-style base programs
per bank problem and single-edit bugs), and keeps an edit only if, by execution
against the problem's own tests (visible, hidden and diagnostic):

1. the base program passes every test (so it is a correct solution);
2. the edited program compiles and fails at least one test (the bug is visible);
3. the single inverse edit restores the passing base (so the bug is sufficient).

Writes `annotations/tier0b_student_synthetic.jsonl` (rows in the tier0 shape, label
source `synthetic`, `verified_by_execution`), the bank problems' train-only cluster
table `splits/bank_clusters.csv`, and `reports/student_synthetic_report.md`.

Only bank problems are used. CodeStream and PROGPedia problems of the held-out
clusters are never read here, so nothing built from their statements can leak into
training.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DS = ROOT / "data" / "misconception_dataset"
BANK = ROOT / "data" / "cpp_diagnostics" / "problems.json"
OUT = DS / "annotations" / "tier0b_student_synthetic.jsonl"
CLUSTERS = DS / "splits" / "bank_clusters.csv"
PROOFS = DS / "annotations" / "mutant_proofs"
REPORT = DS / "reports" / "student_synthetic_report.md"
TIMEOUT = 3.0


def tokens(text: str) -> list[str]:
    return text.split()


def run_tests(code: str, tests: list[dict[str, str]]) -> dict[str, Any]:
    """Compile with the dataset's warning flags, then run every test."""
    with tempfile.TemporaryDirectory() as tmp:
        src, exe = Path(tmp) / "a.cpp", Path(tmp) / "a.out"
        src.write_text(code, encoding="utf-8")
        comp = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(src), "-o", str(exe)],
                              capture_output=True, text=True, timeout=60)
        if comp.returncode != 0:
            return {"compiled": False, "passed": 0, "total": len(tests), "warnings": comp.stderr[-2000:]}
        passed, statuses = 0, []
        for t in tests:
            try:
                res = subprocess.run([str(exe)], input=t["stdin"], capture_output=True, text=True, timeout=TIMEOUT)
                ok = res.returncode == 0 and tokens(res.stdout) == tokens(t["expected_output"])
                statuses.append("pass" if ok else ("crash" if res.returncode != 0 else "wrong"))
            except subprocess.TimeoutExpired:
                ok = False
                statuses.append("timeout")
            passed += int(ok)
        return {"compiled": True, "passed": passed, "total": len(tests), "warnings": comp.stderr[-4000:],
                "statuses": statuses}


def _job(args: tuple[str, str, str, list[dict[str, str]]]) -> tuple[str, str, dict[str, Any]]:
    kind, key, code, tests = args
    try:
        return kind, key, run_tests(code, tests)
    except Exception as exc:
        return kind, key, {"compiled": False, "passed": 0, "total": len(tests), "error": str(exc)}


def apply_edit(base: str, find: str, replace: str) -> str | None:
    return base.replace(find, replace, 1) if base.count(find) == 1 else None


def make_row(pid: str, base_key: str, idx: int, label: str, note: str, code: str, base: str,
             find: str, replace: str, res: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": f"stu-{pid.lower()}-{base_key.lower()}{idx:02d}",
        "dataset_source": "SYNTHETIC", "source_record_id": f"student:{pid}:{base_key}:{idx}",
        "problem_id": f"bank-{pid}", "problem_cluster": None, "language": "cpp",
        "label": label, "label_source": "synthetic", "label_confidence": 0.9, "secondary_labels": [],
        "verdict": None, "firing_functions": ["student_style_edit"],
        "seed_ref": f"student:{pid}:{base_key}", "mutation_op": f"student_{label.lower()}_{idx:02d}",
        "verified_by_execution": True,
        "repair": {"op": "inverse_edit", "before": replace[:200], "after": find[:200],
                   "note": note, "base_sha256": hashlib.sha256(base.encode()).hexdigest()[:16]},
        "meta": {"user_id_hash": None, "attempt_index": None, "timestamp": None, "prev_submission_id": None},
        "static": {"source_code": code, "source_code_sha256": hashlib.sha256(code.encode()).hexdigest()},
        "warnings": {"compile_warnings": res.get("warnings", "")},
        "runtime": {"tests_passed": res["passed"], "tests_failed": res["total"] - res["passed"],
                    "tests_total": res["total"], "sanitizer_ok": None},
        "tests": {}, "cpg": {}, "context": {},
        "pipeline_run_id": "build_student_synthetic/1.0.0", "taxonomy_version": "tl-cpp-v2", "schema_version": "1.1",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)

    from student_specs_a import SPECS as SPECS_A
    from student_specs_b import SPECS as SPECS_B

    specs = {**SPECS_A, **SPECS_B}
    problems = {q["id"]: q for q in json.loads(BANK.read_text(encoding="utf-8"))["problems"]}
    tests_of = {pid: [{"stdin": t["stdin"], "expected_output": t["expected_output"]} for t in problems[pid]["test_cases"]]
                for pid in specs}

    jobs: list[tuple[str, str, str, list[dict[str, str]]]] = []
    edited: dict[str, tuple] = {}
    problems_report: dict[str, Counter] = {pid: Counter() for pid in specs}
    for pid, spec in specs.items():
        for key in ("A", "B"):
            jobs.append(("base", f"{pid}:{key}", spec[key], tests_of[pid]))
        for i, (base_key, label, find, replace, note) in enumerate(spec["edits"]):
            code = apply_edit(spec[base_key], find, replace)
            if code is None:
                problems_report[pid]["edit_not_unique"] += 1
                continue
            edited[f"{pid}:{base_key}:{i}"] = (pid, base_key, i, label, note, code, spec[base_key], find, replace)
            jobs.append(("edit", f"{pid}:{base_key}:{i}", code, tests_of[pid]))

    print(f"running {len(jobs)} programs", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        results = {(k, key): res for k, key, res in ex.map(_job, jobs, chunksize=2)}

    good_base = {}
    for pid in specs:
        for key in ("A", "B"):
            r = results[("base", f"{pid}:{key}")]
            good_base[(pid, key)] = r["compiled"] and r["passed"] == r["total"]
            if not good_base[(pid, key)]:
                problems_report[pid][f"base_{key}_fails"] += 1

    rows, seen_code = [], set()
    for key, (pid, base_key, i, label, note, code, base, find, replace) in edited.items():
        res = results[("edit", key)]
        if not good_base[(pid, base_key)]:
            problems_report[pid]["dropped_bad_base"] += 1
        elif not res["compiled"]:
            problems_report[pid]["dropped_compile_error"] += 1
        elif res["passed"] == res["total"]:
            problems_report[pid]["dropped_passes_all_tests"] += 1
        elif code in seen_code:
            problems_report[pid]["dropped_duplicate"] += 1
        else:
            seen_code.add(code)
            rows.append(make_row(pid, base_key, i, label, note, code, base, find, replace, res))
            problems_report[pid]["kept"] += 1

    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    PROOFS.mkdir(parents=True, exist_ok=True)
    for old in PROOFS.glob("student-*.json"):
        old.unlink()
    for r in rows:      # the committed evidence the G1 proof-join looks for (problem, operator, label)
        proof = {"run_id": r["row_id"], "seed_submission_id": r["seed_ref"], "problem_id": r["problem_id"],
                 "operator": r["mutation_op"], "label": r["label"], "seed_sha256": r["repair"]["base_sha256"],
                 "mutant_sha256": r["static"]["source_code_sha256"],
                 "tests_passed": r["runtime"]["tests_passed"], "tests_total": r["runtime"]["tests_total"],
                 "inverse_edit": r["repair"]}
        (PROOFS / f"student-{r['row_id']}.json").write_text(
            json.dumps(proof, indent=1) + "\n", encoding="utf-8", newline="\n")
    with CLUSTERS.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["problem_id", "cluster_id", "split", "statement_len"])
        for pid in sorted(specs):
            w.writerow([f"bank-{pid}", f"bank-{pid}", "train", len(problems[pid]["statement_markdown"])])

    by_label = Counter(r["label"] for r in rows)
    lines = ["# Student-style synthetic rows (bank problems)", "",
             "Generated by `scripts/build_student_synthetic.py`. Do not edit by hand.", "",
             f"- Programs run: {len(jobs)} · rows kept: {len(rows)} · problems: {len(specs)}",
             "- Kept only if the base passes all tests, the edited program compiles and fails at least one, "
             "and the single inverse edit is the base (a proof the bug is what breaks it).",
             "- Bank problems only; all are train clusters (`splits/bank_clusters.csv`).", "",
             "| Label | Rows |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in sorted(by_label.items())]
    lines += ["", "| Problem | Outcome counts |", "|---|---|"]
    for pid in sorted(problems_report):
        lines.append(f"| {pid} | {dict(problems_report[pid])} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"kept {len(rows)} rows: {dict(by_label)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
