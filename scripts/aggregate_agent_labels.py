"""Combine independent annotator labels: agreement, adjudication queue, consensus.

    python scripts/aggregate_agent_labels.py agreement     # A vs B, writes adjudication shards
    python scripts/aggregate_agent_labels.py consensus     # after the adjudicators (C) finished

Annotators A and B label every item alone. Where they disagree (or either says UNCERTAIN) the
item goes to adjudicator C, who sees it with no knowledge of A or B. The consensus is the
label two of the three annotators gave; an item with three different answers stays
UNCERTAIN and is not used. Everything is written under review/agent_labels/ and the
cache (adjudication shards contain student code, so they are gitignored).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
LAB = DS / "review" / "agent_labels"
POOL = DS / "cache" / "pg_pool"
CLASSES = ["CPP_ARRAY_BOUNDS", "CPP_ASSIGN_VS_COMPARE", "CPP_INT_OVERFLOW", "CPP_LOOP_BOUNDARY",
           "CPP_MISSING_BASE_CASE", "CPP_OFF_BY_ONE", "CPP_OTHER_ERROR", "CPP_RANGE_CHECK",
           "CPP_STALE_EXIT", "CPP_UNINITIALIZED_VAR", "CPP_WRONG_LOOP_DIR", "UNCERTAIN"]


def load(who: str) -> dict[str, tuple[str, int, str]]:
    out: dict[str, tuple[str, int, str]] = {}
    for p in sorted((LAB / who).glob("shard_*.json")):
        for item, v in json.loads(p.read_text(encoding="utf-8")).items():
            label = v[0] if v[0] in CLASSES else "UNCERTAIN"
            out[item] = (label, int(v[1]) if len(v) > 1 and str(v[1]).isdigit() else 1, str(v[2]) if len(v) > 2 else "")
    return out


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def agreement() -> None:
    A, B = load("A"), load("B")
    items = sorted(set(A) & set(B))
    manifest = {m["item_id"]: m for m in json.loads((POOL / "manifest.json").read_text(encoding="utf-8"))}
    la, lb = [A[i][0] for i in items], [B[i][0] for i in items]
    agree = [i for i in items if A[i][0] == B[i][0] and A[i][0] != "UNCERTAIN"]
    mis = [i for i in items if A[i][0] != "CPP_OTHER_ERROR" or B[i][0] != "CPP_OTHER_ERROR"]
    mis_agree = [i for i in mis if A[i][0] == B[i][0]]
    rep = {"items": len(items), "missing_A": len(set(manifest) - set(A)), "missing_B": len(set(manifest) - set(B)),
           "raw_agreement": round(len(agree) / len(items), 3), "cohen_kappa": round(kappa(la, lb), 3),
           "either_flags_a_misconception": len(mis), "agree_on_those": len(mis_agree),
           "A_counts": dict(Counter(la)), "B_counts": dict(Counter(lb)),
           "confusions": dict(Counter(f"{A[i][0]} | {B[i][0]}" for i in items if A[i][0] != B[i][0]).most_common(25))}
    (LAB / "agreement_AB.json").write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rep, indent=1))
    # adjudication shards: the disagreeing items, text copied from the original shards
    blocks: dict[str, str] = {}
    for p in sorted(POOL.glob("shard_*.txt")):
        for blk in re.split(r"(?m)^(?====== PG-)", p.read_text(encoding="utf-8")):
            m = re.match(r"===== (PG-\d+)", blk)
            if m:
                blocks[m.group(1)] = blk
    todo = [i for i in items if i not in agree]
    for n in range(0, len(todo), 100):
        (POOL / f"adj_{n // 100 + 1:02d}.txt").write_text("\n".join(blocks[i] for i in todo[n:n + 100]), encoding="utf-8", newline="\n")
    print(f"{len(todo)} items to adjudicate in {-(-len(todo) // 100)} shards")


def consensus() -> None:
    A, B, C = load("A"), load("B"), load("C") if (LAB / "C").exists() else {}
    manifest = json.loads((POOL / "manifest.json").read_text(encoding="utf-8"))
    out, stats = {}, Counter()
    for m in manifest:
        i = m["item_id"]
        if i not in A or i not in B:
            stats["unlabelled"] += 1
            continue
        a, b = A[i][0], B[i][0]
        if a == b and a != "UNCERTAIN":
            label, how = a, "A=B"
        else:
            c = C.get(i, ("UNCERTAIN", 1, ""))[0]
            votes = Counter(x for x in (a, b, c) if x != "UNCERTAIN")
            top = votes.most_common(2)
            if top and top[0][1] >= 2:
                label, how = top[0][0], "2-of-3"
            else:
                label, how = "UNCERTAIN", "no-majority"
        stats[how] += 1
        out[i] = {"label": label, "how": how, "A": A[i][0], "B": B[i][0], "C": C.get(i, ("", 0, ""))[0],
                  "note": (A[i][2] or B[i][2])[:160]}
    (LAB / "consensus.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(dict(stats), dict(Counter(v["label"] for v in out.values())))


if __name__ == "__main__":
    {"agreement": agreement, "consensus": consensus}[sys.argv[1]]()
