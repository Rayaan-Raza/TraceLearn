"""U1: separate code origin, label origin and reviewer type (master plan, G1).

`label_source == "human"` conflates agent consensus, assumed-human sign-off and
real human review. This module derives three explicit fields per row and writes
them to a sidecar (annotations/label_provenance.csv). labels.jsonl is NOT edited:
it is hash-pinned in the dataset manifest, and every script that selects on
`label_source` must keep selecting exactly the same rows (G3 numbers depend on it).

    python scripts/label_provenance.py            # write sidecar + print counts
    python scripts/label_provenance.py --check    # fail if sidecar is stale
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
FIELDS = ["row_id", "label_source", "code_origin", "label_origin", "reviewer_type"]

# Label origins that used to be reported as `label_source == "human"`. Written out on purpose: it
# shows that agent-consensus and assumed-human rows are in this set. A script that selects with this
# list keeps exactly the rows it selected with the old flag (tests/test_label_provenance.py checks
# that against the committed labels.jsonl). "legacy_human_flag" is a human-flagged row with no
# recorded origin; it is kept so that such a row is not dropped silently.
HUMAN_FLAG_LABEL_ORIGINS = ("agent_consensus", "blind_review", "human_review", "legacy_human_flag")
# The only rows a named person signed: reviewer_type human_signed.
HUMAN_SIGNED = "human_signed"

CODE_ORIGIN = {"SYNTHETIC": "synthetic_mutant"}  # everything else is a real student submission


def _signer(row: dict) -> str:
    review = row.get("review") or {}
    audit = row.get("audit") or {}
    return str(review.get("signed_off_by") or audit.get("signed_off_by") or "").strip()


def _reviewer_from_signer(signer: str) -> str:
    s = signer.lower()
    if not s:
        return "none_recorded"
    if s.startswith("assumed-human"):
        return "human_assumed"
    if s.startswith("agent consensus"):
        return "model_agents"
    return "human_signed"


def derive_provenance(row: dict) -> dict:
    """Return code_origin, label_origin, reviewer_type for one labels.jsonl row."""
    code_origin = CODE_ORIGIN.get(row.get("dataset_source"), "real_student")
    src, status = row.get("label_source"), row.get("label_status")
    review = row.get("review") or {}

    if src == "synthetic":
        return {"code_origin": code_origin, "label_origin": "synthetic_by_construction", "reviewer_type": "none"}
    if review.get("basis") == "human":  # explicit per-row human decision overrides the tier label
        return {"code_origin": code_origin, "label_origin": "human_review",
                "reviewer_type": _reviewer_from_signer(str(review.get("signed_off_by") or ""))}
    if status == "agent_consensus":
        return {"code_origin": code_origin, "label_origin": "agent_consensus", "reviewer_type": "model_agents"}
    if status == "blind_review":
        return {"code_origin": code_origin, "label_origin": "blind_review",
                "reviewer_type": _reviewer_from_signer(_signer(row))}
    if status == "human_review":
        return {"code_origin": code_origin, "label_origin": "human_review",
                "reviewer_type": _reviewer_from_signer(_signer(row))}
    if status == "repair_verified":
        return {"code_origin": code_origin, "label_origin": "repair_verified", "reviewer_type": "execution"}
    if status == "weak_rule" or src == "weak_rule":
        return {"code_origin": code_origin, "label_origin": "weak_rule", "reviewer_type": "rule"}
    return {"code_origin": code_origin, "label_origin": "legacy_human_flag", "reviewer_type": _reviewer_from_signer(_signer(row))}


def has_human_flag_origin(row: dict) -> bool:
    """True for the rows `label_source == "human"` used to select (see HUMAN_FLAG_LABEL_ORIGINS)."""
    return derive_provenance(row)["label_origin"] in HUMAN_FLAG_LABEL_ORIGINS


def is_human_signed(row: dict) -> bool:
    """True when a named person signed this row's label (not assumed-human, not agent consensus)."""
    return derive_provenance(row)["reviewer_type"] == HUMAN_SIGNED


def build_rows(labels_path: Path) -> list[dict]:
    out = []
    with labels_path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                out.append({"row_id": r["row_id"], "label_source": r.get("label_source"), **derive_provenance(r)})
    return sorted(out, key=lambda x: str(x["row_id"]))


def card_table(ds: Path) -> str:
    """Markdown table for DATASET_CARD.md: code origin x label origin x reviewer type, by split."""
    rows = build_rows(ds / "annotations" / "labels.jsonl")
    with (ds / "splits" / "splits.csv").open(encoding="utf-8") as fh:
        split = {r["row_id"]: r["split"] for r in csv.DictReader(fh)}
    order = ["train", "dev_gold", "test", "test_iid"]
    seen = sorted({split.get(r["row_id"], "unsplit") for r in rows},
                  key=lambda s: (order.index(s) if s in order else 99, s))
    cnt = Counter((r["code_origin"], r["label_origin"], r["reviewer_type"], split.get(r["row_id"], "unsplit"))
                  for r in rows)
    keys = sorted({k[:3] for k in cnt}, key=lambda k: (-sum(v for kk, v in cnt.items() if kk[:3] == k), k))
    out = ["| code origin | label origin | reviewer type | " + " | ".join(seen) + " | total |",
           "|---|---|---|" + "---:|" * (len(seen) + 1)]
    for k in keys:
        vals = [cnt.get((*k, s), 0) for s in seen]
        out.append(f"| {k[0]} | {k[1]} | {k[2]} | " + " | ".join(f"{v:,}" for v in vals) + f" | {sum(vals):,} |")
    tot = [sum(v for kk, v in cnt.items() if kk[3] == s) for s in seen]
    out.append("| **all rows** | | | " + " | ".join(f"**{v:,}**" for v in tot) + f" | **{sum(tot):,}** |")
    return "\n".join(out)


def _render(rows: list[dict]) -> str:
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", type=Path, default=DS)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--card-table", action="store_true", help="print the DATASET_CARD.md provenance table")
    a = ap.parse_args(argv)
    if a.card_table:
        print(card_table(a.dataset_dir))
        return 0
    rows = build_rows(a.dataset_dir / "annotations" / "labels.jsonl")
    out =a.dataset_dir / "annotations" / "label_provenance.csv"
    text = _render(rows)
    if a.check:
        if not out.exists() or out.read_text(encoding="utf-8") != text:
            print("label_provenance.csv is stale; rerun scripts/label_provenance.py")
            return 1
        print("label_provenance.csv up to date")
        return 0
    out.write_text(text, encoding="utf-8", newline="")
    c = Counter((r["label_source"], r["label_origin"], r["reviewer_type"]) for r in rows)
    for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
        print(f"{v:5d}  {k}")
    print(f"{len(rows)} rows -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
