"""Bring signed sheets exported from the sign-off page back into the repo.

    python scripts/import_signoff.py <exported.csv> [more.csv ...] [--dry-run]

Each exported CSV must match a sheet in ``review/model_prereview/`` by file
name. Only the human columns (``human_verdict``, ``human_label``,
``signed_off_by``, ``signed_off_at``, ``human_notes``) are copied; every other
column must be unchanged, so an edited model verdict or a reordered sheet is
refused instead of silently merged. A row already signed in the repo is never
overwritten by a different signature (refused, so two people do not clobber
each other); signing it again identically is fine.

Then run ``scripts/apply_prereview_signoff.py`` (``--dry-run`` first).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prereview_common import COLUMNS, HUMAN_VERDICTS, PREREVIEW_DIR, read_sheet, write_sheet  # noqa: E402

HUMAN_COLS = ["human_verdict", "human_label", "signed_off_by", "signed_off_at", "human_notes"]
FIXED_COLS = [c for c in COLUMNS if c not in HUMAN_COLS]
CLASSES = {"CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS", "CPP_UNINITIALIZED_VAR",
           "CPP_INT_OVERFLOW", "CPP_MISSING_BASE_CASE", "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR",
           "CPP_RANGE_CHECK", "CPP_STALE_EXIT", "CPP_OTHER_ERROR"}


class ImportRefused(ValueError):
    pass


def validate_row(r: dict) -> None:
    v = (r.get("human_verdict") or "").strip().lower()
    if not v:
        return
    if v not in HUMAN_VERDICTS:
        raise ImportRefused(f"{r['item_id']}: human_verdict {v!r} is not agree / disagree / unsure")
    if not (r.get("signed_off_by") or "").strip():
        raise ImportRefused(f"{r['item_id']}: signed without signed_off_by")
    if v == "disagree" and (r.get("human_label") or "").strip() not in CLASSES | {"UNCERTAIN"}:
        raise ImportRefused(f"{r['item_id']}: disagree needs human_label in tl-cpp-v2 or UNCERTAIN")


def merge_sheet(repo_rows: list[dict], signed_rows: list[dict]) -> tuple[list[dict], int]:
    """Copy human columns from ``signed_rows`` into ``repo_rows``; returns (rows, newly signed)."""
    if [r["item_id"] for r in repo_rows] != [r["item_id"] for r in signed_rows]:
        raise ImportRefused("item ids or their order differ from the repo sheet")
    out, n_new = [], 0
    for cur, new in zip(repo_rows, signed_rows):
        changed = [c for c in FIXED_COLS if (cur.get(c) or "") != (new.get(c) or "")]
        if changed:
            raise ImportRefused(f"{cur['item_id']}: non-human column(s) changed: {', '.join(changed)}")
        validate_row(new)
        merged = dict(cur)
        if (new.get("human_verdict") or "").strip():
            if (cur.get("human_verdict") or "").strip():
                if any((cur.get(c) or "") != (new.get(c) or "") for c in HUMAN_COLS):
                    raise ImportRefused(f"{cur['item_id']}: already signed differently in the repo "
                                        f"(by {cur.get('signed_off_by')}); resolve it by hand")
            else:
                n_new += 1
            for c in HUMAN_COLS:
                merged[c] = (new.get(c) or "").strip()
            merged["human_verdict"] = merged["human_verdict"].lower()
        out.append(merged)
    return out, n_new


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--sheet-dir", type=Path, default=PREREVIEW_DIR)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rc = 0
    for f in a.files:
        target = a.sheet_dir / f.name
        if not target.exists():
            print(f"REFUSED {f.name}: no sheet of that name in {a.sheet_dir}")
            rc = 1
            continue
        try:
            rows, n_new = merge_sheet(read_sheet(target), read_sheet(f))
        except ImportRefused as e:
            print(f"REFUSED {f.name}: {e}")
            rc = 1
            continue
        signed = sum(1 for r in rows if r.get("human_verdict"))
        print(f"{f.name}: {n_new} newly signed, {signed}/{len(rows)} signed in total"
              + (" (dry run)" if a.dry_run else ""))
        if not a.dry_run:
            write_sheet(target, rows)
    if rc == 0 and not a.dry_run:
        print("next: python scripts/apply_prereview_signoff.py --dry-run")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
