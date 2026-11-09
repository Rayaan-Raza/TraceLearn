"""Append blind labels to a labels file: `python scripts/record_blind_labels.py NAME < labels.json`.

Input is a JSON object {item_id: [label, note]}. Labels must be one of the
tl-cpp-v2 classes or UNCERTAIN. The file `review/blind_labels/NAME.json` keeps
{item_id: {"label", "note"}} and never overwrites an existing item with a
different label (relabelling must be deliberate: delete the entry first).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "misconception_dataset" / "review" / "blind_labels"
CLASSES = {"CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS", "CPP_UNINITIALIZED_VAR", "CPP_INT_OVERFLOW",
           "CPP_MISSING_BASE_CASE", "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK",
           "CPP_STALE_EXIT", "CPP_OTHER_ERROR", "UNCERTAIN"}


def merge(existing: dict, new: dict) -> dict:
    out = dict(existing)
    for item, (label, note) in new.items():
        if label not in CLASSES:
            raise ValueError(f"{item}: unknown label {label!r}")
        if item in out and out[item]["label"] != label:
            raise ValueError(f"{item}: already labelled {out[item]['label']!r}, refusing to overwrite with {label!r}")
        out[item] = {"label": label, "note": note}
    return out


def main(argv: list[str]) -> int:
    name = argv[1]
    path = DIR / f"{name}.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    merged = merge(existing, json.load(sys.stdin))
    DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(merged.items())), indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{name}: {len(merged)} items labelled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
