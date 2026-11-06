"""EXPERIMENT: train with real "no rule fired" failures as weak OTHER_ERROR (not adopted).

    python scripts/experiment_weak_other.py

Why. 27 of 30 CodeStream items pre-reviewed by the model-assisted reviewer and 14
of 34 held-out PROGPedia items were OTHER_ERROR, but the training set holds 13
OTHER_ERROR rows, all mutant decoys. The model has never seen a real program
that is wrong for none of the ten reasons, so it names one of the ten.

The binding rule this experiment departs from (master plan §13.5, v4.1 fix): "unreviewed
no-fire rows are never labeled; REAL OTHER_ERROR rows are human-confirmed only",
because real instances of the hard classes (UNINITIALIZED_VAR, WRONG_LOOP_DIR,
RANGE_CHECK, STALE_EXIT) have no detector and would be taught as OTHER. So nothing
here writes into the dataset or the served model: it trains throw-away models in
memory and reports what would change, for the owner to decide.

Rows used: failing CodeStream submissions in TRAIN clusters where no labeling
function fired and no repair verified (`codestream_failing_index.csv`), features
from the gitignored dump of `eval_real_data.py --pool train --features-only`.
Label OTHER_ERROR, confidence 0.3 (trainer weights then shrink them), capped per
problem so one problem cannot dominate.

Reported per configuration (served `best` columns, grouped CV, 3 repeats):
- out-of-fold macro-F1 on the ORIGINAL rows only (does adding OTHER hurt?);
- on the unseen dev-gold clusters: abstain rate and OTHER share of answers;
- the open-set reference (14 held-out PROGPedia rows judged OTHER by the
  unsigned model-assisted pre-review): false-alarm count.
Contamination is unknown: some no-fire rows are real instances of a modelled
class the rules cannot see. The pre-review suggests about 10%.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
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
from backend.app.diagnosis.xgb_classifier import rescale  # noqa: E402

DS = eb.DATASET_DIR
OTHER = "CPP_OTHER_ERROR"
WEAK_CONFIDENCE = 0.3
PER_PROBLEM_CAP = 8
SERVED = ("static", "warnings", "semantics")


def _num(v: str) -> float:
    try:
        return math.nan if v in ("", "nan", "NaN") else float(v)
    except ValueError:
        return math.nan


def no_fire_train_rows(names: list[str], cap: int | None) -> tuple[np.ndarray, list[str], list[str]]:
    index = {r["submission_id"]: r for r in csv.DictReader(
        (DS / "annotations" / "codestream_failing_index.csv").open(encoding="utf-8", newline=""))}
    dump = DS / "cache" / "real_eval_features_train.csv"
    rows, clusters, problems = [], [], []
    seen: dict[str, int] = defaultdict(int)
    for r in csv.DictReader(dump.open(encoding="utf-8", newline="")):
        meta = index.get(r["submission_id"])
        if not meta or meta["split_pool"] != "train" or meta["decision"] != "no_fire" or r["branch"] != "failing":
            continue
        if cap is not None and seen[r["problem_id"]] >= cap:
            continue
        seen[r["problem_id"]] += 1
        rows.append([_num(r[n]) for n in names])
        clusters.append(r["cluster"])
        problems.append(r["problem_id"])
    return np.array(rows, dtype=float), clusters, problems


def build(pool: dict[str, Any], cap: int | None):
    """Training matrix, labels, clusters, meta, is_aug mask for one configuration."""
    import pandas as pd

    names = pool["features"]
    tri = np.flatnonzero(pool["split"] == "train")
    X, y, cl = pool["X"][tri], pool["y"][tri], pool["cluster"][tri]
    meta = pool["meta"].iloc[tri].reset_index(drop=True)
    is_aug = np.zeros(len(y), dtype=bool)
    if cap is not None:
        ax, acl, _ = no_fire_train_rows(names, cap if cap > 0 else None)
        if len(ax):
            other_idx = pool["classes"].index(OTHER)
            X = np.vstack([X, ax])
            y = np.r_[y, np.full(len(ax), other_idx)]
            cl = np.r_[cl, np.array(acl)]
            meta = pd.concat([meta, pd.DataFrame({"label": [OTHER] * len(ax),
                                                  "label_confidence": [WEAK_CONFIDENCE] * len(ax),
                                                  "dataset_source": ["CODESTREAM"] * len(ax)})], ignore_index=True)
            is_aug = np.r_[is_aug, np.ones(len(ax), dtype=bool)]
    return X, y, cl, meta, is_aug


def _feature_dicts(X: np.ndarray, names: list[str]) -> list[dict[str, float | None]]:
    return [{n: (None if math.isnan(v) else float(v)) for n, v in zip(names, row)} for row in X]


def evaluate(pool: dict[str, Any], cap: int | None, seed: int = 7, repeats: int = 3) -> dict[str, Any]:
    names, classes, k = pool["features"], pool["classes"], len(pool["classes"])
    cols = eb.columns_for(names, SERVED)
    X, y, cl, meta, is_aug = build(pool, cap)
    scores = []
    for rep in range(repeats):
        P = np.zeros((len(y), k))
        for _, tr, va in eb.folds(y, cl, seed + rep, 1):
            w, _ = trainer.compute_weights(meta.iloc[tr].reset_index(drop=True), 1.0)
            P[va] = trainer._fit_predict(X[tr][:, cols], y[tr], w, X[va][:, cols], seed + rep, k)
        keep = ~is_aug
        scores.append(trainer.macro_f1(y[keep], P[keep].argmax(1), list(range(k))))
    out: dict[str, Any] = {"aug_rows": int(is_aug.sum()), "aug_problems": len(set(cl[is_aug].tolist())),
                           "oof_macro_f1_original_rows": round(float(np.mean(scores)), 4)}

    # final model on everything, then behaviour on unseen real code (with the applicability rules, as served)
    w, _ = trainer.compute_weights(meta, 1.0)
    model, present = trainer._fit_model(X[:, cols], y, w, seed)

    def predict(rows: list[dict[str, float | None]], full: np.ndarray) -> list[tuple[str, float]]:
        probs = trainer._to_global(model.predict_proba(full[:, cols]), present, k)
        probs = rescale(probs, 1.0)
        res = []
        for p, f in zip(probs, rows):
            q = move_ruled_out_mass(p, classes, ruled_out(f))
            res.append((classes[int(q.argmax())], float(q.max())))
        return res

    dump = DS / "cache" / "real_eval_features_dev_gold.csv"
    unseen = [r for r in csv.DictReader(dump.open(encoding="utf-8", newline="")) if r["branch"] == "failing"]
    Xu = np.array([[_num(r[n]) for n in names] for r in unseen], dtype=float)
    pu = predict(_feature_dicts(Xu, names), Xu)
    threshold = 0.42    # the served best threshold, so configurations are comparable
    answered = [lab for lab, p in pu if p >= threshold]
    out["unseen_dev_gold"] = {
        "failing": len(unseen), "abstain_rate": round(1 - len(answered) / len(pu), 3),
        "other_share_of_answers": round(sum(a == OTHER for a in answered) / max(len(answered), 1), 3),
        "answers": dict(Counter(answered)),
    }

    feats = {r["row_id"]: r for r in csv.DictReader((DS / "features" / "features.csv").open(encoding="utf-8", newline=""))}
    ref = []
    for sheet in ("dev_gold_progpedia", "iid_test_progpedia"):
        for r in csv.DictReader((DS / "review" / "model_prereview" / f"{sheet}.csv").open(encoding="utf-8", newline="")):
            if r["model_label"] and r["row_id"] in feats:
                ref.append((r["model_label"], [_num(feats[r["row_id"]][n]) for n in names]))
    Xr = np.array([v for _, v in ref], dtype=float)
    pr = predict(_feature_dicts(Xr, names), Xr)
    tally: Counter = Counter()
    for (truth, _), (lab, p) in zip(ref, pr):
        if truth == OTHER:
            tally["other: abstain" if p < threshold else ("other: says OTHER" if lab == OTHER else "other: FALSE ALARM")] += 1
        else:
            tally["misconception: abstain" if p < threshold else
                  ("misconception: correct" if lab == truth else "misconception: wrong class")] += 1
    out["open_set_reference"] = dict(sorted(tally.items()))
    return out


def main() -> int:
    pool = eb.load_training_pool(DS)
    report = {
        "note": "throw-away models; nothing is written to the dataset or the served model",
        "contamination_estimate": "about 10% (3 of 30 CodeStream pre-reviewed items were a modelled class)",
        "configurations": {
            "baseline (no real OTHER)": evaluate(pool, None),
            f"+ real no-fire rows, up to {PER_PROBLEM_CAP} per problem": evaluate(pool, PER_PROBLEM_CAP),
            "+ all real no-fire rows": evaluate(pool, 0),
        },
    }
    out = DS / "reports" / "experiment_weak_other.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    for name, r in report["configurations"].items():
        print(f"\n{name}\n  aug rows {r['aug_rows']} from {r['aug_problems']} problems · OOF macro-F1 on original rows "
              f"{r['oof_macro_f1_original_rows']}\n  unseen: {r['unseen_dev_gold']}\n  reference: {r['open_set_reference']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
