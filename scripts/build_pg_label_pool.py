"""Blind labelling pool from real PROGPedia failing submissions (WRONG_ANSWER / RUNTIME_ERROR).

    wsl python3 scripts/build_pg_label_pool.py --raw-root /mnt/g/TraceLearn/Datasets_RAW

PROGPedia has ~6,000 real student failures; the earlier lanes labelled 285 of them. This
builds the pool for independent multi-annotator labelling:

- every WA/RE C/C++ submission of the problems that have oracle tests, de-duplicated by
  normalised code, minus rows a person already labelled;
- executed on the oracle tests (sandbox_runner, cached) so each item shows the first
  failing test, expected output and observed output, exactly as the CodeStream batches do;
- shards of SHARD items in a seeded random order, one `shard_NN.txt` per shard plus
  `statements.md` (the statements of the problems in the pool);
- a manifest with item id, source_record_id, problem, split group (train / heldout).

Nothing from a labeling function or the model is shown. The batches live in the
gitignored cache because they contain student code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import progpedia_oracle_tests as oracle  # noqa: E402
from label_progpedia_exec import collect  # noqa: E402

from sandbox_runner import RunConfig, run_many  # noqa: E402

DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "cache" / "pg_pool"
SHARD = 120
SEED = 20261108
# Whole problems that never reach training: the unbiased test for "unseen problem".
HELDOUT_PROBLEMS = ("tl-progpedia-00000021", "tl-progpedia-00000039", "tl-progpedia-00000053")
COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)


def norm_key(code: str) -> str:
    return hashlib.md5(re.sub(r"\s+", "", COMMENT.sub("", code)).encode()).hexdigest()


def clip(text: str, n: int) -> str:
    text = (text or "").replace("\r\n", "\n").strip("\n")
    return text if len(text) <= n else text[:n] + "\n...[cut]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()

    tests = {}
    for p in sorted((DS / "oracle_tests" / "progpedia").glob("*.json.gz")):
        pid = p.name[: -len(".json.gz")]
        t = oracle.load_tests(pid)
        if t:
            tests[pid] = t
    humans = set()
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("dataset_source") == "PROGPEDIA" and r.get("label_source") == "human":
            humans.add(r["source_record_id"])
    subs, seen = [], set()
    for s in collect(a.raw_root, sorted(tests)):
        k = norm_key(s["code"])
        if k in seen or s["source_record_id"] in humans:
            continue
        seen.add(k)
        subs.append(s)
    print(f"{len(subs)} unlabelled de-duplicated submissions over {len(tests)} problems", flush=True)

    cfg = RunConfig(sanitizer_max_input_bytes=20_000, valgrind_max_input_bytes=20_000, slow_pass_skip_timeouts=True)
    jobs = [(s["code"], s["lang"], tests[s["problem_id"]]) for s in subs]
    (DS / "cache" / "progpedia_exec").mkdir(parents=True, exist_ok=True)
    results = list(run_many(jobs, cfg, workers=a.workers, cache_dir=str(DS / "cache" / "progpedia_exec" / "runs")))

    items = []
    for s, res in zip(subs, results):
        if res.get("branch") != "failing":
            continue                       # all_pass / compile error / timeout-only: not a clean failing case
        items.append((s, res))
    random.Random(SEED).shuffle(items)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, blocks = [], []
    for n, (s, res) in enumerate(items, 1):
        t = res.get("tests") or {}
        first = t.get("first_failed")
        got = next((x for x in t.get("results", []) if x.get("idx") == first), {})
        case = tests[s["problem_id"]][first] if isinstance(first, int) and first < len(tests[s["problem_id"]]) else {}
        item = f"PG-{n:04d}"
        manifest.append({"item_id": item, "problem_id": s["problem_id"], "source_record_id": s["source_record_id"],
                         "sha": s["sha"], "verdict": s["verdict"], "lang": s["lang"],
                         "group": "heldout" if s["problem_id"] in HELDOUT_PROBLEMS else "train",
                         "tests_passed": t.get("passed"), "tests_total": t.get("total"), "raw_copy": s["raw_copy"]})
        blocks.append(
            f"===== {item} | {s['problem_id'][-8:]} | {s['verdict']} | oracle tests {t.get('passed')}/{t.get('total')}\n"
            f"--- first failing test input:\n{clip(case.get('input', ''), 220)}\n"
            f"--- expected output:\n{clip(case.get('output', ''), 160)}\n"
            f"--- observed output (status {got.get('status')}, rc {got.get('rc')}):\n{clip(got.get('stdout_head', ''), 160)}\n"
            f"--- code ({s['lang']}):\n{clip(s['code'], 2600)}\n")
    for i in range(0, len(blocks), SHARD):
        (OUT / f"shard_{i // SHARD + 1:02d}.txt").write_text("\n".join(blocks[i:i + SHARD]), encoding="utf-8", newline="\n")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8", newline="\n")
    stmts = []
    for pid in sorted({m["problem_id"] for m in manifest}):
        text = ""
        for d in oracle.problem_dirs(a.raw_root, pid):
            if (d / "statement.md").exists():
                text = (d / "statement.md").read_text(encoding="utf-8", errors="replace")
                break
        stmts.append(f"## {pid[-8:]}\n{clip(text, 1500)}\n")
    (OUT / "statements.md").write_text("\n".join(stmts), encoding="utf-8", newline="\n")
    with (OUT / "exec.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for (s, res), m in zip(items, manifest):
            fh.write(json.dumps({"item_id": m["item_id"], "result": res}) + "\n")
    print(f"{len(manifest)} failing items in {-(-len(blocks) // SHARD)} shards -> {OUT}; "
          f"heldout {sum(1 for m in manifest if m['group'] == 'heldout')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
