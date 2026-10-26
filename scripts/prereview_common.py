"""Shared format for model pre-review sheets (human sign-off workflow).

A pre-review sheet is a CSV in ``data/misconception_dataset/review/model_prereview/``.
Each row is one item a *model* (Claude) reviewed: its verdict, the label it
would give, and why. Nothing in a sheet is a label until a person signs off.

Columns the reviewer (model) fills: everything up to ``reviewed_at``.
Columns a person fills: ``human_verdict`` (agree / disagree / unsure),
``human_label`` (required on disagree), ``signed_off_by``, ``signed_off_at``,
``human_notes``. ``spotcheck=1`` marks the seeded 20% sample to sign first.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREVIEW_DIR = ROOT / "data" / "misconception_dataset" / "review" / "model_prereview"
REVIEWER = "claude (model pre-review)"
COLUMNS = [
    "item_id", "sheet", "row_id", "submission_id", "source_record_id", "dataset_source", "problem_id",
    "current_label", "current_label_source", "firing_functions",
    "model_verdict", "model_label", "model_confidence", "model_rationale", "evidence",
    "spotcheck", "reviewer", "reviewed_at",
    "human_verdict", "human_label", "signed_off_by", "signed_off_at", "human_notes",
]
VERDICTS = {"correct", "incorrect", "uncertain", "label"}  # 'label' = new item, no prior label
HUMAN_VERDICTS = {"agree", "disagree", "unsure"}
SPOTCHECK_FRACTION = 0.20
ACCEPT_AGREEMENT = 0.90


def mark_spotcheck(rows: list[dict], seed: int, fraction: float = SPOTCHECK_FRACTION) -> None:
    """Seeded sample (at least 1 row) the humans sign first."""
    k = max(1, round(len(rows) * fraction))
    pick = set(random.Random(seed).sample(range(len(rows)), min(k, len(rows))))
    for i, r in enumerate(rows):
        r["spotcheck"] = "1" if i in pick else "0"


def write_sheet(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def read_sheet(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
