"""Validate the committed Lane B artifacts (run in CI; no raw data needed).

    python scripts/check_lane_b_artifacts.py

Checks
* splits: every problem has one cluster, every cluster exactly one pool;
* tier1a rows: required fields and enums, unique row ids, pool matches the
  frozen split, repair_verified ⇔ stored repair proof, confidence ≤ cap,
  never an automatic OTHER_ERROR, never source code;
* review pools: nothing in them carries a training label source;
* blind forms and the hidden key are not tracked by git.

Exit code 1 on any failure; every problem is printed.
"""

from __future__ import annotations

import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
CLASSES = {"CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS", "CPP_UNINITIALIZED_VAR",
           "CPP_INT_OVERFLOW", "CPP_MISSING_BASE_CASE", "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR",
           "CPP_RANGE_CHECK", "CPP_STALE_EXIT", "CPP_OTHER_ERROR"}
POOLS = {"train", "dev_gold", "test"}
REQUIRED = ["row_id", "dataset_source", "source_record_id", "problem_id", "problem_cluster",
            "split_pool", "language", "label", "label_source", "label_confidence",
            "secondary_labels", "firing_functions", "verified_by_execution", "meta", "runtime",
            "tests", "pipeline_run_id", "taxonomy_version", "schema_version"]
CAP = 0.85


def _jsonl(p: Path):
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def check(root: Path = ROOT) -> list[str]:
    ds = root / "data" / "misconception_dataset"
    errs: list[str] = []

    split_path = ds / "splits" / "codestream_clusters.csv"
    pool_of_problem, cluster_of_problem = {}, {}
    pools_of_cluster = defaultdict(set)
    if not split_path.exists():
        errs.append(f"missing {split_path.relative_to(root)}")
    else:
        with open(split_path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["problem_id"] in pool_of_problem:
                    errs.append(f"split: duplicate problem {r['problem_id']}")
                if r["pool"] not in POOLS:
                    errs.append(f"split: bad pool {r['pool']!r} for {r['problem_id']}")
                pool_of_problem[r["problem_id"]] = r["pool"]
                cluster_of_problem[r["problem_id"]] = r["problem_cluster"]
                pools_of_cluster[r["problem_cluster"]].add(r["pool"])
        for c, ps in pools_of_cluster.items():
            if len(ps) > 1:
                errs.append(f"split: cluster {c} is in several pools {sorted(ps)}")

    seen = set()
    for r in _jsonl(ds / "annotations" / "tier1a_codestream.jsonl"):
        rid = r.get("row_id", "?")
        for k in REQUIRED:
            if k not in r:
                errs.append(f"tier1a {rid}: missing field {k}")
        if rid in seen:
            errs.append(f"tier1a {rid}: duplicate row_id")
        seen.add(rid)
        if not str(rid).startswith("cs-"):
            errs.append(f"tier1a {rid}: row_id must start with cs-")
        if r.get("label") not in CLASSES:
            errs.append(f"tier1a {rid}: label {r.get('label')!r} not in tl-cpp-v2")
        if r.get("label") == "CPP_OTHER_ERROR":
            errs.append(f"tier1a {rid}: OTHER_ERROR must be human-confirmed, never automatic")
        if r.get("label_source") not in ("repair_verified", "weak_rule"):
            errs.append(f"tier1a {rid}: bad label_source {r.get('label_source')!r}")
        if (r.get("label_source") == "repair_verified") != bool(r.get("repair")):
            errs.append(f"tier1a {rid}: repair_verified must carry a repair proof (and only then)")
        if r.get("verified_by_execution") != (r.get("label_source") == "repair_verified"):
            errs.append(f"tier1a {rid}: verified_by_execution disagrees with label_source")
        conf = r.get("label_confidence")
        if conf is None or not (0 <= conf <= CAP):
            errs.append(f"tier1a {rid}: label_confidence {conf!r} outside [0, {CAP}]")
        if r.get("split_pool") not in POOLS:
            errs.append(f"tier1a {rid}: bad split_pool")
        pid = r.get("problem_id")
        if pid in pool_of_problem:
            if r.get("split_pool") != pool_of_problem[pid]:
                errs.append(f"tier1a {rid}: split_pool {r.get('split_pool')} != frozen {pool_of_problem[pid]}")
            if r.get("problem_cluster") != cluster_of_problem[pid]:
                errs.append(f"tier1a {rid}: problem_cluster disagrees with the frozen split")
        elif pool_of_problem:
            errs.append(f"tier1a {rid}: problem {pid} not in the split")
        if r.get("taxonomy_version") != "tl-cpp-v2":
            errs.append(f"tier1a {rid}: taxonomy_version must be tl-cpp-v2")
        if "source_code" in r or "code" in r:
            errs.append(f"tier1a {rid}: rows must not embed student source code")

    for name in ("multi_signal", "discovery_candidates", "repair_discovered", "other_error_candidates"):
        for r in _jsonl(ds / "annotations" / "review" / f"{name}.jsonl"):
            if r.get("label_source") is not None:
                errs.append(f"review/{name} {r.get('row_id')}: review rows must not carry a label_source")
            if "source_code" in r or "code" in r:
                errs.append(f"review/{name} {r.get('row_id')}: must not embed source code")

    try:
        tracked = subprocess.run(["git", "ls-files", "data/misconception_dataset/annotations"],
                                 cwd=root, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        tracked = []
    for t in tracked:
        if "/annotations/forms/" in t or "/annotations/forms_key/" in t:
            errs.append(f"git tracks {t}: blind forms and the hidden key must stay local")
    return errs


def main() -> int:
    errs = check()
    for e in errs:
        print("FAIL", e)
    print(f"{len(errs)} problem(s)" if errs else "Lane B artifacts OK")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
