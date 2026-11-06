"""Does ruling out impossible classes help on real code, and does it cost anything? (docs/6-nov.md §9)

    python scripts/eval_applicability.py

Four checks of `backend/app/diagnosis/applicability.py`:

1. Safety: how often a rule would rule out a row's OWN label, split by certain
   (execution-verified mutants, repair-verified rows) and weak labels.
2. Cost: out-of-fold macro-F1 of the served `best` variant with and without the
   rules, overall and on non-synthetic rows.
3. Behaviour on unseen real failures (the gitignored dump from
   `eval_real_data.py --features-only`): how often the top class is ruled out,
   and how the abstain rate and class histogram move.
4. Open-set reference: the 34 held-out PROGPedia rows that have a MODEL-ASSISTED
   pre-review label (unsigned, not gold). For rows the reviewer called
   OTHER_ERROR, how often does the model raise a false alarm?

Writes reports/applicability.json / .md. Item 4 is tiny and uses unsigned labels:
read it as a direction, not a measurement.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import eval_baselines as eb  # noqa: E402
import train_xgb_misconception as trainer  # noqa: E402

from backend.app.diagnosis.applicability import move_ruled_out_mass, ruled_out  # noqa: E402
from backend.app.diagnosis.xgb_classifier import ModelClassifier  # noqa: E402

DS = eb.DATASET_DIR
CERTAIN_SOURCES = {"synthetic", "repair_verified", "human"}


def _num(value: str) -> float | None:
    try:
        return None if value in ("", "nan", "NaN") else float(value)
    except ValueError:
        return None


def safety() -> dict[str, Any]:
    labels = {}
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            labels[row["row_id"]] = row
    total: Counter = Counter()
    bad: Counter = Counter()
    examples: list[str] = []
    for r in csv.DictReader((DS / "features" / "features.csv").open(encoding="utf-8", newline="")):
        feats = {k: _num(v) for k, v in r.items() if "." in k}
        kind = "certain" if labels[r["row_id"]]["label_source"] in CERTAIN_SOURCES else "weak"
        total[kind] += 1
        if r["label"] in ruled_out(feats):
            bad[kind] += 1
            examples.append(r["row_id"])
    return {"rows": dict(total), "ruled_out_own_label": dict(bad), "examples": examples[:5]}


def _apply(probs: np.ndarray, feats: list[dict[str, float | None]], classes: list[str]) -> np.ndarray:
    return np.array([move_ruled_out_mass(p, classes, ruled_out(f)) for p, f in zip(probs, feats)])


def oof_cost(seed: int = 7, repeats: int = 3) -> dict[str, Any]:
    pool = eb.load_training_pool(DS)
    names, X, y, k = pool["features"], pool["X"], pool["y"], len(pool["classes"])
    cols = eb.columns_for(names, ("static", "warnings", "semantics"))
    tri = np.flatnonzero(pool["split"] == "train")
    Xt, yt, ct = X[tri], y[tri], pool["cluster"][tri]
    meta = pool["meta"].iloc[tri].reset_index(drop=True)
    real = pool["source"][tri] != "SYNTHETIC"
    feats = [{n: (None if math.isnan(v) else float(v)) for n, v in zip(names, row)} for row in Xt]
    before, after = [], []
    changed = 0
    for rep in range(repeats):
        P = np.zeros((len(yt), k))
        for _, tr, va in eb.folds(yt, ct, seed + rep, 1):
            w, _ = trainer.compute_weights(meta.iloc[tr].reset_index(drop=True), 1.0)
            P[va] = trainer._fit_predict(Xt[tr][:, cols], yt[tr], w, Xt[va][:, cols], seed + rep, k)
        Pm = _apply(P, feats, pool["classes"])
        changed += int((P.argmax(1) != Pm.argmax(1)).sum())
        allc = list(range(k))
        before.append((trainer.macro_f1(yt, P.argmax(1), allc), trainer.macro_f1(yt[real], P[real].argmax(1), allc)))
        after.append((trainer.macro_f1(yt, Pm.argmax(1), allc), trainer.macro_f1(yt[real], Pm[real].argmax(1), allc)))
    b, a = np.mean(before, axis=0), np.mean(after, axis=0)
    return {
        "oof_macro_f1_all": {"without_rules": round(float(b[0]), 4), "with_rules": round(float(a[0]), 4)},
        "oof_macro_f1_non_synthetic": {"without_rules": round(float(b[1]), 4), "with_rules": round(float(a[1]), 4)},
        "top_class_changed_rows": changed, "repeats": repeats,
    }


def _full_features(row: dict[str, str]) -> dict[str, float | None]:
    return {k: _num(v) for k, v in row.items() if "." in k}


def unseen_behaviour(pool_name: str = "dev_gold") -> dict[str, Any]:
    dump = DS / "cache" / f"real_eval_features_{pool_name}.csv"
    rows = [r for r in csv.DictReader(dump.open(encoding="utf-8", newline="")) if r["branch"] == "failing"]
    feats = [_full_features(r) for r in rows]
    out: dict[str, Any] = {"pool": pool_name, "failing": len(rows)}
    for variant in ("best", "common"):
        model = ModelClassifier.load(variant)
        res = {}
        for label, flag in (("without_rules", False), ("with_rules", True)):
            preds = [model.predict(f, apply_applicability=flag) for f in feats]
            kept = [p for p in preds if not p.abstained]
            res[label] = {
                "abstain_rate": round(1 - len(kept) / len(preds), 3),
                "other_error_share_of_answers": round(sum(p.top_label == "CPP_OTHER_ERROR" for p in kept) / max(len(kept), 1), 3),
                "answer_histogram": dict(Counter(p.top_label for p in kept)),
            }
        res["rows_with_a_ruled_out_class"] = sum(1 for f in feats if ruled_out(f))
        res["top_class_was_ruled_out"] = sum(
            1 for f in feats if model.predict(f, apply_applicability=False).top_label in ruled_out(f))
        out[variant] = res
    return out


def open_set_reference() -> dict[str, Any]:
    pg = {r["row_id"]: r for r in csv.DictReader((DS / "features" / "features.csv").open(encoding="utf-8", newline=""))}
    items = []
    for sheet in ("dev_gold_progpedia", "iid_test_progpedia"):
        path = DS / "review" / "model_prereview" / f"{sheet}.csv"
        for r in csv.DictReader(path.open(encoding="utf-8", newline="")):
            if r["model_label"] and r["row_id"] in pg:
                items.append((r["model_label"], _full_features(pg[r["row_id"]])))
    out: dict[str, Any] = {"n": len(items), "reference": "model-assisted pre-review labels, unsigned; not gold",
                           "reference_other": sum(1 for lab, _ in items if lab == "CPP_OTHER_ERROR")}
    for variant in ("best", "common"):
        model = ModelClassifier.load(variant)
        res = {}
        for label, flag in (("without_rules", False), ("with_rules", True)):
            tally: Counter = Counter()
            for ref, f in items:
                p = model.predict(f, apply_applicability=flag)
                if ref == "CPP_OTHER_ERROR":
                    tally["other: abstain" if p.abstained else ("other: says OTHER" if p.top_label == ref else "other: FALSE ALARM")] += 1
                else:
                    tally["misconception: abstain" if p.abstained else
                          ("misconception: correct" if p.top_label == ref else "misconception: wrong class")] += 1
            res[label] = dict(sorted(tally.items()))
        out[variant] = res
    return out


def render(rep: dict[str, Any]) -> str:
    s, c, u, o = rep["safety"], rep["cost"], rep["unseen"], rep["open_set_reference"]
    lines = [
        "# Applicability rules: safety, cost and effect on real code", "",
        "Generated by `scripts/eval_applicability.py`. Do not edit by hand.", "",
        "## 1. Safety (does a rule ever rule out a row's own label?)", "",
        f"- Rows checked: {s['rows']} · rule violations: {s['ruled_out_own_label'] or 'none'}", "",
        "## 2. Cost (served `best`, grouped out-of-fold, 3 repeats)", "",
        "| Rows | Without rules | With rules |", "|---|---:|---:|",
        f"| all | {c['oof_macro_f1_all']['without_rules']} | {c['oof_macro_f1_all']['with_rules']} |",
        f"| non-synthetic | {c['oof_macro_f1_non_synthetic']['without_rules']} | {c['oof_macro_f1_non_synthetic']['with_rules']} |", "",
        f"Top class changed on {c['top_class_changed_rows']} row-repeats.", "",
        f"## 3. Unseen real failures (`{u['pool']}` clusters, {u['failing']} submissions)", "",
    ]
    for v in ("best", "common"):
        r = u[v]
        lines += [f"**{v}**: top class was ruled out on {r['top_class_was_ruled_out']} rows; "
                  f"{r['rows_with_a_ruled_out_class']} rows have at least one class ruled out.", "",
                  "| | Abstain rate | OTHER_ERROR share of answers | Answers |", "|---|---:|---:|---|"]
        for k in ("without_rules", "with_rules"):
            lines.append(f"| {k.replace('_', ' ')} | {r[k]['abstain_rate']} | {r[k]['other_error_share_of_answers']} | "
                         f"{r[k]['answer_histogram']} |")
        lines.append("")
    lines += [f"## 4. Open-set reference ({o['n']} held-out PROGPedia rows, {o['reference_other']} judged OTHER_ERROR)", "",
              f"_{o['reference']}._", ""]
    for v in ("best", "common"):
        lines.append(f"- **{v}** without rules: {o[v]['without_rules']}")
        lines.append(f"- **{v}** with rules: {o[v]['with_rules']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    rep = {"safety": safety(), "cost": oof_cost(), "unseen": unseen_behaviour(), "open_set_reference": open_set_reference()}
    reports = DS / "reports"
    (reports / "applicability.json").write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8", newline="\n")
    (reports / "applicability.md").write_text(render(rep), encoding="utf-8", newline="\n")
    print(render(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
