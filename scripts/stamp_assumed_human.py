"""Stamp the model pre-review sheets as signed, on the project owner's instruction.

    python scripts/stamp_assumed_human.py [--by "<who instructed>"] [--date YYYY-MM-DD]

On 2026-11-07 the project owner instructed that the pre-review verdicts be treated
as human labels for training and evaluation until real-life tests exist. This
script records that instruction in the sheets so `apply_prereview_signoff.py`
can run, without hiding what the labels are:

- `correct` / `incorrect` / `label` verdicts become `human_verdict = agree`, so
  the model's label is the label (an `incorrect` verdict therefore relabels);
- `uncertain` verdicts become `unsure` and stay undecided;
- `signed_off_by` says the signature is an instruction, not independent review,
  and `human_notes` repeats it.

Nothing here makes the labels independent. Any number measured against them is
agreement with a model-assisted reviewer, and the reports must say so. Re-running
is idempotent and never overwrites a real signature.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prereview_common import PREREVIEW_DIR, read_sheet, write_sheet  # noqa: E402

MARK = "assumed-human"
NOTE = "provenance: model pre-review accepted as human by owner instruction; not independent review"


def stamp(rows: list[dict], by: str, date: str) -> tuple[int, int, int]:
    agreed = unsure = kept = 0
    for r in rows:
        if (r.get("human_verdict") or "").strip() and MARK not in (r.get("signed_off_by") or ""):
            kept += 1                       # a real signature: leave it alone
            continue
        verdict = (r.get("model_verdict") or "").strip()
        if verdict == "uncertain" or not (r.get("model_label") or "").strip():
            r["human_verdict"] = "unsure"
            unsure += 1
        else:
            r["human_verdict"] = "agree"
            agreed += 1
        r["human_label"] = ""
        r["signed_off_by"] = f"{MARK} ({by})"
        r["signed_off_at"] = date
        r["human_notes"] = NOTE
    return agreed, unsure, kept


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--by", default="project owner instruction")
    ap.add_argument("--date", default="2026-11-07")
    args = ap.parse_args(argv)
    for path in sorted(PREREVIEW_DIR.glob("*.csv")):
        rows = read_sheet(path)
        agreed, unsure, kept = stamp(rows, args.by, args.date)
        write_sheet(path, rows)
        print(f"{path.name}: agree {agreed}, unsure {unsure}, real signatures kept {kept}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
