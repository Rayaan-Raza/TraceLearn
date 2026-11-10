"""Build a human-labelled real test set meeting the per-class coverage targets.

    python scripts/build_real_test_set.py [--min-rows 15] [--min-problems 5] [--out review/real_test_queue.csv]

The senior review requires a dedicated real test set for every class with:
    - >= 15 real (human-labelled) rows per class
    - From >= 5 distinct problems per class

This script does NOT create labels. It queries the existing human-labelled
rows, finds how many are already in the 'test' split, and writes a CSV of
*candidates* from the 'unlabelled' or 'dev_gold' pools that could be promoted
to fill the gap. Each candidate row is one for a human annotator to verify.

Output columns:
    row_id, problem_id, current_split, proposed_label, rationale
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rows", type=int, default=15,
                    help="minimum real test rows per class")
    ap.add_argument("--min-problems", type=int, default=5,
                    help="minimum distinct test problems per class")
    ap.add_argument("--out", default=str(DS / "review" / "real_test_queue.csv"))
    args = ap.parse_args()

    labels: dict[str, dict] = {}
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            labels[r["row_id"]] = r

    splits: dict[str, str] = {}
    for row in csv.DictReader((DS / "splits" / "splits.csv").open(newline="", encoding="utf-8")):
        splits[row["row_id"]] = row["split"]

    # Tally real test rows per class
    test_rows: dict[str, list[str]] = defaultdict(list)
    test_probs: dict[str, Counter] = defaultdict(Counter)
    for row_id, meta in labels.items():
        if meta.get("label_source") != "human":
            continue
        if splits.get(row_id) != "test":
            continue
        lbl = meta.get("label", "")
        if lbl:
            test_rows[lbl].append(row_id)
            test_probs[lbl][meta.get("problem_id", "?")] += 1

    all_labels = sorted({m.get("label") for m in labels.values() if m.get("label")})

    print(f"\n{'Class':<35} {'Test rows':>10} {'Problems':>10}  Status")
    print("-" * 68)
    need_more: list[tuple[str, int, int]] = []
    for lbl in all_labels:
        n = len(test_rows[lbl])
        p = len(test_probs[lbl])
        flag = "ok" if (n >= args.min_rows and p >= args.min_problems) else "⚠ NEEDS MORE"
        print(f"  {lbl:<33} {n:>10} {p:>10}  {flag}")
        if n < args.min_rows or p < args.min_problems:
            need_more.append((lbl, max(0, args.min_rows - n), max(0, args.min_problems - p)))

    if not need_more:
        print("\nAll classes meet the real test-set targets. Nothing to queue.")
        return 0

    # Collect non-test human rows as candidates to promote
    candidates: list[dict] = []
    for row_id, meta in labels.items():
        if meta.get("label_source") != "human":
            continue
        if splits.get(row_id) in ("test",):
            continue
        lbl = meta.get("label", "")
        if not lbl:
            continue
        if any(lbl == t for t, _, _ in need_more):
            candidates.append({
                "row_id": row_id,
                "problem_id": meta.get("problem_id", "?"),
                "current_split": splits.get(row_id, "unknown"),
                "proposed_label": lbl,
                "rationale": "promote to test to meet real test-set target",
            })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["row_id", "problem_id", "current_split",
                                                 "proposed_label", "rationale"])
        writer.writeheader()
        writer.writerows(candidates)

    print(f"\nWrote {len(candidates)} promotion candidates → {out_path}")
    print("A human annotator should verify each row before moving it to the test split.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
