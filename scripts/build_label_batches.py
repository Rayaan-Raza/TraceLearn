"""Blind reading batches for labelling real failing CodeStream submissions.

    wsl python3 scripts/build_label_batches.py --pool test  --per-problem 12 --raw /mnt/g/...
    wsl python3 scripts/build_label_batches.py --pool train --from-queue          --raw /mnt/g/...

Writes text batches to the gitignored cache (they contain student code). Each item
shows the problem statement, the first failing test (input, expected, observed) and
the code, and NOTHING produced by a rule or the model. The reader labels each item
following docs in `ANNOTATION_GUIDELINE.md` and records the answer in
`review/blind_labels/<name>.json` ({item_id: {"label", "note"}}); `submission_id`
for every item is in the manifest written next to the batches.

Sampling is random within each problem (seeded) over ALL failing submissions of the
pool, not only unlabeled-by-rules ones, so class prevalence is not distorted by the
labeling functions. Rows that already have a label in `labels.jsonl` are skipped.
Executing the submissions here does not run the model: labels must be frozen before
any model prediction on these items is looked at.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DS = ROOT / "data" / "misconception_dataset"
CACHE = DS / "cache"
SEED = 20261107
BATCH = 12


def clip(text: str, limit: int) -> str:
    text = (text or "").replace("\r\n", "\n").strip("\n")
    return text if len(text) <= limit else text[:limit] + "\n...[cut]"


def sample_failing(index_rows: list[dict[str, str]], pool: str, per_problem: int, already: set[str],
                   seed: int = SEED, problems: Sequence[str] = ()) -> list[dict[str, str]]:
    """Seeded per-problem random sample of failing rows of one pool, skipping already-labelled rows."""
    by_problem: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in sorted(index_rows, key=lambda r: r["submission_id"]):
        if (r["problem_id"] in problems if problems else r["split_pool"] == pool) and r["row_id"] not in already:
            by_problem[r["problem_id"]].append(r)
    rng = random.Random(seed)
    chosen: list[dict[str, str]] = []
    for problem in sorted(by_problem):
        rows = by_problem[problem][:]
        rng.shuffle(rows)
        chosen.extend(rows[:per_problem])
    rng.shuffle(chosen)
    return chosen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool", choices=("test", "train", "dev_gold"), required=True)
    ap.add_argument("--per-problem", type=int, default=12)
    ap.add_argument("--from-queue", action="store_true", help="use the 76-item OTHER_ERROR review queue")
    ap.add_argument("--raw", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--name", default=None)
    ap.add_argument("--batch", type=int, default=BATCH, help="items per batch file")
    ap.add_argument("--problems", default="", help="comma-separated problem ids: sample these problems instead of a pool")
    ap.add_argument("--seen", default="", help="comma-separated problem ids whose statement the reader already has")
    args = ap.parse_args(argv)

    from codestream_common import find_raw, load_problems, load_submissions
    from eval_real_data import execute_pool

    index = list(csv.DictReader((DS / "annotations" / "codestream_failing_index.csv").open(encoding="utf-8", newline="")))
    labelled = {json.loads(line)["row_id"] for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8") if line.strip()}
    raw = find_raw(args.raw)
    probs = load_problems(raw)
    subs = {s.submission_id: s for s in load_submissions(raw)}

    if args.from_queue:
        picked_ids = [r["submission_id"] for r in csv.DictReader(
            (CACHE / "review_queue_other_codestream.csv").open(encoding="utf-8", newline=""))]
        by_id = {r["submission_id"]: r for r in index}
        picked = [by_id[i] for i in picked_ids if i in by_id]
    else:
        picked = sample_failing(index, args.pool, args.per_problem, labelled,
                                problems=[x for x in args.problems.split(",") if x])

    name = args.name or f"{args.pool}{'_queue' if args.from_queue else ''}"
    exec_path = CACHE / f"label_exec_{name}.jsonl"
    chosen_subs = [subs[r["submission_id"]] for r in picked if r["submission_id"] in subs]
    results = execute_pool(chosen_subs, probs, exec_path, args.workers)

    out_dir = CACHE / "label_batches" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest, blocks = [], []
    shown = set(x for x in args.seen.split(",") if x)
    for n, s in enumerate(chosen_subs, 1):
        res = results.get(s.submission_id)
        if res is None or res.get("branch") != "failing":
            continue
        tests = res.get("tests") or {}
        first = tests.get("first_failed")
        got = next((x for x in tests.get("results", []) if x.get("idx") == first), {})
        case = probs[s.problem_id].tests[first] if isinstance(first, int) and first < len(probs[s.problem_id].tests) else {}
        item = f"{name[:2].upper()}-{len(manifest) + 1:03d}"
        manifest.append({"item_id": item, "submission_id": s.submission_id, "problem_id": s.problem_id,
                         "row_id": next(r["row_id"] for r in picked if r["submission_id"] == s.submission_id)})
        blocks.append(
            f"===== {item} | {s.problem_id} | tests {tests.get('passed')}/{tests.get('total')} | {s.verdict}\n"
            + ("" if s.problem_id in shown else f"--- statement:\n{clip(probs[s.problem_id].statement, 420)}\n")
            + f"--- first failing test: input:\n{clip(case.get('input', ''), 110)}\n"
            f"--- expected:\n{clip(case.get('output', ''), 110)}\n"
            f"--- observed (status {got.get('status')}, rc {got.get('rc')}):\n{clip(got.get('stdout_head', ''), 110)}\n"
            f"--- code:\n{clip(s.code, 1900)}\n")
    size = args.batch
    for i in range(0, len(blocks), size):
        (out_dir / f"batch_{i // size + 1:02d}.txt").write_text("\n".join(blocks[i:i + size]), encoding="utf-8", newline="\n")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8", newline="\n")
    print(f"{len(manifest)} items in {-(-len(blocks) // size)} batches -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
