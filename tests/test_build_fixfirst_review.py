"""The fix-first label review sheet (scripts/build_fixfirst_review.py)."""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_fixfirst_review as B  # noqa: E402


def _row(rid, label, fixes):
    return {"row_id": rid, "label": label, "fix_first": fixes, "split": "train"}


def test_select_takes_every_disputed_row_and_seeded_controls():
    rows = ([_row(f"o{i}", B.OTHER, ["OFF_BY_ONE"]) for i in range(5)]
            + [_row("o-two", B.OTHER, ["OFF_BY_ONE", "LOOP_BOUNDARY"])]          # two classes: not disputed
            + [_row(f"c{i}", B.OTHER, []) for i in range(30)]
            + [_row(f"k{i}", "CPP_OFF_BY_ONE", ["OFF_BY_ONE"]) for i in range(20)]
            + [_row("k-range", "CPP_RANGE_CHECK", ["RANGE_CHECK"])])              # class not disputed: no control
    items = B.select(rows, seed=1)
    groups = Counter(r["group"] for r in items)
    assert groups == {"disputed": 5, "control_other": B.N_CONTROL_OTHER, "control_class": B.N_CONTROL_CLASS}
    assert {r["row_id"] for r in items if r["group"] == "disputed"} == {f"o{i}" for i in range(5)}
    assert "o-two" not in {r["row_id"] for r in items} and "k-range" not in {r["row_id"] for r in items}
    assert [r["item_id"] for r in items] == [f"FF-{i:03d}" for i in range(1, len(items) + 1)]
    assert [r["row_id"] for r in B.select(rows, seed=1)] == [r["row_id"] for r in items]   # seeded


def test_committed_sheet_is_blind_and_training_side_only():
    out = B.OUT
    sheet = list(csv.DictReader((out / "blind_sheet.csv").open(encoding="utf-8")))
    assert not {"recorded_label", "group", "evidence_class", "label", "label_status"} & set(sheet[0])
    assert all(not r["rater_label"] for r in sheet)
    key = {r["item_id"]: r for r in csv.DictReader((out / "key.csv").open(encoding="utf-8"))}
    assert set(key) == {r["item_id"] for r in sheet}
    assert {r["split"] for r in key.values()} <= {"train", "dev_gold"}
    assert all(r["recorded_label"] == B.OTHER for r in key.values() if r["group"] == "disputed")
