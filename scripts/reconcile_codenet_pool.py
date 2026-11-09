"""Re-judge the labelled CodeNet pool against the reference-solution oracle.

    wsl python3 scripts/reconcile_codenet_pool.py --raw-root /mnt/g/TraceLearn/Datasets_RAW

The first pool (build_codenet_pool.py before REFERENCES) took expected outputs from the
submissions' majority, which is wrong on p02742's one-row boards. This re-runs every item
(cached), rewrites `oracle_tests/codenet/` from the references and sorts the items:

- `drop`: the program passes every reference test (it was correct);
- `keep`: same first failing input and output as the annotators saw, labels stand;
- `relabel`: the first failing case changed, or the code was cut in the shard; a new shard
  `relabel.txt` shows the corrected case and the full code.

Writes `reconcile.json` ({item_id: decision}) and updates manifest/items with the new case.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import build_codenet_pool as B  # noqa: E402
from sandbox_runner import RunConfig, run_many  # noqa: E402

CUT = 2600


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    items = [json.loads(line) for line in (B.OUT / "items.jsonl").open(encoding="utf-8")]
    cfg = RunConfig(warnings_pass=False, sanitizer_pass=False, valgrind_pass=False, double_run=False,
                    stop_after_timeouts=2, keep_stdout_bytes=600)
    cache = str(B.DS / "cache" / "codenet_exec" / "runs")
    decisions, blocks = {}, []
    for pid in sorted({s["problem_id"] for s in items}):
        samp = B.samples(a.raw_root, pid)
        gr = random.Random(f"{B.SEED}-{pid}")
        inputs = [s["input"] for s in samp] + [B.GENERATORS[pid](gr, i) for i in range(B.N_GENERATED)]
        expected = [B.canon(B.REFERENCES[pid](x)) for x in inputs]
        assert all(expected[k] == B.canon(s["output"]) for k, s in enumerate(samp)), pid
        tests = [{"input": x, "output": e} for x, e in zip(inputs, expected)]
        old = json.load(gzip.open(B.TESTS / f"{pid}.json.gz", "rt", encoding="utf-8"))
        for s in items:
            if s["problem_id"] == pid and "first_input" not in s:
                s["first_input"] = old[s["first_failed"]]["input"]
        with gzip.open(B.TESTS / f"{pid}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(tests, fh)
        mine = [s for s in items if s["problem_id"] == pid]
        probe = [{"input": x, "output": ""} for x in inputs]
        runs = list(run_many([(s["code"], "cpp", probe) for s in mine], cfg, workers=a.workers, cache_dir=cache))
        for s, r in zip(mine, runs):
            res = {x.get("idx"): x for x in (r.get("tests") or {}).get("results", [])}
            outs = [B.canon(res[i].get("stdout_head", "")) if i in res and res[i].get("status") not in
                    ("timeout", "crash", "output_limit", "skipped", None) else None for i in range(len(inputs))]
            fails = [i for i in range(len(inputs)) if outs[i] != expected[i]]
            statuses = {(res.get(i) or {}).get("status") for i in fails}
            old_input = s.get("first_input")
            if not fails or statuses <= {"timeout", None}:
                decisions[s["item_id"]] = "drop"
                continue
            first = fails[0]
            got = res.get(first) or {}
            same_case = inputs[first].strip() == (old_input or "").strip() if old_input else None
            s.update(first_failed=first, first_input=inputs[first], tests_total=len(tests),
                     tests_passed=len(tests) - len(fails), observed=got.get("stdout_head", ""),
                     observed_status=got.get("status"), rc=got.get("rc"))
            changed = same_case is False
            cut = len(s["code"].replace("\r\n", "\n").strip("\n")) > CUT
            if changed or cut:
                decisions[s["item_id"]] = "relabel"
                blocks.append(
                    f"===== {s['item_id']} | {pid} | derived tests {s['tests_passed']}/{s['tests_total']}\n"
                    f"--- first failing test input:\n{B.clip(inputs[first], 220)}\n"
                    f"--- expected output:\n{B.clip(expected[first], 160)}\n"
                    f"--- observed output (status {s['observed_status']}, rc {s['rc']}):\n{B.clip(s['observed'], 160)}\n"
                    f"--- code (cpp):\n{s['code'].strip()}\n")
            else:
                decisions[s["item_id"]] = "keep"
    (B.OUT / "reconcile.json").write_text(json.dumps(decisions, indent=1), encoding="utf-8")
    (B.OUT / "relabel.txt").write_text("\n".join(blocks), encoding="utf-8", newline="\n")
    with (B.OUT / "items.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for s in items:
            fh.write(json.dumps(s) + "\n")
    from collections import Counter
    print(Counter(decisions.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
