"""Turn the frozen blind labels into dataset rows (`tier1e_blind_review.jsonl`).

    wsl python3 scripts/ingest_blind_labels.py

Reads `review/blind_labels/{test,train_queue,tr2}.json` (tr2 = the 322 unlabelled real
training-pool failures, read in priority order; identical code inherits its twin's label) and the batch manifests plus the
cached executions written by `build_label_batches.py`, and writes one row per labelled
item (UNCERTAIN items are skipped). The merge then places each row by its problem's
cluster: test-cluster rows land in the held-out `test` split and never reach
training; train-queue rows are real OTHER_ERROR (and a few other) training rows.

Provenance is explicit on every row: `label_source = human` because the owner
instructed on 2026-11-07 that blind model-assisted labels are treated as human
labels, and `audit.signed_off_by` says so. They are not independent review, and any
number measured against them is agreement with that reviewer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "annotations" / "tier1e_blind_review.jsonl"
SET_PREFIX = {"test": "te", "train_queue": "tr"}
SIGNED = "assumed-human (blind labels by a model-assisted reviewer; owner instruction 2026-11-07)"


def build_row(item_id: str, label: str, note: str, sub, result: dict, prefix: str = "") -> dict:
    from label_weak_codestream import slim_runtime, slim_tests

    return {
        "row_id": f"bl-{prefix}{item_id.lower()}", "dataset_source": "CODESTREAM", "source_record_id": sub.source_submission_id,
        "submission_id": sub.submission_id, "problem_id": sub.problem_id, "problem_cluster": None,
        "language": sub.lang, "label": label, "label_source": "human", "label_confidence": 1.0,
        "label_status": "blind_review", "secondary_labels": [], "verdict": sub.verdict, "firing_functions": [],
        "firing_count": 0, "lf_evidence": [],
        "audit": {"key": "human", "item_id": item_id, "signed_off_by": SIGNED, "note": note},
        "seed_ref": None, "mutation_op": None, "repair": None, "verified_by_execution": False,
        "meta": {"user_id_hash": None, "attempt_index": sub.attempt_number, "timestamp": None, "prev_submission_id": None},
        "static": None, "warnings": {"_compiled": True, **((result.get("warnings") or {}).get("count_by_flag") or {})},
        "runtime": slim_runtime(result), "tests": slim_tests(result), "cpg": None, "context": None,
        "evidence_vocab": "sandbox_runner", "pipeline_run_id": "ingest_blind_labels/1.0.0",
        "taxonomy_version": "tl-cpp-v2", "schema_version": "1.1",
    }


def _code_key(code: str) -> str:
    import hashlib
    import re
    stripped = re.sub(r"//[^\n]*|/\*.*?\*/", "", code, flags=re.S)
    return hashlib.md5(re.sub(r"\s+", "", stripped).encode()).hexdigest()


def main() -> int:
    from codestream_common import find_raw, load_submissions

    raw = find_raw("/mnt/g/TraceLearn/Datasets_RAW")
    subs = {s.submission_id: s for s in load_submissions(raw)}
    rows, skipped = [], 0
    for name in ("test", "train_queue", "tr2"):
        labels = json.loads((DS / "review" / "blind_labels" / f"{name}.json").read_text(encoding="utf-8"))
        manifest = json.loads((DS / "cache" / "label_batches" / name / "manifest.json").read_text(encoding="utf-8"))
        executed = {}
        for line in (DS / "cache" / f"label_exec_{name}.jsonl").open(encoding="utf-8"):
            rec = json.loads(line)
            executed[rec["submission_id"]] = rec["result"]
        by_code: dict[str, dict] = {}
        for m in manifest:                      # identical normalised code carries the same label
            lab = labels.get(m["item_id"])
            if lab and lab["label"] != "UNCERTAIN" and m["submission_id"] in subs:
                by_code.setdefault(_code_key(subs[m["submission_id"]].code), lab)
        for m in manifest:
            lab = labels.get(m["item_id"])
            if lab is None and name == "tr2" and m["submission_id"] in subs:
                twin = by_code.get(_code_key(subs[m["submission_id"]].code))
                if twin:
                    lab = {"label": twin["label"], "note": "identical code to a labelled item: " + twin["note"]}
            if lab is None or lab["label"] == "UNCERTAIN" or m["submission_id"] not in executed:
                skipped += 1
                continue
            rows.append(build_row(m["item_id"], lab["label"], lab["note"], subs[m["submission_id"]], executed[m["submission_id"]],
                                  "t2-" if name == "tr2" else ""))
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    print(f"wrote {len(rows)} rows (skipped {skipped}) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
