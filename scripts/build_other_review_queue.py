"""Blind review sheet to confirm real OTHER_ERROR candidates (needs the raw corpus).

    wsl python3 scripts/build_other_review_queue.py --raw /mnt/g/TraceLearn/Datasets_RAW [--per-problem 6]

Why. Real failing student programs are mostly "wrong for none of the ten modelled
reasons", yet the training set holds 13 OTHER_ERROR rows, all mutant decoys
(`scripts/experiment_weak_other.py`). The master plan allows real OTHER_ERROR rows
only when a person confirmed them. This builds the smallest useful sheet for that:
a seeded, per-problem-stratified sample of failing CodeStream submissions from
TRAIN clusters on which no labeling function fired and no repair verified.

The sheet is BLIND: it shows the code, the failing test and the observed output,
and never the model's prediction or any rule output, so the reviewer is not
anchored. For each row write one `tl-cpp-v2` class (or `UNCERTAIN`) in
`human_label`, sign it, and add notes. Two uses of the answers:

1. the share of rows that turn out to be a modelled class is the CONTAMINATION
   rate of "no rule fired" as an OTHER_ERROR proxy (decides whether the weak-OTHER
   experiment is safe to adopt);
2. confirmed OTHER_ERROR rows are the real negatives the classifier lacks.

The output stays in the gitignored cache because it contains student code. It is
rebuilt deterministically from the seed. Ingesting signed rows needs
`apply_prereview_signoff.py` extended to a train-pool sheet (not done here).
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DS = ROOT / "data" / "misconception_dataset"
CACHE = DS / "cache"
SEED = 20261107
CLASSES = ("CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS", "CPP_UNINITIALIZED_VAR", "CPP_INT_OVERFLOW",
           "CPP_MISSING_BASE_CASE", "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK",
           "CPP_STALE_EXIT", "CPP_OTHER_ERROR", "UNCERTAIN")


def head(text: str, limit: int = 400) -> str:
    text = (text or "").replace("\r\n", "\n")
    return text if len(text) <= limit else text[:limit] + " ...[cut]"


def sample_queue(index_rows: list[dict[str, str]], per_problem: int, seed: int = SEED) -> list[dict[str, str]]:
    """Seeded, per-problem-stratified sample of train-cluster no-fire failing rows."""
    pool = [r for r in index_rows if r["split_pool"] == "train" and r["decision"] == "no_fire"]
    by_problem: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in sorted(pool, key=lambda r: r["submission_id"]):
        by_problem[r["problem_id"]].append(r)
    rng = random.Random(seed)
    chosen: list[dict[str, str]] = []
    for problem in sorted(by_problem):
        rows = by_problem[problem][:]
        rng.shuffle(rows)
        chosen.extend(rows[:per_problem])
    rng.shuffle(chosen)
    return chosen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default=None)
    ap.add_argument("--per-problem", type=int, default=6)
    args = ap.parse_args(argv)

    from codestream_common import find_raw, load_problems, load_submissions

    index = list(csv.DictReader((DS / "annotations" / "codestream_failing_index.csv").open(encoding="utf-8", newline="")))
    picked = sample_queue(index, args.per_problem)
    raw = find_raw(args.raw)
    probs = load_problems(raw)
    subs = {s.submission_id: s for s in load_submissions(raw)}

    import json
    executed: dict[str, dict] = {}
    for line in (CACHE / "real_eval_exec_train.jsonl").open(encoding="utf-8"):
        rec = json.loads(line)
        executed[rec["submission_id"]] = rec["result"]

    out = CACHE / "review_queue_other_codestream.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "submission_id", "problem_id", "cluster", "source_verdict", "tests_passed",
                    "failing_input", "expected_output", "observed_output", "code",
                    "human_label", "signed_off_by", "signed_off_at", "notes"])
        n = 0
        for r in picked:
            sub, res = subs.get(r["submission_id"]), executed.get(r["submission_id"])
            if sub is None or res is None:
                continue
            tests = res.get("tests") or {}
            first = tests.get("first_failed")
            result = next((x for x in tests.get("results", []) if x.get("idx") == first), {})
            problem_tests = probs[sub.problem_id].tests
            case = problem_tests[first] if isinstance(first, int) and first < len(problem_tests) else {}
            n += 1
            w.writerow([f"OC-{n:03d}", sub.submission_id, sub.problem_id, r["problem_cluster"], sub.verdict,
                        f"{tests.get('passed')}/{tests.get('total')}", head(case.get("input", "")),
                        head(case.get("output", "")), head(result.get("stdout_head", "")), sub.code, "", "", "", ""])
    print(f"wrote {n} items for {len({r['problem_id'] for r in picked})} problems -> {out}")
    print("allowed human_label values:", ", ".join(CLASSES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
