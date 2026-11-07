"""Blind audit sheet for the served model's array-bounds calls on the held-out problems.

    python scripts/build_flag_audit.py            # writes cache/flag_audit/audit_01.txt + key.json
    python scripts/build_flag_audit.py --score    # after annotators C1 and C2 wrote review/flag_audit/{C1,C2}.json

The sheet holds every held-out row the model called ARRAY_BOUNDS plus every held-out row the
original labels call ARRAY_BOUNDS that the model did not (its misses), shuffled, with neutral
ids. Annotators see the same text as the earlier labelling rounds and never the model's call or
the earlier label. `--score` compares the two audit annotators with the model and the original label.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
CACHE = DS / "cache"
OUT = CACHE / "flag_audit"
REV = DS / "review" / "flag_audit"
TARGET = "CPP_ARRAY_BOUNDS"


def blocks_from(path: Path) -> dict[str, str]:
    out = {}
    for blk in re.split(r"(?m)^(?====== )", path.read_text(encoding="utf-8")):
        m = re.match(r"===== (\S+)", blk)
        if m:
            out[m.group(1)] = blk
    return out


def row_blocks() -> dict[str, str]:
    """row_id -> the formatted item text the labellers saw."""
    got: dict[str, str] = {}
    pg = {}
    for p in sorted((CACHE / "pg_pool").glob("shard_*.txt")):
        pg.update(blocks_from(p))
    for item, blk in pg.items():
        got[f"pgx-a{int(item[3:]):05d}"] = blk
    for name in ("test", "tr2", "train_queue", "final"):
        d = CACHE / "label_batches" / name
        if not (d / "manifest.json").exists():
            continue
        text = {}
        for p in sorted(d.glob("batch_*.txt")):
            text.update(blocks_from(p))
        for m in json.loads((d / "manifest.json").read_text(encoding="utf-8")):
            if m["item_id"] in text:
                got.setdefault(f"bl-{'t2-' if name == 'tr2' else ''}{m['item_id'].lower()}", text[m["item_id"]])
    return got


def older_progpedia_blocks(row_ids: list[str], raw_root: str = "/mnt/g/TraceLearn/Datasets_RAW") -> dict[str, str]:
    """Item text for the earlier PROGPedia execution-lane rows (not in the pool shards), in the same format."""
    import sys
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    import progpedia_oracle_tests as oracle
    from label_progpedia_exec import collect

    def clip(t: str, n: int) -> str:
        t = (t or "").replace("\r\n", "\n").strip("\n")
        return t if len(t) <= n else t[:n] + "\n...[cut]"

    labels = {}
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if r["row_id"] in row_ids:
            labels[r["row_id"]] = r
    out = {}
    for pid in sorted({r["problem_id"] for r in labels.values()}):
        tests = oracle.load_tests(pid) or []
        subs = {s["source_record_id"]: s for s in collect(Path(raw_root), [pid])}
        for rid, r in labels.items():
            if r["problem_id"] != pid or r["source_record_id"] not in subs:
                continue
            sub, t = subs[r["source_record_id"]], r.get("tests") or {}
            first = t.get("first_failed")
            got = next((x for x in t.get("results", []) if x.get("idx") == first), {})
            case = tests[first] if isinstance(first, int) and first < len(tests) else {}
            out[rid] = (f"===== {rid} | {pid[-8:]} | {sub['verdict']} | oracle tests {t.get('passed')}/{t.get('total')}\n"
                        f"--- first failing test input:\n{clip(case.get('input', ''), 220)}\n"
                        f"--- expected output:\n{clip(case.get('output', ''), 160)}\n"
                        f"--- observed output (status {got.get('status')}, rc {got.get('rc')}):\n{clip(got.get('stdout_head', ''), 160)}\n"
                        f"--- code ({sub['lang']}):\n{clip(sub['code'], 2600)}\n")
    return out


def build() -> None:
    pred = json.loads((DS / "reports" / "heldout_predictions.json").read_text(encoding="utf-8"))
    cols = pred["columns"]
    mi = cols.index("model: best")
    rows = [r for r in pred["rows"] if r[mi] == TARGET or r[2] == TARGET]
    text = row_blocks()
    text.update(older_progpedia_blocks([r[0] for r in rows if r[0] not in text]))
    rng = random.Random(20261109)
    rng.shuffle(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    key, blocks = {}, []
    for n, r in enumerate(rows, 1):
        if r[0] not in text:
            continue
        aid = f"AU-{n:03d}"
        key[aid] = {"row_id": r[0], "model": r[mi], "original_label": r[2]}
        blocks.append(re.sub(r"^===== \S+", f"===== {aid}", text[r[0]], count=1))
    (OUT / "audit_01.txt").write_text("\n".join(blocks), encoding="utf-8", newline="\n")
    (OUT / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8", newline="\n")
    print(f"{len(blocks)} items of {len(rows)} (missing text for {len(rows) - len(blocks)}) -> {OUT}")


def score() -> None:
    key = json.loads((OUT / "key.json").read_text(encoding="utf-8"))
    ann = {w: json.loads((REV / f"{w}.json").read_text(encoding="utf-8")) for w in ("C1", "C2")}
    called = [a for a, k in key.items() if k["model"] == TARGET]
    rep = {"items": len(key), "model_called_array_bounds": len(called)}

    def verdict(a):
        c1, c2 = ann["C1"].get(a, ["?"])[0], ann["C2"].get(a, ["?"])[0]
        return c1, c2

    both = [a for a in called if verdict(a)[0] == TARGET and verdict(a)[1] == TARGET]
    either = [a for a in called if TARGET in verdict(a)]
    orig = [a for a in called if key[a]["original_label"] == TARGET]
    rep["precision_original_label"] = f"{len(orig)}/{len(called)}"
    rep["precision_both_audit_annotators_agree"] = f"{len(both)}/{len(called)}"
    rep["precision_at_least_one_audit_annotator"] = f"{len(either)}/{len(called)}"
    rep["audit_annotators_agree_with_each_other"] = sum(verdict(a)[0] == verdict(a)[1] for a in key)
    rep["audit_vs_original_label_agree"] = sum(verdict(a)[0] == key[a]["original_label"] for a in key)
    rep["model_calls_audit_says_not_array_bounds"] = [(a, key[a]["original_label"], verdict(a)) for a in called
                                                       if TARGET not in verdict(a)]
    rep["audit_label_counts_on_model_calls"] = dict(Counter(verdict(a)[0] for a in called))
    (REV / "audit_result.json").write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    score() if a.score else build()
