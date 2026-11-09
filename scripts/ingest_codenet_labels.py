"""Turn the CodeNet annotator consensus into dataset rows (`tier1g_codenet_agent.jsonl`).

    python scripts/ingest_codenet_labels.py

Inputs: `review/agent_labels_cn/consensus.json` (scripts/aggregate_cn_labels.py), the pool's
`manifest.json` and `items.jsonl` (scripts/build_codenet_pool.py, reconciled by
scripts/reconcile_codenet_pool.py). Writes:

- `annotations/tier1g_codenet_agent.jsonl`: one row per item whose consensus label is not UNCERTAIN;
- `annotations/codenet_index.csv`: source_record_id -> source_code_path (relative to the raw root)
  and the code's hash, the traceability join for these rows (CodeNet is not in the normalized index);
- `splits/codenet_clusters.csv` (one train cluster per problem) and `splits/codenet_holdout.csv`
  (the held-out problems, `test`).

Provenance, on every row: labels from independent annotator agents (two agree, or two of three with
a blind adjudicator), marked `human` / `agent_consensus` like the PROGPedia agent lane (owner
instruction 2026-11-08 to treat agent consensus as verified; repeated 2026-11-09 for this lane).
They are not independent human review. Tests are derived: reference-solution outputs on the
statement samples plus generated inputs, so `test_source` is `derived_reference`.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

DS = ROOT / "data" / "misconception_dataset"
POOL = DS / "cache" / "cn_pool"
OUT = DS / "annotations" / "tier1g_codenet_agent.jsonl"
INDEX = DS / "annotations" / "codenet_index.csv"
CLUSTERS = DS / "splits" / "codenet_clusters.csv"
HOLDOUT = DS / "splits" / "codenet_holdout.csv"
RAW_PREFIX = "Project_CodeNet/Project_CodeNet/data"
HELDOUT_PROBLEMS = ("p02766", "p03803")   # = build_codenet_pool.HELDOUT_PROBLEMS (that module needs Linux)
SIGNED = ("agent consensus (independent annotator agents, blind adjudicator on disagreements; owner instruction "
          "to treat as verified; not independent human review)")


# Consensus labels that contradict the frozen taxonomy definition, corrected here with the reason.
# CN-0479: `b == 14;` (comparison written where an assignment was meant). CPP_ASSIGN_VS_COMPARE is
# "assignment operator inside a condition" (docs/master_plan_dataset.md section 3, class 7); the reverse
# slip is not that misconception. Annotator A's CPP_OTHER_ERROR stands.
TAXONOMY_CORRECTIONS = {"CN-0479": ("CPP_OTHER_ERROR", "ASSIGN_VS_COMPARE is `=` inside a condition; "
                                    "this is `==` as a statement")}


def problem_id(pid: str) -> str:
    return f"tl-codenet-{pid}"


def main() -> int:
    consensus = json.loads((DS / "review" / "agent_labels_cn" / "consensus.json").read_text(encoding="utf-8"))
    manifest = {m["item_id"]: m for m in json.loads((POOL / "manifest.json").read_text(encoding="utf-8"))}
    items = {s["item_id"]: s for s in map(json.loads, (POOL / "items.jsonl").open(encoding="utf-8"))}
    rows, index = [], []
    for item, c in sorted(consensus.items()):
        if c["label"] == "UNCERTAIN":
            continue
        m, s = manifest[item], items[item]
        pid = problem_id(m["problem_id"])
        correction = TAXONOMY_CORRECTIONS.get(item)
        if correction:
            c = {**c, "label": correction[0], "rule": "taxonomy_correction"}
        rows.append({
            "row_id": f"cnx-{int(item[3:]):05d}", "dataset_source": "CODENET",
            "source_record_id": f"codenet:{m['source_record_id']}",
            "source_code_path": f"{RAW_PREFIX}/{m['source_record_id']}",
            "submission_id": None, "problem_id": pid, "problem_cluster": None, "language": "cpp",
            "label": c["label"], "label_source": "human",
            "label_confidence": 1.0 if c["rule"] == "A=B" else 0.7, "label_status": "agent_consensus",
            "secondary_labels": [], "verdict": "WRONG_ANSWER", "firing_functions": [], "firing_count": 0, "lf_evidence": [],
            "audit": {"key": "agent_consensus", "item_id": item, "signed_off_by": SIGNED, "how": c["rule"],
                      "A": c["A"], "B": c["B"], "C": c["C"], "reconcile": c["reconcile"],
                      **({"correction": correction[1]} if correction else {})},
            "seed_ref": None, "mutation_op": None, "repair": None, "verified_by_execution": False,
            "meta": {"user_id_hash": None, "attempt_index": None, "timestamp": None, "prev_submission_id": None,
                     "code_sha256": None, "code_norm_md5": m["sha"],
                     "first_failing_input": s.get("first_input"), "tests_passed": s.get("tests_passed"),
                     "tests_total": s.get("tests_total")},
            "static": None, "warnings": None, "runtime": None, "tests": None, "cpg": None,
            "context": {"source": "codenet", "problem": m["problem_id"]},
            "test_source": "derived_reference", "evidence_vocab": "sandbox_runner",
            "pipeline_run_id": "ingest_codenet_labels/1.0.0", "taxonomy_version": "tl-cpp-v2", "schema_version": "1.1",
        })
        index.append({"source_record_id": f"codenet:{m['source_record_id']}",
                      "source_code_path": f"{RAW_PREFIX}/{m['source_record_id']}", "code_norm_md5": m["sha"]})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    with INDEX.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["source_record_id", "source_code_path", "code_norm_md5"], lineterminator="\n")
        w.writeheader()
        w.writerows(index)
    problems = sorted({r["problem_id"] for r in rows})
    with CLUSTERS.open("w", newline="", encoding="utf-8") as fh:
        fh.write("problem_id,cluster_id,split,statement_len\n")
        for pid in problems:
            fh.write(f"{pid},{pid},train,0\n")
    with HOLDOUT.open("w", newline="", encoding="utf-8") as fh:
        fh.write("problem_id,pool\n")
        for p in HELDOUT_PROBLEMS:
            fh.write(f"{problem_id(p)},test\n")
    held = sum(r["problem_id"] in {problem_id(p) for p in HELDOUT_PROBLEMS} for r in rows)
    print(f"wrote {len(rows)} rows ({held} on held-out problems) over {len(problems)} problems -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
