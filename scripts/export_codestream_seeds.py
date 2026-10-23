"""Export execution-verified CodeStream seeds for Lane A (Eman) — read-only hand-off.

A seed is a C/C++ submission that passes **every** test in our sandbox,
whatever its source verdict says. Only **train-side** clusters are exported
(§13.4: no mutant may be seeded from dev-gold or test clusters). Eman reads
this file; Lane B never writes mutants (§5 anti-collision matrix).

    python scripts/export_codestream_seeds.py

Output: data/misconception_dataset/annotations/codestream_seeds_train.csv
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codestream_common import DATASET_DIR, code_sha, find_raw, load_submissions  # noqa: E402

EXEC_PATH = DATASET_DIR / "cache" / "codestream_exec.jsonl"
OUT = DATASET_DIR / "annotations" / "codestream_seeds_train.csv"


def main() -> int:
    raw = find_raw(sys.argv[1] if len(sys.argv) > 1 else None)
    subs = {s.submission_id: s for s in load_submissions(raw)}
    with open(DATASET_DIR / "splits" / "codestream_clusters.csv", encoding="utf-8") as f:
        pools = {r["problem_id"]: (r["problem_cluster"], r["pool"]) for r in csv.DictReader(f)}
    rows, seen = [], set()
    per = Counter()
    for line in EXEC_PATH.open(encoding="utf-8"):
        r = json.loads(line)
        res = r["result"]
        s = subs.get(r["submission_id"])
        if not s or res.get("branch") != "all_pass":
            continue
        cluster, pool = pools[s.problem_id]
        if pool != "train":
            continue
        san = ((res.get("runtime") or {}).get("sanitizer") or {}).get("reports") or []
        h = code_sha(s.code)
        if h in seen:
            continue
        seen.add(h)
        per[s.problem_id] += 1
        rows.append({"submission_id": s.submission_id, "problem_id": s.problem_id,
                     "problem_cluster": cluster, "language": s.lang, "source_verdict": s.verdict,
                     "tests_passed": res["tests"]["passed"], "sanitizer_clean": not san,
                     "code_sha256": h})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["submission_id"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    clean = sum(r["sanitizer_clean"] for r in rows)
    print(f"{len(rows)} train-side seeds ({clean} sanitizer-clean) across {len(per)} problems -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
