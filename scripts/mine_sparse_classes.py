"""Report real-data coverage for sparse misconception classes and suggest mining targets.

    python scripts/mine_sparse_classes.py [--min-rows 30] [--min-problems 5]

The four classes flagged by the senior review as near-empty in real (human-labelled)
training data are:
    CPP_ASSIGN_VS_COMPARE, CPP_MISSING_BASE_CASE, CPP_WRONG_LOOP_DIR, CPP_STALE_EXIT

For each of the 11 classes this script counts real rows in the training split and
shows how many distinct problems they come from. Classes that fall below --min-rows or
--min-problems are highlighted as mining targets. The script also prints the top-5
problems per sparse class (sorted by real row count) to guide where to look for new
annotation candidates.

Target (per senior review): >= 30 real rows from >= 5 distinct problems per class.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"

SPARSE_CLASSES = {
    "CPP_ASSIGN_VS_COMPARE",
    "CPP_MISSING_BASE_CASE",
    "CPP_WRONG_LOOP_DIR",
    "CPP_STALE_EXIT",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rows", type=int, default=30,
                    help="target minimum real rows per class")
    ap.add_argument("--min-problems", type=int, default=5,
                    help="target minimum distinct problems per class")
    args = ap.parse_args()

    # Load labels (human-only)
    labels: dict[str, dict] = {}
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            labels[r["row_id"]] = r

    # Load split assignments
    train_ids: set[str] = set()
    for row in csv.DictReader((DS / "splits" / "splits.csv").open(newline="", encoding="utf-8")):
        if row["split"] == "train":
            train_ids.add(row["row_id"])

    # Count real rows per class in train
    class_rows: dict[str, list[str]] = defaultdict(list)   # label -> [row_id]
    class_problems: dict[str, Counter] = defaultdict(Counter)  # label -> Counter(problem_id)

    for row_id, meta in labels.items():
        if meta.get("label_source") != "human":
            continue
        if row_id not in train_ids:
            continue
        lbl = meta.get("label", "")
        if not lbl:
            continue
        class_rows[lbl].append(row_id)
        prob = meta.get("problem_id", "unknown")
        class_problems[lbl][prob] += 1

    all_classes = sorted(
        {m.get("label") for m in labels.values() if m.get("label")} | SPARSE_CLASSES
    )

    print(f"\n{'Class':<35} {'Real rows':>10} {'Problems':>10}  {'Status'}")
    print("-" * 70)
    gaps = []
    for cls in all_classes:
        n_rows = len(class_rows[cls])
        n_probs = len(class_problems[cls])
        need_rows = max(0, args.min_rows - n_rows)
        need_probs = max(0, args.min_problems - n_probs)
        is_sparse = cls in SPARSE_CLASSES or n_rows < args.min_rows
        flag = "⚠ SPARSE" if (n_rows < args.min_rows or n_probs < args.min_problems) else "ok"
        print(f"  {cls:<33} {n_rows:>10} {n_probs:>10}  {flag}")
        if need_rows > 0 or need_probs > 0:
            gaps.append((cls, need_rows, need_probs, class_problems[cls]))

    if gaps:
        print(f"\n{'='*70}")
        print("Mining targets (need rows / problems to reach targets):\n")
        for cls, need_rows, need_probs, prob_ctr in gaps:
            print(f"  {cls}")
            print(f"    need {need_rows} more rows, {need_probs} more problems")
            top5 = prob_ctr.most_common(5)
            if top5:
                print("    existing problems (by row count):")
                for prob, cnt in top5:
                    print(f"      {prob}: {cnt} rows")
            else:
                print("    no existing real rows — start from scratch")
            print()
    else:
        print("\nAll classes meet the coverage targets.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
