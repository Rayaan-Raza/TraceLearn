"""Find LOOP_BOUNDARY / OFF_BY_ONE labelling conflicts and write a review queue.

    python scripts/find_label_conflicts.py [--out data/misconception_dataset/review/label_conflicts/lb_obo_conflicts.csv]

A conflict row is any real (label_source=human) row labelled LOOP_BOUNDARY or OFF_BY_ONE where
a secondary-label field or a cross-annotator signal suggests the other class. The script also
flags rows where annotators disagreed (agent-label vs final label) on exactly the LB/OBO pair.

Output columns: row_id, current_label, conflict_signal, relabel (blank for human), note (blank).

The boundary rule that determines the correct label is in section 6 of
data/misconception_dataset/ANNOTATION_GUIDELINE.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"

LB = "CPP_LOOP_BOUNDARY"
OBO = "CPP_OFF_BY_ONE"
CONFLICT_PAIR = {LB, OBO}


def load_labels() -> dict[str, dict]:
    out = {}
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            out[r["row_id"]] = r
    return out


def load_agent_labels() -> dict[str, list[str]]:
    """Return {row_id: [agent_label, ...]} from all agent label JSONL files."""
    out: dict[str, list[str]] = {}
    for path in sorted((DS / "review" / "agent_labels").glob("*.jsonl")):
        for line in path.open(encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            rid = r.get("row_id")
            lbl = r.get("label")
            if rid and lbl:
                out.setdefault(rid, []).append(lbl)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DS / "review" / "label_conflicts" / "lb_obo_conflicts.csv"))
    args = ap.parse_args()

    labels = load_labels()
    agent_labels = load_agent_labels()

    conflicts: list[dict] = []

    for row_id, meta in labels.items():
        if meta.get("label_source") != "human":
            continue
        label = meta.get("label", "")
        if label not in CONFLICT_PAIR:
            continue

        signals = []

        # Check agent-label disagreement in the conflict pair
        alabs = agent_labels.get(row_id, [])
        other = OBO if label == LB else LB
        if other in alabs:
            agent_votes = {l: alabs.count(l) for l in set(alabs)}
            signals.append(f"agent_vote:{agent_votes}")

        # Check also_* secondary fields (some label records carry them)
        for key in ("also_lb", "also_obo", "also_loop_boundary", "also_off_by_one"):
            if meta.get(key):
                signals.append(f"secondary_field:{key}")

        if signals:
            conflicts.append({
                "row_id": row_id,
                "current_label": label,
                "conflict_signal": "; ".join(signals),
                "relabel": "",
                "note": "",
            })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["row_id", "current_label", "conflict_signal", "relabel", "note"])
        writer.writeheader()
        writer.writerows(conflicts)

    print(f"Found {len(conflicts)} conflict candidates → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
