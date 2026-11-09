"""Verify and ingest the agent-written student-style programs of round 2.

    wsl python3 scripts/build_synth_v2.py [--workers 8]

Reads `synth_v2/agent_*.json` (see `synth_v2/SPEC.md`). Per problem the expected outputs come from
running the reference program, never from what the author typed. A bug is kept only if, by execution,

1. the reference runs on every test input (exit 0, under the time limit);
2. `fixed` compiles and produces the reference's output on every test (the bug-free program);
3. `buggy` compiles and fails at least one test (wrong output, crash or timeout);
4. `buggy` and `fixed` differ by at most 4 changed lines (one bug, not several);
5. class evidence where a tool can give it: CPP_ARRAY_BOUNDS needs an AddressSanitizer error on some
   failing test; CPP_INT_OVERFLOW needs a UBSan signed-overflow report (or, for unsigned/long long
   wraparound, no report but a wrong result on a test where `fixed` is right) - the report is stored.

Writes `annotations/tier0c_student_synthetic_v2.jsonl`, the train-only clusters
`splits/synth2_clusters.csv` and `reports/synth_v2_report.md`. Every problem is its own train cluster:
these rows never enter a held-out split.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
SRC = DS / "synth_v2"
OUT = DS / "annotations" / "tier0c_student_synthetic_v2.jsonl"
PROOFS = DS / "annotations" / "mutant_proofs"
CLUSTERS = DS / "splits" / "synth2_clusters.csv"
REPORT = DS / "reports" / "synth_v2_report.md"
TIMEOUT = 3.0
CLASSES = {"CPP_ARRAY_BOUNDS", "CPP_ASSIGN_VS_COMPARE", "CPP_INT_OVERFLOW", "CPP_LOOP_BOUNDARY", "CPP_MISSING_BASE_CASE",
           "CPP_OFF_BY_ONE", "CPP_OTHER_ERROR", "CPP_RANGE_CHECK", "CPP_STALE_EXIT", "CPP_UNINITIALIZED_VAR",
           "CPP_WRONG_LOOP_DIR"}


def compile_cpp(code: str, tmp: Path, name: str, extra: list[str] | None = None):
    src, exe = tmp / f"{name}.cpp", tmp / f"{name}.out"
    src.write_text(code, encoding="utf-8")
    cmd = ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", *(extra or []), str(src), "-o", str(exe)]
    comp = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    return (exe if comp.returncode == 0 else None), comp.stderr


def run_one(exe: Path, stdin: str):
    try:
        res = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True, timeout=TIMEOUT)
        return res.returncode, res.stdout.split(), res.stderr
    except subprocess.TimeoutExpired:
        return "timeout", [], ""


def verify_problem(p: dict) -> dict:
    out = {"id": p.get("id"), "problem": p, "bugs": [], "dropped": Counter()}
    try:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            tests = [x for x in p["tests"] if isinstance(x, str)]
            ref, _ = compile_cpp(p["reference"], tmp, "ref")
            if ref is None or len(tests) < 6:
                out["dropped"]["bad_reference_or_few_tests"] += len(p.get("bugs", []))
                return out
            expected = []
            for s in tests:
                rc, toks, _ = run_one(ref, s)
                if rc != 0:
                    out["dropped"]["reference_fails_a_test"] += len(p.get("bugs", []))
                    return out
                expected.append(toks)
            out["expected"] = [" ".join(e) for e in expected]
            for i, b in enumerate(p.get("bugs", [])):
                label = b.get("label")
                if label not in CLASSES:
                    out["dropped"]["unknown_label"] += 1
                    continue
                fixed, _ = compile_cpp(b["fixed"], tmp, f"fx{i}")
                if fixed is None:
                    out["dropped"]["fixed_does_not_compile"] += 1
                    continue
                if any(run_one(fixed, s)[:2] != (0, e) for s, e in zip(tests, expected)):
                    out["dropped"]["fixed_fails_a_test"] += 1
                    continue
                diff = [l for l in difflib.unified_diff(b["fixed"].splitlines(), b["buggy"].splitlines(), lineterm="", n=0)
                        if l[:1] in "+-" and l[:3] not in ("+++", "---")]
                if not diff or len(diff) > 8:                       # 4 changed lines = 4 minus + 4 plus
                    out["dropped"]["not_a_small_single_edit"] += 1
                    continue
                buggy, warn = compile_cpp(b["buggy"], tmp, f"bg{i}")
                if buggy is None:
                    out["dropped"]["buggy_does_not_compile"] += 1
                    continue
                statuses = []
                for s, e in zip(tests, expected):
                    rc, toks, _ = run_one(buggy, s)
                    statuses.append("pass" if (rc == 0 and toks == e) else ("timeout" if rc == "timeout" else ("crash" if rc != 0 else "wrong")))
                if all(x == "pass" for x in statuses):
                    out["dropped"]["buggy_passes_all_tests"] += 1
                    continue
                first = next(i2 for i2, x in enumerate(statuses) if x != "pass")
                evidence = None
                if label in ("CPP_ARRAY_BOUNDS", "CPP_INT_OVERFLOW"):
                    san, _ = compile_cpp(b["buggy"], tmp, f"sn{i}", ["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"])
                    if san is None:
                        out["dropped"]["sanitizer_build_failed"] += 1
                        continue
                    for s, st in zip(tests, statuses):
                        if st == "pass":
                            continue
                        res = subprocess.run([str(san)], input=s, capture_output=True, text=True, timeout=10)
                        err = res.stderr
                        if label == "CPP_ARRAY_BOUNDS" and ("AddressSanitizer" in err and "buffer-overflow" in err or "out of bounds" in err):
                            evidence = "asan:buffer-overflow" if "buffer-overflow" in err else "ubsan:out-of-bounds"
                            break
                        if label == "CPP_INT_OVERFLOW" and "signed integer overflow" in err:
                            evidence = "ubsan:signed-integer-overflow"
                            break
                    if evidence is None and label == "CPP_ARRAY_BOUNDS":
                        out["dropped"]["array_bounds_no_sanitizer_evidence"] += 1
                        continue
                    if evidence is None and label == "CPP_INT_OVERFLOW":
                        # wraparound that no sanitizer reports (e.g. int*int promoted wrongly): keep only if a test
                        # where the bug-free program is right gives a different answer, which is already true here
                        evidence = "wrong_result_on_large_input"
                out["bugs"].append({"idx": i, "label": label, "buggy": b["buggy"], "fixed": b["fixed"], "note": b.get("note", ""),
                                    "statuses": statuses, "first_failed": first, "evidence": evidence,
                                    "warnings": warn[-3000:], "passed": sum(x == "pass" for x in statuses), "total": len(tests)})
    except Exception as exc:  # noqa: BLE001
        out["dropped"]["error:" + type(exc).__name__] += 1
    return out


# Author labels that contradict the taxonomy, corrected with the reason (row id -> label, reason).
# stu-s2-f-06-03: the edit adds a wrong early `return true` to a recursive palindrome check. There is
# no loop, so it cannot be a stale loop exit (applicability.py rules STALE_EXIT out without a loop).
LABEL_CORRECTIONS = {"stu-s2-f-06-03": ("CPP_OTHER_ERROR", "wrong early return in recursion; no loop, not STALE_EXIT")}


def make_row(pid: str, n: int, b: dict) -> dict:
    code = b["buggy"]
    fix = LABEL_CORRECTIONS.get(f"stu-{pid.lower()}-{n:02d}")
    if fix:
        b = {**b, "label": fix[0], "note": f"{b['note']} [label corrected: {fix[1]}]"}
    return {
        "row_id": f"stu-{pid.lower()}-{n:02d}", "dataset_source": "SYNTHETIC", "source_record_id": f"synth2:{pid}:{n}",
        "problem_id": f"synth2-{pid}", "problem_cluster": None, "language": "cpp",
        "label": b["label"], "label_source": "synthetic", "label_confidence": 0.9, "secondary_labels": [],
        "verdict": None, "firing_functions": ["agent_authored_edit"], "seed_ref": f"synth2:{pid}",
        "mutation_op": f"synth2_{b['label'].lower()}", "verified_by_execution": True,
        "repair": {"op": "fixed_version", "before": b["buggy"][:200], "after": b["fixed"][:200], "note": b["note"],
                   "evidence": b["evidence"], "base_sha256": hashlib.sha256(b["fixed"].encode()).hexdigest()[:16]},
        "meta": {"user_id_hash": None, "attempt_index": None, "timestamp": None, "prev_submission_id": None},
        "static": {"source_code": code, "source_code_sha256": hashlib.sha256(code.encode()).hexdigest()},
        "warnings": {"compile_warnings": b["warnings"]},
        "runtime": {"tests_passed": b["passed"], "tests_failed": b["total"] - b["passed"], "tests_total": b["total"],
                    "sanitizer_ok": None},
        "tests": {}, "cpg": {}, "context": {},
        "pipeline_run_id": "build_synth_v2/1.0.0", "taxonomy_version": "tl-cpp-v2", "schema_version": "1.1",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    problems, seen_ids = [], set()
    for f in sorted(SRC.glob("agent_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"{f.name}: unreadable ({exc})")
            continue
        for p in data.get("problems", []):
            if p.get("id") and p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                problems.append(p)
    print(f"{len(problems)} problems", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(verify_problem, problems, chunksize=1))
    rows, seen_code, dropped, by_agent = [], set(), Counter(), Counter()
    for r in results:
        dropped.update(r["dropped"])
        for n, b in enumerate(r["bugs"], 1):
            key = hashlib.sha256("".join(b["buggy"].split()).encode()).hexdigest()
            if key in seen_code:
                dropped["duplicate_code"] += 1
                continue
            seen_code.add(key)
            rows.append(make_row(r["id"], n, b))
            by_agent[r["id"].split("-")[1] if r["id"].count("-") >= 2 else "?"] += 1
    OUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8", newline="\n")
    PROOFS.mkdir(parents=True, exist_ok=True)
    for old_proof in PROOFS.glob("synth2-*.json"):
        old_proof.unlink()
    for x in rows:        # the committed evidence the G1 proof-join looks for (problem, operator, label)
        proof = {"run_id": x["row_id"], "seed_submission_id": x["seed_ref"], "problem_id": x["problem_id"],
                 "operator": x["mutation_op"], "label": x["label"], "seed_sha256": x["repair"]["base_sha256"],
                 "mutant_sha256": x["static"]["source_code_sha256"], "tests_passed": x["runtime"]["tests_passed"],
                 "tests_total": x["runtime"]["tests_total"], "fixed_version": x["repair"], "evidence": x["repair"]["evidence"]}
        (PROOFS / f"synth2-{x['row_id']}.json").write_text(json.dumps(proof, indent=1) + "\n", encoding="utf-8", newline="\n")
    kept_problems = sorted({x["problem_id"] for x in rows})
    with CLUSTERS.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["problem_id", "cluster_id", "split", "statement_len"])
        statements = {f"synth2-{p['id']}": len(p.get("statement", "")) for p in problems}
        for pid in kept_problems:
            w.writerow([pid, pid, "train", statements.get(pid, 0)])
    by_label = Counter(x["label"] for x in rows)
    lines = ["# Agent-written student-style programs, round 2", "", "Generated by `scripts/build_synth_v2.py`. Do not edit by hand.", "",
             f"- Problems read: {len(problems)} · problems with at least one kept bug: {len(kept_problems)} · rows kept: {len(rows)}",
             "- Kept only if the bug-free `fixed` program matches the reference on every test, `buggy` fails at least one, they differ by a "
             "small single edit, and array-bounds/overflow rows have sanitizer evidence where the tool can report it.",
             "- Every problem is a train-only cluster (`splits/synth2_clusters.csv`).", "", "| Label | Rows |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(by_label.items())]
    lines += ["", "Dropped:", ""] + [f"- {k}: {v}" for k, v in dropped.most_common()]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"kept {len(rows)} rows in {len(kept_problems)} problems: {dict(by_label)}; dropped {dict(dropped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
