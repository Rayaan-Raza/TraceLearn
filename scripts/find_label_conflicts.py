"""Find LOOP_BOUNDARY / OFF_BY_ONE labelling conflicts and write a review queue.

    python scripts/find_label_conflicts.py [--out data/misconception_dataset/review/label_conflicts/lb_obo_conflicts.csv]

A conflict row is a real (non-synthetic) row labelled LOOP_BOUNDARY or OFF_BY_ONE whose own
execution evidence points at the other class:

* **repair evidence** (the main signal): the other class's single-edit repair makes every test
  pass (`repair.<other>_fix_all = 1`), with or without its own class's repair also doing so.
  The repairs are the two inverse operators of the boundary rule (operator flip for
  LOOP_BOUNDARY, operand +-1 for OFF_BY_ONE), so this is exactly where the rule decides;
* **agent votes**: an annotator agent chose the other class (only for row ids found in
  `review/agent_labels/*.jsonl`; the sharded A/B/C sheets are keyed by item id, not row id).

Output columns: row_id, problem_id, current_label, conflict_signal, relabel (blank, for a
person), note (blank). The boundary rule is section 6 of
data/misconception_dataset/ANNOTATION_GUIDELINE.md.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"

LB = "CPP_LOOP_BOUNDARY"
OBO = "CPP_OFF_BY_ONE"
CONFLICT_PAIR = {LB, OBO}
FIX_ALL = {LB: "repair.loop_boundary_fix_all", OBO: "repair.off_by_one_fix_all"}
FIELDS = ["row_id", "problem_id", "current_label", "conflict_signal", "relabel", "note"]


def load_labels() -> dict[str, dict]:
    out = {}
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            out[r["row_id"]] = r
    return out


def load_features() -> dict[str, dict[str, str]]:
    path = DS / "features" / "features.csv"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["row_id"]: r for r in csv.DictReader(fh)}


def load_agent_labels() -> dict[str, list[str]]:
    """Return {row_id: [agent_label, ...]} from agent label JSONL files keyed by row id."""
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


def _flag(features: Mapping[str, Any], name: str) -> bool:
    try:
        return float(features.get(name) or 0) >= 1.0
    except (TypeError, ValueError):
        return False


def conflict_signals(label: str, features: Mapping[str, Any], agent_votes: list[str]) -> list[str]:
    """Why a row labelled LB or OBO may belong to the other class (empty list: no conflict)."""
    if label not in CONFLICT_PAIR:
        return []
    other = OBO if label == LB else LB
    signals = []
    if _flag(features, FIX_ALL[other]):
        own = _flag(features, FIX_ALL[label])
        signals.append(f"repair:{FIX_ALL[other].split('.')[1]}=1,{FIX_ALL[label].split('.')[1]}={int(own)}")
    if other in agent_votes:
        signals.append(f"agent_vote:{ {v: agent_votes.count(v) for v in sorted(set(agent_votes))} }")
    return signals


def find_conflicts(labels: Mapping[str, dict], features: Mapping[str, Mapping[str, Any]],
                   agent_labels: Mapping[str, list[str]]) -> list[dict]:
    out = []
    for row_id, meta in sorted(labels.items()):
        if meta.get("dataset_source") == "SYNTHETIC":
            continue  # a synthetic row's label is its mutation operator; nothing to review
        signals = conflict_signals(meta.get("label", ""), features.get(row_id, {}), agent_labels.get(row_id, []))
        if signals:
            out.append({"row_id": row_id, "problem_id": meta.get("problem_id", ""),
                        "current_label": meta["label"], "conflict_signal": "; ".join(signals),
                        "relabel": "", "note": ""})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DS / "review" / "label_conflicts" / "lb_obo_conflicts.csv"))
    args = ap.parse_args(argv)

    conflicts = find_conflicts(load_labels(), load_features(), load_agent_labels())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(conflicts)
    print(f"Found {len(conflicts)} conflict candidates -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
