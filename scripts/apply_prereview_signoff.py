"""Turn signed-off model pre-review sheets into labels and audits.

    python scripts/apply_prereview_signoff.py [--raw-root DIR] [--dry-run]

Reads every sheet in ``review/model_prereview/*.csv`` (format:
``prereview_common.py``). A model verdict becomes data only through a person:

* a row a person signed (``human_verdict`` agree / disagree) is decided by the
  person — agree keeps the model label, disagree uses ``human_label``;
* the rest of a sheet is accepted on the model's word **only** when every
  ``spotcheck=1`` row is signed and people agreed with the model on at least
  90% of the signed rows (``unsure`` rows do not count either way);
* otherwise unsigned rows change nothing;
* rows in a held-out evaluation pool (``dev_gold`` / ``test_iid`` in the last
  merge's ``splits/splits.csv``) are gold: only a person's signature decides
  them, on any sheet, never spot-check acceptance.

Effects
* ``weak_labels_*`` sheets → ``annotations/label_review_decisions.jsonl``
  (confirm / relabel / reject per existing row; the merge applies it) and the
  per-LF audit counts in ``annotations/lf_audits.csv`` (Beta-bound confidence).
* ``dev_gold_*`` / ``iid_test_*`` sheets → new human-labeled rows in
  ``annotations/tier1d_human_review.jsonl``, re-executed from the raw code so
  they carry the same evidence as lane rows. A sheet row that already exists
  in a lane becomes a confirm / relabel decision instead (never a duplicate).
* ``review/model_prereview/signoff_report.md`` — what was decided and why.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from prereview_common import (  # noqa: E402
    ACCEPT_AGREEMENT,
    HUMAN_VERDICTS,
    PREREVIEW_DIR,
    read_sheet,
)

DS = ROOT / "data" / "misconception_dataset"
DECISIONS = DS / "annotations" / "label_review_decisions.jsonl"
TIER1D = DS / "annotations" / "tier1d_human_review.jsonl"
AUDITS = DS / "annotations" / "lf_audits.csv"
REPORT = PREREVIEW_DIR / "signoff_report.md"
CLASSES = {"CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS", "CPP_UNINITIALIZED_VAR",
           "CPP_INT_OVERFLOW", "CPP_MISSING_BASE_CASE", "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR",
           "CPP_RANGE_CHECK", "CPP_STALE_EXIT", "CPP_OTHER_ERROR"}


def sheet_status(rows: list[dict]) -> dict:
    signed = [r for r in rows if (r.get("human_verdict") or "").strip().lower() in HUMAN_VERDICTS]
    spot = [r for r in rows if r.get("spotcheck") == "1"]
    spot_signed = [r for r in spot if r in signed]
    agree = sum(1 for r in signed if r["human_verdict"].strip().lower() == "agree")
    disagree = sum(1 for r in signed if r["human_verdict"].strip().lower() == "disagree")
    judged = agree + disagree
    agreement = agree / judged if judged else None
    accepted = bool(spot) and len(spot_signed) == len(spot) and agreement is not None \
        and agreement >= ACCEPT_AGREEMENT
    return {"rows": len(rows), "signed": len(signed), "spotcheck": len(spot),
            "spotcheck_signed": len(spot_signed), "agree": agree, "disagree": disagree,
            "agreement": agreement, "accepted_on_spotcheck": accepted}


def decide_row(r: dict, accepted: bool) -> tuple[str | None, str | None]:
    """(final_label, basis) for one sheet row, or (None, None) when undecided."""
    hv = (r.get("human_verdict") or "").strip().lower()
    if hv == "agree":
        return r["model_label"], "human"
    if hv == "disagree":
        lab = (r.get("human_label") or "").strip()
        if lab not in CLASSES and lab != "UNCERTAIN":
            raise ValueError(f"{r['item_id']}: disagree needs human_label in tl-cpp-v2 or UNCERTAIN, got {lab!r}")
        return lab, "human"
    if hv == "unsure":
        return None, None
    if accepted and r.get("model_verdict") != "uncertain" and r.get("model_label") in CLASSES:
        return r["model_label"], "model_prereview_spotchecked"
    return None, None


GOLD_SPLITS = {"dev_gold", "test_iid"}


def gold_row_ids() -> set[str]:
    path = DS / "splits" / "splits.csv"
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {r["row_id"] for r in csv.DictReader(f) if r["split"] in GOLD_SPLITS}


def may_accept_on_spotcheck(sheet_name: str, row_id: str, sheet_accepted: bool, gold: set[str]) -> bool:
    """Spot-check acceptance applies only to weak-label audit rows outside the gold pools."""
    return sheet_accepted and sheet_name.startswith("weak_labels_") and row_id not in gold


def lane_rows() -> dict[str, dict]:
    out = {}
    for p in sorted((DS / "annotations").glob("tier*.jsonl")):
        if p.name == TIER1D.name:
            continue
        for line in p.open(encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                out[r["row_id"]] = r
    return out


def build_human_row(item: dict, label: str, raw_root: Path | None) -> dict | None:
    """Re-execute the item's own code against its tests and wrap it as a human row."""
    from label_weak_codestream import slim_runtime, slim_tests

    from sandbox_runner import RunConfig, run_submission
    src = item["dataset_source"]
    if raw_root is None:
        return None
    if src == "CODESTREAM":
        from codestream_common import find_raw, load_problems, load_submissions
        raw = find_raw(str(raw_root))
        subs = {s.submission_id: s for s in load_submissions(raw)}
        s = subs.get(item["submission_id"])
        if s is None:
            return None
        code, lang, tests = s.code, s.lang, load_problems(raw)[s.problem_id].tests
        rec_id, verdict = s.source_submission_id, s.verdict
    elif src == "PROGPEDIA":
        import progpedia_oracle_tests as oracle
        tests = oracle.load_tests(item["problem_id"])
        path = next((raw_root / c / item["source_record_id"] for c in oracle.COPIES
                     if (raw_root / c / item["source_record_id"]).exists()), None)
        if not tests or path is None:
            return None
        code = path.read_text(encoding="utf-8", errors="replace")
        lang = "c" if path.suffix == ".c" else "cpp"
        rec_id, verdict = item["source_record_id"], item["source_record_id"].split("/")[1]
    else:
        return None
    res = run_submission(code, lang, tests, RunConfig(sanitizer_max_input_bytes=20_000,
                                                     valgrind_max_input_bytes=20_000,
                                                     slow_pass_skip_timeouts=True))
    return {
        "row_id": f"hr-{item['item_id'].lower()}",
        "dataset_source": src, "source_record_id": rec_id,
        "submission_id": item.get("submission_id") or None, "problem_id": item["problem_id"],
        "problem_cluster": None, "language": lang, "label": label, "label_source": "human",
        "label_confidence": 1.0, "label_status": "human_review", "secondary_labels": [],
        "verdict": verdict, "firing_functions": [], "firing_count": 0, "lf_evidence": [],
        "audit": {"key": "human", "item_id": item["item_id"], "signed_off_by": item.get("signed_off_by")},
        "seed_ref": None, "mutation_op": None, "repair": None, "verified_by_execution": False,
        "meta": {"user_id_hash": None, "attempt_index": None, "timestamp": None, "prev_submission_id": None},
        "static": None,
        "warnings": {"_compiled": True, **((res.get("warnings") or {}).get("count_by_flag") or {})},
        "runtime": slim_runtime(res), "tests": slim_tests(res), "cpg": None,
        "context": None, "evidence_vocab": "sandbox_runner",
        "pipeline_run_id": "apply_prereview_signoff/1.0.0", "taxonomy_version": "tl-cpp-v2",
        "schema_version": "1.1",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, default=None,
                    help="Datasets_RAW (CodeStream CSVs and progpedia/); needed for new dev-gold / IID rows")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    lanes = lane_rows()
    gold = gold_row_ids()
    decisions, new_rows, audits = [], [], defaultdict(lambda: [0, 0, set()])
    lines = ["# Pre-review sign-off report", "",
             "Generated by `scripts/apply_prereview_signoff.py`. A model verdict counts only "
             f"after a person signs it, or when every spot-check row is signed with ≥{int(ACCEPT_AGREEMENT*100)}% "
             "agreement (then the rest of that sheet is accepted on the model's word).", "",
             "| Sheet | Rows | Signed | Spot-check signed | Agreement | Accepted on spot-check | Decisions |",
             "|---|---:|---:|---:|---:|---|---:|"]
    for path in sorted(PREREVIEW_DIR.glob("*.csv")):
        rows = read_sheet(path)
        st = sheet_status(rows)
        n_dec = 0
        for r in rows:
            label, basis = decide_row(r, may_accept_on_spotcheck(path.name, r.get("row_id") or "",
                                                                st["accepted_on_spotcheck"], gold))
            if label is None:
                continue
            n_dec += 1
            target = lanes.get(r.get("row_id") or "")
            if target is not None:
                cur = target["label"]
                if label == cur:
                    action = "confirm"
                elif label == "UNCERTAIN" or basis != "human":
                    action = "reject"  # a model alone never relabels
                else:
                    action = "relabel"
                decisions.append({"row_id": target["row_id"], "action": action,
                                  "label": label if action == "relabel" else cur, "basis": basis,
                                  "item_id": r["item_id"], "signed_off_by": r.get("signed_off_by") or None})
                # any signed / accepted verdict on a lane row is an audit of its LFs
                for key in (r.get("firing_functions") or "").split("|"):
                    if key:
                        audits[key][0] += 1
                        audits[key][1] += int(label == cur)
                        audits[key][2].add(basis)
                if target.get("label_source") == "repair_verified":
                    k = f"repair_verified:{cur}"
                    audits[k][0] += 1
                    audits[k][1] += int(label == cur)
                    audits[k][2].add(basis)
            elif not path.name.startswith("weak_labels_") and basis == "human" and label != "UNCERTAIN":
                row = None if a.dry_run else build_human_row(r, label, a.raw_root)
                if row is not None:
                    new_rows.append(row)
        acc = f"{st['agreement']:.0%}" if st["agreement"] is not None else "—"
        lines.append(f"| {path.name} | {st['rows']} | {st['signed']} | {st['spotcheck_signed']}/{st['spotcheck']} | "
                     f"{acc} | {'yes' if st['accepted_on_spotcheck'] else 'no'} | {n_dec} |")

    actions = Counter(d["action"] for d in decisions)
    lines += ["", f"Decisions on existing rows: {dict(actions) or 'none'} · new human-labeled rows: {len(new_rows)}", ""]
    if a.dry_run:
        print("\n".join(lines))
        return 0
    with open(DECISIONS, "w", encoding="utf-8", newline="\n") as f:
        for d_ in decisions:
            f.write(json.dumps(d_) + "\n")
    with open(TIER1D, "w", encoding="utf-8", newline="\n") as f:
        for row in new_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if audits:
        existing = {}
        if AUDITS.exists():
            with open(AUDITS, encoding="utf-8") as f:
                existing = {r["key"]: r for r in csv.DictReader(f)}
        today = dt.date.today().isoformat()
        for key, (n, k, bases) in audits.items():
            auditor = "human" if bases == {"human"} else "model pre-review + human spot-check"
            existing[key] = {"key": key, "audited": n, "correct": k, "auditor": auditor, "date": today,
                             "notes": "apply_prereview_signoff.py"}
        with open(AUDITS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["key", "audited", "correct", "auditor", "date", "notes"],
                               lineterminator="\n")
            w.writeheader()
            for key in sorted(existing):
                w.writerow({c: existing[key].get(c, "") for c in w.fieldnames})
        lines += ["| Audit key | Audited | Correct |", "|---|---:|---:|"]
        lines += [f"| {k} | {v[0]} | {v[1]} |" for k, v in sorted(audits.items())]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
