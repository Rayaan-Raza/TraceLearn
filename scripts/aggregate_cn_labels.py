"""Consensus of the CodeNet annotators (A, B, adjudicator C) -> review/agent_labels_cn/consensus.json.

    python scripts/aggregate_cn_labels.py

Items the reconcile step marked `drop` (correct under the reference oracle) are left out. For
`keep` items A and B labelled the shard; for `relabel` items they labelled `relabel.txt` (full code,
corrected case). C labelled every A/B disagreement and every relabel item, blind. A label stands
when two of the three agree; otherwise the item is UNCERTAIN and not used.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
LAB = DS / "review" / "agent_labels_cn"


def load(who: str, pattern: str) -> dict:
    out = {}
    for f in sorted((LAB / who).glob(pattern)):
        out.update(json.loads(f.read_text(encoding="utf-8")))
    return out


def main() -> int:
    dec = json.loads((DS / "cache" / "cn_pool" / "reconcile.json").read_text(encoding="utf-8"))
    a, b = load("A", "shard_*.json"), load("B", "shard_*.json")
    a.update(load("A", "relabel.json"))
    b.update(load("B", "relabel.json"))
    c = load("C", "adj_*.json")
    consensus, how = {}, Counter()
    for item, d in sorted(dec.items()):
        if d == "drop":
            continue
        la, lb = a[item][0], b[item][0]
        lc = c.get(item, [None])[0]
        if la == lb and la != "UNCERTAIN":
            label, rule = la, "A=B"
        elif lc and lc != "UNCERTAIN" and lc in (la, lb):
            label, rule = lc, "2of3"
        else:
            label, rule = "UNCERTAIN", "no_majority"
        how[rule] += 1
        consensus[item] = {"label": label, "rule": rule, "A": a[item], "B": b[item], "C": c.get(item), "reconcile": d}
    keep = [i for i, x in dec.items() if x == "keep"]
    agree = sum(a[i][0] == b[i][0] for i in keep)
    ca, cb = Counter(a[i][0] for i in keep), Counter(b[i][0] for i in keep)
    pe = sum(ca[k] * cb[k] for k in ca) / len(keep) ** 2
    po = agree / len(keep)
    stats = {"items": len(dec), "dropped_correct": sum(x == "drop" for x in dec.values()), "rules": dict(how),
             "agreement_AB_keep": round(po, 3), "kappa_AB_keep": round((po - pe) / (1 - pe), 3),
             "labels": dict(Counter(v["label"] for v in consensus.values()).most_common())}
    (LAB / "consensus.json").write_text(json.dumps(consensus, indent=1), encoding="utf-8", newline="\n")
    (LAB / "agreement.json").write_text(json.dumps(stats, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(stats, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
