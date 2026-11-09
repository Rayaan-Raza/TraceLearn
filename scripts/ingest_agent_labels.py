"""Turn the annotator consensus into dataset rows (`tier1f_agent_labelled.jsonl`).

    wsl python3 scripts/ingest_agent_labels.py --raw-root /mnt/g/TraceLearn/Datasets_RAW

Reads `review/agent_labels/consensus.json` (from `aggregate_agent_labels.py consensus`), the
pool manifest and the cached oracle-test executions, and writes one row per item whose label
is not UNCERTAIN and whose submission is listed in the normalized index (the merge's G1 join).

Provenance, stated on every row: the labels come from independent annotator agents (two
agree, or two of three after adjudication) and are marked `human` / `agent_consensus` on the
owner's instruction (2026-11-08) that they be treated as verified. They are model-made labels
agreed between annotators of the same model family, not independent human review, and any
number measured against them is agreement with those annotators.

PROGPedia problems listed in `splits/progpedia_holdout.csv` land in the held-out `test`
split through the merge; the rest are training rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

DS = ROOT / "data" / "misconception_dataset"
POOL = DS / "cache" / "pg_pool"
OUT = DS / "annotations" / "tier1f_agent_labelled.jsonl"
INDEX = ROOT / "data" / "Data_from_Datasets" / "intermediate" / "normalized" / "submissions" / "submissions.csv"
SIGNED = ("agent consensus (independent annotator agents; owner instruction 2026-11-08 to treat as verified; "
          "not independent human review)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, required=True)
    a = ap.parse_args()
    from label_progpedia_exec import problem_context
    from label_weak_codestream import slim_runtime, slim_tests

    consensus = json.loads((DS / "review" / "agent_labels" / "consensus.json").read_text(encoding="utf-8"))
    manifest = {m["item_id"]: m for m in json.loads((POOL / "manifest.json").read_text(encoding="utf-8"))}
    executed = {}
    for line in (POOL / "exec.jsonl").open(encoding="utf-8"):
        rec = json.loads(line)
        executed[rec["item_id"]] = rec["result"]
    csv.field_size_limit(2**31 - 1)
    with open(INDEX, encoding="utf-8-sig", newline="") as f:
        known = {r["source_record_id"] for r in csv.DictReader(f) if r.get("dataset_source") == "PROGPEDIA"}
    tier1b_ctx = {}
    for line in (DS / "annotations" / "tier1b_progpedia.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if isinstance(r.get("context"), dict):
            tier1b_ctx.setdefault(r["problem_id"], r["context"])
    contexts = {}
    rows, skipped = [], {"uncertain": 0, "not_indexed": 0}
    for item, c in sorted(consensus.items()):
        m = manifest[item]
        if c["label"] == "UNCERTAIN":
            skipped["uncertain"] += 1
            continue
        if m["source_record_id"] not in known:
            skipped["not_indexed"] += 1
            continue
        pid = m["problem_id"]
        if pid not in contexts:
            contexts[pid] = problem_context(a.raw_root, pid, tier1b_ctx)
        res = executed[item]
        rows.append({
            "row_id": f"pgx-a{int(item[3:]):05d}", "dataset_source": "PROGPEDIA",
            "source_record_id": m["source_record_id"],
            "source_code_path": f"{m['raw_copy']}/{m['source_record_id']}",
            "submission_id": None, "problem_id": pid, "problem_cluster": None, "language": m["lang"],
            "label": c["label"], "label_source": "human",
            "label_confidence": 1.0 if c["how"] == "A=B" else 0.7, "label_status": "agent_consensus",
            "secondary_labels": [], "verdict": m["verdict"], "firing_functions": [], "firing_count": 0, "lf_evidence": [],
            "audit": {"key": "agent_consensus", "item_id": item, "signed_off_by": SIGNED, "how": c["how"],
                      "A": c["A"], "B": c["B"], "C": c["C"], "note": c["note"]},
            "seed_ref": None, "mutation_op": None, "repair": None, "verified_by_execution": False,
            "meta": {"user_id_hash": hashlib.sha256(f"progpedia:{m['source_record_id'].split('/')[2].split('_')[0]}".encode()).hexdigest()[:16],
                     "attempt_index": None, "timestamp": None, "prev_submission_id": None,
                     "code_sha256": m["sha"], "raw_copy": m["raw_copy"]},
            "static": None,
            "warnings": {"_compiled": True, **((res.get("warnings") or {}).get("count_by_flag") or {})},
            "runtime": slim_runtime(res), "tests": slim_tests(res), "cpg": None, "context": contexts[pid],
            "test_source": "oracle", "evidence_vocab": "sandbox_runner",
            "pipeline_run_id": "ingest_agent_labels/1.0.0", "taxonomy_version": "tl-cpp-v2", "schema_version": "1.1",
        })
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    print(f"wrote {len(rows)} rows, skipped {skipped} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
