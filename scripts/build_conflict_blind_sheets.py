"""U4: blank, blind rating sheets for the 19 LB/OBO conflict rows.

One private sheet per rater. Deliberately NO current label, conflict signal,
repair evidence, agent votes or model output (they would anchor the rater).
Only a locator, the problem id and a test-split marker are included; row order is
shuffled per rater with a fixed seed.

    python scripts/build_conflict_blind_sheets.py [--raters 3] [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
CHOICES = "LOOP_BOUNDARY | OFF_BY_ONE | OTHER (explain in note)"
FIELDS = ["row_id", "problem_id", "in_test_split", "source_code_path", "rater_label", "note"]


def build(ds: Path, out: Path, raters: int, seed: int = 20261120) -> list[Path]:
    ids = [r["row_id"] for r in csv.DictReader((ds / "review/label_conflicts/lb_obo_conflicts.csv").open(encoding="utf-8"))]
    split = {r["row_id"]: r["split"] for r in csv.DictReader((ds / "splits/splits.csv").open(encoding="utf-8"))}
    meta = {}
    for line in (ds / "annotations/labels.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if r["row_id"] in ids:
            meta[r["row_id"]] = r
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for k in range(1, raters + 1):
        order = sorted(ids)
        random.Random(seed + k).shuffle(order)
        p = out / f"rater_{k}_blank.csv"
        with p.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            for rid in order:
                m = meta[rid]
                w.writerow({"row_id": rid, "problem_id": m["problem_id"],
                            "in_test_split": "yes" if split.get(rid) == "test" else "no",
                            "source_code_path": m.get("source_code_path") or m.get("source_record_id") or "",
                            "rater_label": "", "note": ""})
        paths.append(p)
    return paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raters", type=int, default=3)
    ap.add_argument("--out", type=Path, default=DS / "review/label_conflicts/blind")
    a = ap.parse_args()
    for p in build(DS, a.out, a.raters):
        print(p)
    print("Allowed rater_label:", CHOICES)
