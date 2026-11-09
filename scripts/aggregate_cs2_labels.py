"""Second and third opinions on the 322 real CodeStream training-pool failures (`tr2`).

    python scripts/aggregate_cs2_labels.py

The `tr2` items were first labelled by one blind reader (`review/blind_labels/tr2.json`, 184
items; the other 138 inherit a label from identical code). Annotators A and B (agents, working
alone) then labelled every item again from the same batch files (`review/agent_labels_cs2/`).
Consensus per item = the label at least two of the available opinions agree on (A, B and, where
there is one, the original reader); otherwise UNCERTAIN, and the item is dropped by the ingest.
Writes `review/agent_labels_cs2/consensus.json` and `agreement.json`.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
LAB = DS / "review" / "agent_labels_cs2"
CLASSES = {"CPP_ARRAY_BOUNDS", "CPP_ASSIGN_VS_COMPARE", "CPP_INT_OVERFLOW", "CPP_LOOP_BOUNDARY", "CPP_MISSING_BASE_CASE",
           "CPP_OFF_BY_ONE", "CPP_OTHER_ERROR", "CPP_RANGE_CHECK", "CPP_STALE_EXIT", "CPP_UNINITIALIZED_VAR", "CPP_WRONG_LOOP_DIR"}


def load(who: str) -> dict[str, tuple[str, str]]:
    out = {}
    for p in sorted((LAB / who).glob("batch_*.json")):
        for item, v in json.loads(p.read_text(encoding="utf-8")).items():
            out[item] = (v[0] if v[0] in CLASSES else "UNCERTAIN", str(v[2]) if len(v) > 2 else "")
    return out


def main() -> None:
    A, B = load("A"), load("B")
    reader = {k: (v["label"], v["note"]) for k, v in
              json.loads((DS / "review" / "blind_labels" / "tr2.json").read_text(encoding="utf-8")).items()}
    items = sorted(set(A) | set(B) | set(reader))
    out, how = {}, Counter()
    for i in items:
        votes = [x[i][0] for x in (A, B, reader) if i in x and x[i][0] != "UNCERTAIN"]
        top = Counter(votes).most_common(1)
        if top and top[0][1] >= 2:
            label, h = top[0][0], f"{top[0][1]}-of-{len([x for x in (A, B, reader) if i in x])}"
        else:
            label, h = "UNCERTAIN", "no-majority"
        how[h] += 1
        out[i] = {"label": label, "how": h, "A": A.get(i, ("",))[0], "B": B.get(i, ("",))[0],
                  "reader": reader.get(i, ("",))[0], "note": (A.get(i) or B.get(i) or reader.get(i) or ("", ""))[1][:160]}
    ab = [i for i in items if i in A and i in B]
    agree = sum(A[i][0] == B[i][0] for i in ab)
    vs_reader = [i for i in items if i in A and i in reader]
    rep = {"items": len(items), "A_vs_B_agree": agree, "A_vs_B_n": len(ab),
           "A_vs_reader_agree": sum(A[i][0] == reader[i][0] for i in vs_reader), "A_vs_reader_n": len(vs_reader),
           "consensus": dict(how), "labels": dict(Counter(v["label"] for v in out.values())),
           "changed_vs_reader": sum(1 for i in reader if i in out and out[i]["label"] not in ("UNCERTAIN", reader[i][0]))}
    (LAB / "consensus.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    (LAB / "agreement.json").write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
