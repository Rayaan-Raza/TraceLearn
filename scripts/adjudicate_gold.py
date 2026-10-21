"""Adjudicate filled gold / dev-gold forms (H1 → G6).

    python scripts/adjudicate_gold.py

Reads annotations/forms/*/answers.csv and the hidden key, then reports

* Fleiss κ over the 4 raters on the overlap items (gate: ≥ 0.6 overall);
* per-class Fleiss κ for the hard-3 only (items whose stratum is that class);
* pairwise Cohen κ (descriptive);
* intra-rater agreement on blind duplicates (gate: ≥ 8/10);
* human–LF agreement per class (a finding about the LFs, not about gold).

Labels: majority vote; a split with no majority (or a majority of
UNCERTAIN) → discussion list → UNCERTAIN, dropped from test, counted.
Writes annotations/gold.jsonl, annotations/dev_gold.jsonl,
annotations/review/adjudication_needed.csv and reports/gold_agreement_report.md.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codestream_common import DATASET_DIR, write_jsonl  # noqa: E402

ANN = DATASET_DIR / "annotations"
FORMS = ANN / "forms"
KEY = ANN / "forms_key" / "gold_key.csv"
HARD3 = ["CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK", "CPP_STALE_EXIT"]
UNCERTAIN = "UNCERTAIN"


def fleiss_kappa(table: list[list[str]]) -> float | None:
    """``table`` = per item, the list of labels from its raters (equal counts)."""
    table = [t for t in table if len(t) >= 2]
    if not table:
        return None
    n = len(table[0])
    table = [t for t in table if len(t) == n]
    cats = sorted({c for t in table for c in t})
    N = len(table)
    if N == 0 or len(cats) < 2:
        return 1.0 if N else None
    p_j = {c: sum(t.count(c) for t in table) / (N * n) for c in cats}
    P_i = [(sum(t.count(c) ** 2 for c in cats) - n) / (n * (n - 1)) for t in table]
    P_bar = sum(P_i) / N
    P_e = sum(v * v for v in p_j.values())
    if P_e == 1:
        return 1.0
    return round((P_bar - P_e) / (1 - P_e), 4)


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    if not a:
        return None
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] * cb[c] for c in set(a) | set(b)) / (n * n)
    return round((po - pe) / (1 - pe), 4) if pe != 1 else 1.0


def majority(labels: list[str]) -> str:
    c = Counter(labels).most_common()
    if not c:
        return UNCERTAIN
    top, k = c[0]
    if len(c) > 1 and c[1][1] == k:
        return UNCERTAIN  # tie → discussion
    if k * 2 <= len(labels) and len(labels) > 2:
        return UNCERTAIN  # no absolute majority among 3–4 raters
    return top


def read_answers() -> dict[tuple[str, str], dict]:
    out = {}
    for folder in FORMS.iterdir() if FORMS.exists() else []:
        p = folder / "answers.csv"
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("primary_label", "").strip():
                    sec = [k[5:] for k, v in r.items() if k.startswith("also_") and v.strip()]
                    out[(folder.name, r["item_id"])] = {"primary": r["primary_label"].strip(),
                                                        "secondary": sec, "notes": r.get("notes", "")}
    return out


def main() -> int:
    with open(KEY, encoding="utf-8") as f:
        key = list(csv.DictReader(f))
    ans = read_answers()
    folder_of = {"gold": lambda r: r["rater"], "dev_gold": lambda r: f"dev_gold_{r['rater']}",
                 "calibration": lambda r: "calibration"}
    by_row = defaultdict(list)  # (form,row_id) -> [(rater, label, key)]
    dup = defaultdict(list)  # (rater,row_id) -> labels
    for k in key:
        a = ans.get((folder_of[k["form"]](k), k["item_id"]))
        if not a:
            continue
        if k["duplicate"] == "True":
            dup[(k["rater"], k["row_id"])].append(a["primary"])
            continue
        by_row[(k["form"], k["row_id"])].append((k["rater"], a, k))
        if k["form"] == "gold":
            dup[(k["rater"], k["row_id"])].insert(0, a["primary"])

    gold, dev, needs = [], [], []
    overlap_tables, per_class_tables = [], defaultdict(list)
    pair_labels = defaultdict(lambda: ([], []))
    lf_agree = defaultdict(Counter)
    for (form, row_id), lst in sorted(by_row.items()):
        if form == "calibration":
            continue
        labels = [a["primary"] for _, a, _ in lst]
        k0 = lst[0][2]
        if k0["overlap"] == "True" and len(lst) >= 2:
            overlap_tables.append(labels)
            if k0["stratum"] in HARD3:
                per_class_tables[k0["stratum"]].append(labels)
            raters = {r: a["primary"] for r, a, _ in lst}
            for x, y in combinations(sorted(raters), 2):
                pair_labels[(x, y)][0].append(raters[x])
                pair_labels[(x, y)][1].append(raters[y])
        final = majority(labels)
        sec = sorted({s for _, a, _ in lst for s in a["secondary"]} - {final})
        rec = {"row_id": row_id, "submission_id": k0["submission_id"],
               "problem_cluster": k0["problem_cluster"], "label": final, "label_source": "human",
               "secondary_labels": sec, "raters": {r: a["primary"] for r, a, _ in lst},
               "stratum": k0["stratum"], "firing_count": int(k0["firing_count"]),
               "lf_label": k0["lf_label"] or None, "split": form}
        if final == UNCERTAIN:
            needs.append(rec)
        (gold if form == "gold" else dev).append(rec)
        if form == "gold" and final != UNCERTAIN:
            lf_agree[final]["n"] += 1
            lf_agree[final]["lf_same"] += int(k0["lf_label"] == final)

    write_jsonl(ANN / "gold.jsonl", [g for g in gold if g["label"] != UNCERTAIN])
    write_jsonl(ANN / "dev_gold.jsonl", [d for d in dev if d["label"] != UNCERTAIN])
    (ANN / "review").mkdir(parents=True, exist_ok=True)
    with open(ANN / "review" / "adjudication_needed.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["row_id", "split", "raters", "resolved_label", "notes"])
        for r in needs:
            w.writerow([r["row_id"], r["split"], json.dumps(r["raters"]), "", ""])

    fk = fleiss_kappa(overlap_tables)
    intra = {}
    for (rater, row), labs in dup.items():
        if len(labs) >= 2:
            intra.setdefault(rater, Counter())["n"] += 1
            intra[rater]["same"] += int(labs[0] == labs[1])
    L = ["# Gold agreement report (H1 / G6)", "",
         "Generated by `scripts/adjudicate_gold.py`. Do not edit by hand.", "",
         f"- Gold rows answered: {len(gold)} · labeled: {sum(g['label'] != UNCERTAIN for g in gold)} · "
         f"UNCERTAIN (dropped, counted): {sum(g['label'] == UNCERTAIN for g in gold)}",
         f"- Dev-gold rows answered: {len(dev)}",
         f"- Fleiss κ (overlap, {len(overlap_tables)} items): **{fk}** — gate ≥ 0.6: "
         f"{'PASS' if fk is not None and fk >= 0.6 else 'FAIL / not yet measurable'}", "",
         "| Hard-3 class | Overlap items | Fleiss κ | <0.4 → merge candidate |", "|---|---:|---:|---|"]
    for c in HARD3:
        k = fleiss_kappa(per_class_tables[c])
        L.append(f"| {c} | {len(per_class_tables[c])} | {k} | {'yes' if k is not None and k < 0.4 else ''} |")
    L += ["", "| Rater pair | Items | Cohen κ (descriptive) |", "|---|---:|---:|"]
    for (x, y), (a, b) in sorted(pair_labels.items()):
        L.append(f"| {x} – {y} | {len(a)} | {cohen_kappa(a, b)} |")
    L += ["", "| Rater | Duplicate pairs | Same label | Gate ≥ 8/10 |", "|---|---:|---:|---|"]
    for r, c in sorted(intra.items()):
        ok = c["n"] and c["same"] / c["n"] >= 0.8
        L.append(f"| {r} | {c['n']} | {c['same']} | {'PASS' if ok else 'FAIL'} |")
    L += ["", "## Human–LF agreement (finding about the LFs)", "", "| Human label | Items | LF said the same |",
          "|---|---:|---:|"]
    for c, v in sorted(lf_agree.items()):
        L.append(f"| {c} | {v['n']} | {v['lf_same']} |")
    rep = DATASET_DIR / "reports" / "gold_agreement_report.md"
    rep.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
