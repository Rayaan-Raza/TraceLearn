"""Pick the IID test rows: a seeded, stratified hold-out from *train* clusters.

    python scripts/build_iid_holdout.py [--n 36] [--seed 20261026] [--force]

The cluster-disjoint ``test`` split asks "does the model generalise to
unseen problems?". The IID test asks the other question: "how good is it on
new submissions to problems it has seen?". Its rows therefore come from
train clusters, and ``merge_dataset.py`` moves every row listed in
``splits/iid_holdout.csv`` into split ``test_iid`` so the trainer never sees
them.

Which rows are eligible:
* natural rows only (CodeStream / PROGPedia), from train clusters;
* not the seed of any synthetic mutant (a mutant in train would leak its seed);
* the merge's dedupe already guarantees no >=0.8 code twin elsewhere, and the
  G7 twin check re-verifies it with the IID rows as their own split.

Selection is stratified by (source, label), proportional, with at least one
row from every stratum that has >= 5 rows. The rows are scored only after
their labels are confirmed by a person (``iid_test_*`` pre-review sheet);
``evaluate_holdout.py --split test_iid`` scores certain labels only.

Reads the last merge's ``annotations/labels.jsonl`` + ``splits/splits.csv``.
An existing hold-out is never silently re-drawn: rerun with ``--force``.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "splits" / "iid_holdout.csv"
NATURAL = {"CODESTREAM", "PROGPEDIA"}
FIELDS = ["row_id", "problem_id", "dataset_source", "source_record_id", "label", "label_source", "stratum"]


def eligible(labels: list[dict], split_of: dict[str, str]) -> list[dict]:
    seeds = {r.get("seed_ref") for r in labels if r.get("dataset_source") == "SYNTHETIC" and r.get("seed_ref")}
    return [r for r in labels
            if r["dataset_source"] in NATURAL
            and split_of.get(r["row_id"]) in ("train", "test_iid")
            and r.get("source_record_id") not in seeds]


def stratified_pick(rows: list[dict], n: int, seed: int) -> list[dict]:
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["row_id"]):
        strata[(r["dataset_source"], r["label"])].append(r)
    total = len(rows)
    quota = {k: (max(1, round(n * len(v) / total)) if len(v) >= 5 else 0) for k, v in strata.items()}
    # trim / top up the largest strata so the total is exactly n
    order = sorted(strata, key=lambda k: -len(strata[k]))
    while sum(quota.values()) > n:
        k = next(k for k in order if quota[k] > 1)
        quota[k] -= 1
    i = 0
    while sum(quota.values()) < n and any(quota[k] < len(strata[k]) for k in order):
        k = order[i % len(order)]
        if quota[k] < len(strata[k]) and len(strata[k]) >= 5:
            quota[k] += 1
        i += 1
    rng = random.Random(seed)
    picked = []
    for k in sorted(strata):
        picked += [dict(r, stratum=f"{k[0]}:{k[1]}") for r in rng.sample(strata[k], quota[k])]
    return sorted(picked, key=lambda r: r["row_id"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=36)
    ap.add_argument("--seed", type=int, default=20261026)
    ap.add_argument("--dataset-dir", type=Path, default=DS)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    out = a.dataset_dir / "splits" / "iid_holdout.csv"
    if out.exists() and not a.force:
        print(f"{out} exists — rerun with --force to re-draw (changes the IID test)")
        return 2
    labels = [json.loads(line) for line in open(a.dataset_dir / "annotations" / "labels.jsonl", encoding="utf-8")]
    split_of = {r["row_id"]: r["split"]
                for r in csv.DictReader(open(a.dataset_dir / "splits" / "splits.csv", encoding="utf-8"))}
    pool = eligible(labels, split_of)
    picked = stratified_pick(pool, a.n, a.seed)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(picked)
    by = defaultdict(int)
    for r in picked:
        by[r["stratum"]] += 1
    print(f"{len(picked)} IID rows from {len(pool)} eligible natural train rows -> {out}")
    for k in sorted(by):
        print(f"  {k}: {by[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
