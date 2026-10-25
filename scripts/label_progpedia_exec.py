"""Execution-based labeling of PROGPedia WRONG_ANSWER / RUNTIME_ERROR submissions.

With oracle tests (``progpedia_oracle_tests.py``) a PROGPedia submission can
be run like a CodeStream one, so the Lane B pipeline applies unchanged:
sandbox_runner execution → the two-signal LFs → repair-and-rerun
(``label_weak_codestream.decide``). This gives PROGPedia real rows in classes
other than CPP_ARRAY_BOUNDS (the pg rules only ever fired pg-3).

    python scripts/label_progpedia_exec.py --raw-root <dir with progpedia/ and "progpedia (1)/">

Outputs (data/misconception_dataset/):
  annotations/tier1c_progpedia_exec.jsonl     repair_verified / weak_rule rows
  review/progpedia_exec_review.jsonl          multi_signal, discovery and repair_discovered rows
  review/progpedia_exec_tier1b_evidence.jsonl execution evidence for rows the pg lane
                                              already labeled (feeds the pg-3 pre-review;
                                              those submissions are not emitted twice)
  reports/progpedia_exec_report.md

Rows carry evidence in the sandbox_runner vocabulary and
``evidence_vocab="sandbox_runner"``, so ``tracelearn_features.normalize`` maps
them exactly as it maps CodeStream rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import progpedia_oracle_tests as oracle  # noqa: E402
from codestream_lfs import DISCOVERY_CLASSES, confidence  # noqa: E402
from label_weak_codestream import EXPLORE_CLASSES, decide, slim_runtime, slim_tests  # noqa: E402

from sandbox_runner import RunConfig, run_many  # noqa: E402

DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "annotations" / "tier1c_progpedia_exec.jsonl"
REVIEW = DS / "review" / "progpedia_exec_review.jsonl"
TIER1B_EVIDENCE = DS / "review" / "progpedia_exec_tier1b_evidence.jsonl"
REPORT = DS / "reports" / "progpedia_exec_report.md"
CACHE = DS / "cache" / "progpedia_exec"
PIPELINE = "label_progpedia_exec/1.0.0"
VERDICTS = ("WRONG_ANSWER", "RUNTIME_ERROR")


def collect(raw_root: Path, problems: list[str]) -> list[dict]:
    """WA/RE C/C++ submissions, de-duplicated by code hash across the two raw copies."""
    seen, out = set(), []
    for pid in problems:
        for verdict in VERDICTS:
            for path in oracle.submissions(raw_root, pid, verdict):
                code = path.read_text(encoding="utf-8", errors="replace")
                h = hashlib.sha256(code.encode()).hexdigest()
                if h in seen:
                    continue
                seen.add(h)
                copy_dir = path.relative_to(raw_root).parts[0]
                rel = path.relative_to(raw_root / copy_dir).as_posix()
                out.append({"problem_id": pid, "verdict": verdict, "code": code, "sha": h,
                            "lang": "c" if path.suffix == ".c" else "cpp",
                            "source_record_id": rel, "raw_copy": copy_dir,
                            "user_id": rel.split("/")[2].split("_")[0]})
    return out


def _decide(args):
    code, lang, tests, result, cache_dir = args
    try:
        return decide(code, lang, tests, result, cache_dir=cache_dir, explore=True, explore_tries=6)
    except Exception as exc:  # one bad row must not stop the run
        return {"decision": "error", "error": f"{type(exc).__name__}: {exc}", "fires": [], "repairs": []}


def problem_context(raw_root: Path, problem_id: str, tier1b_ctx: dict) -> dict:
    """Canonical context block, identical to the pg lane's for the same problem
    (so execution rows add no context shift); derived from the statement otherwise."""
    if problem_id in tier1b_ctx:
        return dict(tier1b_ctx[problem_id])
    stmt = ""
    for d in oracle.problem_dirs(raw_root, problem_id):
        if (d / "statement.md").exists():
            stmt = (d / "statement.md").read_text(encoding="utf-8", errors="replace")
            break
    n_samples = len(oracle.statement_samples(raw_root, problem_id))
    return {"available": True, "statement_length": len(stmt), "sample_test_count": n_samples,
            "sample_tests_present": n_samples > 0, "constraints_present": False}


def build_row(n: int, sub: dict, result: dict, dec: dict, audits: dict, context: dict) -> dict:
    label = dec.get("label")
    src = {"repair_verified": "repair_verified", "weak_rule": "weak_rule"}.get(dec["decision"])
    conf, audit = None, None
    if src == "repair_verified":
        conf, k, m = confidence(f"repair_verified:{label}", audits)
        audit = {"key": f"repair_verified:{label}", "correct": k, "audited": m}
    elif src == "weak_rule":
        lf = next(f["lf"] for f in dec["fires"] if f["class"] == label)
        conf, k, m = confidence(lf, audits)
        audit = {"key": lf, "correct": k, "audited": m}
    rep = next((r for r in dec.get("repairs", []) if r.get("verified") and r["class"] == label), None)
    return {
        "row_id": f"pgx-{n:06d}",
        "dataset_source": "PROGPEDIA",
        "source_record_id": sub["source_record_id"],
        "submission_id": None,
        "problem_id": sub["problem_id"],
        "problem_cluster": None,  # the merge joins cluster_assignments.csv
        "language": sub["lang"],
        "label": label,
        "label_source": src,
        "label_confidence": conf,
        "label_status": dec["decision"],
        "secondary_labels": dec.get("secondary", []),
        "verdict": sub["verdict"],
        "firing_functions": sorted({f["lf"] for f in dec["fires"]}),
        "firing_count": dec.get("firing_count", 0),
        "lf_evidence": dec["fires"],
        "audit": audit,
        "seed_ref": None,
        "mutation_op": None,
        "repair": ({"op": rep["repair"]["op"], "line": rep["repair"]["line"],
                    "before": rep["repair"]["before"][:200], "after": rep["repair"]["after"][:200],
                    "proof": rep["proof"]} if rep else None),
        "repair_partial": next((r.get("partial") for r in dec.get("repairs", [])
                                if r["class"] == label and r.get("partial")), None),
        "verified_by_execution": src == "repair_verified",
        "meta": {"user_id_hash": hashlib.sha256(f"progpedia:{sub['user_id']}".encode()).hexdigest()[:16],
                 "attempt_index": None, "timestamp": None, "prev_submission_id": None,
                 "code_sha256": sub["sha"], "raw_copy": sub["raw_copy"]},
        "static": None,
        "warnings": {"_compiled": True, **((result.get("warnings") or {}).get("count_by_flag") or {})},
        "runtime": slim_runtime(result),
        "tests": slim_tests(result),
        "cpg": None,
        "context": context,
        "test_source": "oracle",
        "evidence_vocab": "sandbox_runner",
        "pipeline_run_id": PIPELINE,
        "taxonomy_version": "tl-cpp-v2",
        "schema_version": "1.1",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--index-csv", type=Path, default=None,
                    help="normalized submissions.csv; rows whose source_record_id it does not list are "
                         "left out (the merge's G1 join would reject them)")
    a = ap.parse_args()

    tests = {}
    for p in sorted((DS / "oracle_tests" / "progpedia").glob("*.json.gz")):
        pid = p.name[: -len(".json.gz")]
        t = oracle.load_tests(pid)
        if t:
            tests[pid] = t
    subs = collect(a.raw_root, sorted(tests))
    not_indexed = 0
    if a.index_csv:
        import csv
        csv.field_size_limit(2**31 - 1)
        with open(a.index_csv, encoding="utf-8-sig", newline="") as f:
            known = {r["source_record_id"] for r in csv.DictReader(f) if r.get("dataset_source") == "PROGPEDIA"}
        before = len(subs)
        subs = [s for s in subs if s["source_record_id"] in known]
        not_indexed = before - len(subs)
    if a.limit:
        subs = subs[: a.limit]
    print(f"{len(subs)} WA/RE C/C++ submissions over {len(tests)} problems with oracle tests", flush=True)

    labeled_1b, tier1b_ctx = {}, {}
    tier1b = DS / "annotations" / "tier1b_progpedia.jsonl"
    if tier1b.exists():
        for line in tier1b.open(encoding="utf-8"):
            r = json.loads(line)
            labeled_1b[(r["problem_id"], r["source_record_id"])] = r
            if isinstance(r.get("context"), dict):
                tier1b_ctx.setdefault(r["problem_id"], r["context"])
    contexts = {pid: problem_context(a.raw_root, pid, tier1b_ctx) for pid in tests}

    CACHE.mkdir(parents=True, exist_ok=True)
    jobs = [(s["code"], s["lang"], tests[s["problem_id"]]) for s in subs]
    cfg = RunConfig(sanitizer_max_input_bytes=20_000, valgrind_max_input_bytes=20_000,
                    slow_pass_skip_timeouts=True)
    results = []
    for i, res in enumerate(run_many(jobs, cfg, workers=a.workers, cache_dir=str(CACHE / "runs")), 1):
        results.append(res)
        if i % 100 == 0:
            print(f"  executed {i}/{len(jobs)}", flush=True)
    print("executed", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        decisions = list(ex.map(_decide, [(s["code"], s["lang"], tests[s["problem_id"]], r,
                                           str(CACHE / "repairs")) for s, r in zip(subs, results)],
                                chunksize=4))

    from label_weak_codestream import load_audits
    audits = load_audits()
    rows, review, evidence = [], [], []
    stats, by_class = Counter(), Counter()
    branch = Counter()
    for n, (s, r, d) in enumerate(zip(subs, results, decisions), 1):
        branch[r.get("branch", "error")] += 1
        stats[d["decision"]] += 1
        if d["decision"] in ("pre_branch", "error"):
            continue
        row = build_row(n, s, r, d, audits, contexts[s["problem_id"]])
        key = (s["problem_id"], s["source_record_id"])
        if key in labeled_1b:
            evidence.append({"tier1b_row_id": labeled_1b[key]["row_id"],
                             "tier1b_label": labeled_1b[key]["label"], **row})
            continue
        if d["decision"] in ("repair_verified", "weak_rule"):
            rows.append(row)
            by_class[(row["label"], row["label_source"])] += 1
        elif d["decision"] in ("multi_signal", "discovery", "repair_discovered"):
            review.append(row)

    for path, data in ((OUT, rows), (REVIEW, review), (TIER1B_EVIDENCE, evidence)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for row in data:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    disc = Counter((r["label"] or "|".join(r["secondary_labels"]), r["label_status"]) for r in review)
    lines = ["# PROGPedia execution labeling", "",
             "Generated by `scripts/label_progpedia_exec.py`. Do not edit by hand.", "",
             f"- Submissions (WA/RE, C/C++, de-duplicated): {len(subs)} over {len(tests)} problems with oracle tests",
             "- Execution branch: " + ", ".join(f"{k} {v}" for k, v in sorted(branch.items())),
             "- Decisions: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())),
             f"- Already labeled by the pg lane (evidence only, not re-emitted): {len(evidence)}",
             f"- Left out because the normalized index does not list them: {not_indexed}", "",
             "`all_pass` rows failed on the original judge's hidden tests but pass every oracle test; "
             "they are left unlabeled.", "",
             "## New rows (`tier1c_progpedia_exec.jsonl`)", "", "| Class | repair_verified | weak_rule |",
             "|---|---:|---:|"]
    for c in sorted({c for c, _ in by_class}):
        lines.append(f"| {c} | {by_class[(c, 'repair_verified')]} | {by_class[(c, 'weak_rule')]} |")
    lines += ["", "## Review pool (`review/progpedia_exec_review.jsonl`, human confirmation)", "",
              "| Class(es) | Status | Rows |", "|---|---|---:|"]
    for (c, st), k in sorted(disc.items()):
        lines.append(f"| {c} | {st} | {k} |")
    agree = Counter((e["tier1b_label"] == e["label"], e["label_status"]) for e in evidence)
    lines += ["", "## Execution evidence on pg-lane rows", "",
              "| pg label confirmed by execution | Status | Rows |", "|---|---|---:|"]
    for (same, st), k in sorted(agree.items()):
        lines.append(f"| {'yes' if same else 'no'} | {st} | {k} |")
    lines += ["", f"Discovery classes ({', '.join(DISCOVERY_CLASSES)}) and repair exploration "
              f"({', '.join(EXPLORE_CLASSES)}) go to review, never straight to a label."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
