"""Score a model candidate on REAL training-side rows, grouped out-of-fold, through the served runtime.

    python scripts/eval_candidate_oof.py run data/misconception_dataset/candidates/served.json
    python scripts/eval_candidate_oof.py compare

Phase 0 of docs/MODEL_IMPROVEMENT_PLAN.md. Every later change to the model is judged by this
harness, never by the held-out split.

A candidate is data (a JSON file):

    {"name": "served",            # report name
     "variant": "execution",      # which served variant's feature list to start from
     "profile": "plain_reg",      # trainer profile (train_xgb_misconception.PROFILES)
     "balance": "none",           # plain-family class balance: none | sqrt | full
     "synthetic_multiplier": 1.0, # weight of every synthetic row
     "synthetic_class_weight": {},# extra weight on synthetic rows of one class (P1)
     "exclude_prefixes": null,    # synthetic row-id prefixes left out (null = trainer default)
     "synthetic_cap": null,       # {"ratio": 3, "min_real": 20}: at most ratio x real synthetic rows
                                  # per class, for classes with min_real real rows or more (P1)
     "drop_features": [],         # features removed from the variant's list (P1, P2)
     "drop_rule_only": false,     # train without the rows of the rule-only classes (RULE_ONLY_CLASSES);
                                  # they are still scored, so the real rows stay paired
     "real_augment": null,        # {"target": 60, "max_factor": 2, "k": 5, "swap": 0.5, "weight": 0.5}:
                                  # per fold, new rows for rare classes made from pairs of that fold's
                                  # REAL training rows (train_xgb_misconception.augment_real_rows)
     "calibration": "served",     # served | refit: temperature and threshold
     "bars": "served",            # served | none | cross_fit | {class: bar}
     "include_dev_gold": false,   # also train and score on the dev-gold rows (training-side)
     "run_records": true,         # narrow-repair evidence from cache/counterfactual/evidence_extra.jsonl
     "folds": 3, "repeats": 3, "seed": 7}

How: the rows the candidate trains on (train split, plus dev-gold if asked, filtered the way the
trainer filters its profile) are split into folds by problem cluster, 3 folds x 3 repeats. Each
row gets an out-of-fold probability from every repeat. Each repeat's probabilities, and their
mean over the repeats, then go through `runtime_decision` row by row, the same function the backend
and the held-out evaluator call: applicability rules, the class rule, repair-first and narrow-repair
stages, the threshold and the per-class bars, and the missing-feature abstention. Nothing is
re-implemented here, so the score is the served system's, not the classifier's alone.

What it reports, on real rows (the selection score) and, beside it, on all rows:
- macro-F1 per repeat (mean and spread) and on the mean of the repeats (the figure earlier
  reports quote); an abstention counts as a miss;
- per class precision, recall and F1, Wilson 95% intervals on precision and recall, support,
  and "not estimable" when the real support is under 10;
- false alarm on real OTHER_ERROR rows (flagged as a misconception, abstentions not counted);
- for each rule stage, how often it fired on real and synthetic rows and how often it was right.

`bars: "served"` reuses the bars in calibrator.json. They were fitted on these same out-of-fold
rows by `tune_class_thresholds.py`, so that score is slightly optimistic. `cross_fit` refits
them for each fold on the other folds' rows only, which is the honest setting for a new
candidate.

Writes data/misconception_dataset/reports/candidates/<name>.json; `compare` writes
candidates.md from every JSON there. The held-out test split is never read.
"""
from __future__ import annotations

import argparse
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

import train_xgb_misconception as T  # noqa: E402
from eval_blind_test import wilson  # noqa: E402
from eval_heldout_rows import load_run_records  # noqa: E402

from backend.app.diagnosis.xgb_classifier import (  # noqa: E402
    OTHER_LABEL,
    ModelClassifier,
    mask_rule_only,
    rescale,
    runtime_decision,
)

DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "reports" / "candidates"
RUN_RECORDS = DS / "cache" / "counterfactual" / "evidence_extra.jsonl"
ABSTAIN = "ABSTAIN"
MIN_SUPPORT = 10
DEFAULTS: dict[str, Any] = {
    "variant": "execution", "profile": None, "balance": "none", "synthetic_multiplier": 1.0,
    "synthetic_class_weight": {}, "exclude_prefixes": None, "synthetic_cap": None, "drop_features": [],
    "drop_rule_only": False, "real_augment": None,
    "calibration": "served", "bars": "served", "include_dev_gold": False, "run_records": True,
    "folds": 3, "repeats": 3, "seed": 7,
}
SPLITS = ("train", "dev_gold")


# ------------------------------------------------------------------ candidate and rows

def load_candidate(path: Path | str | dict) -> dict[str, Any]:
    spec = dict(path) if isinstance(path, dict) else json.loads(Path(path).read_text(encoding="utf-8"))
    unknown = sorted(set(spec) - set(DEFAULTS) - {"name", "note"})
    if unknown:
        raise ValueError(f"unknown candidate keys: {unknown}")
    if "name" not in spec:
        raise ValueError("a candidate needs a name")
    return {**DEFAULTS, **spec}


def configure_trainer(cand: dict[str, Any], served_profile: str) -> str:
    """Set the trainer's module-level profile, balance and exclusions; return the profile name."""
    profile = cand["profile"] or served_profile
    T.set_profile(profile)
    T.set_balance(cand["balance"])
    if cand["exclude_prefixes"] is not None:
        T.PLAIN_EXCLUDED_PREFIXES = tuple(cand["exclude_prefixes"])
    return profile


def load_rows(cand: dict[str, Any], profile: str, ds: Path = DS) -> list[dict[str, Any]]:
    """The rows the candidate trains on: train split (and dev-gold if asked), the trainer's row filter."""
    meta = {}
    for line in (ds / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            meta[r["row_id"]] = r
    with (ds / "splits" / "splits.csv").open(newline="", encoding="utf-8") as fh:
        split = {r["row_id"]: (r["cluster_id"], r["split"]) for r in csv.DictReader(fh)}
    wanted = SPLITS if cand["include_dev_gold"] else ("train",)
    rows = []
    with (ds / "features" / "features.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        col = {f: i for i, f in enumerate(header)}
        for rec in reader:
            rid = rec[0]
            if rid not in split or split[rid][1] not in wanted:
                continue
            m = meta[rid]
            if profile in T.PLAIN_FAMILY and not T.plain_row_selected(rid, m):
                continue
            feats = {f: (float(rec[col[f]]) if rec[col[f]] not in ("", "nan", "NaN") else math.nan)
                     for f in header[2:]}
            rows.append({
                "row_id": rid, "label": rec[1], "features": feats, "cluster": split[rid][0],
                "split": split[rid][1], "real": m["dataset_source"] != "SYNTHETIC",
                "label_confidence": float(m.get("label_confidence") or 0.6),
                "dataset_source": m["dataset_source"],
            })
    if cand["synthetic_cap"] is not None:
        rows = cap_synthetic(rows, cand["synthetic_cap"], cand["seed"])
    return rows


def cap_synthetic(rows: list[dict[str, Any]], cap: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    """Keep at most `ratio` x real synthetic rows per class (`train_xgb_misconception.synthetic_cap_drop`)."""
    drop = T.synthetic_cap_drop([r["label"] for r in rows], [r["cluster"] for r in rows],
                                [r["real"] for r in rows], cap, seed)
    return [r for i, r in enumerate(rows) if i not in drop]


def weights(rows: list[dict[str, Any]], cand: dict[str, Any]) -> np.ndarray:
    import pandas as pd

    frame = pd.DataFrame({"label": [r["label"] for r in rows],
                          "label_confidence": [r["label_confidence"] for r in rows],
                          "dataset_source": [r["dataset_source"] for r in rows]})
    w, _ = T.compute_weights(frame, float(cand["synthetic_multiplier"]))
    extra = cand["synthetic_class_weight"] or {}
    if extra:
        w = w * np.array([1.0 if r["real"] else float(extra.get(r["label"], 1.0)) for r in rows])
    return w


def oof_probabilities(rows, features: list[str], classes: list[str], cand: dict[str, Any]):
    """Per-repeat out-of-fold raw probabilities (repeats x rows x classes) and the fold of each row per repeat."""
    from sklearn.model_selection import StratifiedGroupKFold

    X = np.array([[r["features"].get(f, math.nan) for f in features] for r in rows], dtype=float)
    y = np.array([classes.index(r["label"]) for r in rows])
    groups = np.array([r["cluster"] for r in rows])
    w_all = weights(rows, cand)
    reps = np.zeros((cand["repeats"], len(rows), len(classes)))
    fold_of = np.zeros((cand["repeats"], len(rows)), dtype=int)
    real = np.array([r["real"] for r in rows])
    if cand["drop_rule_only"]:
        # Weight 0, the trainer's way (`train(drop_rule_only=True)`): the booster keeps one output
        # per class, so the served label encoder still matches, and those rows teach nothing.
        w_all = w_all * np.array([r["label"] not in T.RULE_ONLY_LABELS for r in rows], dtype=float)
    aug = cand["real_augment"]
    for rep in range(cand["repeats"]):
        splitter = StratifiedGroupKFold(cand["folds"], shuffle=True, random_state=cand["seed"] + rep)
        for k, (tr, va) in enumerate(splitter.split(X, y, groups)):
            X_tr, y_tr, w_tr = X[tr], y[tr], w_all[tr]
            if aug:
                X_new, y_new = T.augment_real_rows(X_tr, y_tr, real[tr], classes, aug,
                                                   cand["seed"] + 100 * rep + k)
                X_tr = np.vstack([X_tr, X_new])
                y_tr = np.concatenate([y_tr, y_new])
                w_tr = np.concatenate([w_tr, np.full(len(y_new), float(aug.get("weight", 0.5)))])
            reps[rep, va] = T._fit_predict(X_tr, y_tr, w_tr, X[va], cand["seed"], len(classes))
            fold_of[rep, va] = k
    return reps, fold_of, y


# ------------------------------------------------------------------ the served runtime on given probabilities

class PresetClassifier(ModelClassifier):
    """A ModelClassifier whose raw output is supplied, so `runtime_decision` can score out-of-fold rows.

    Only `_raw` is replaced: temperature, applicability, the threshold, the bars and every rule
    stage run exactly as they do in the backend.
    """

    def __init__(self, base: ModelClassifier, *, features: list[str], temperature: float,
                 threshold: float, class_thresholds: dict[str, float]) -> None:
        super().__init__(variant=base.variant, booster=None, features=features, classes=base.classes,
                         temperature=temperature, threshold=threshold, model_sha256="out-of-fold",
                         class_thresholds=class_thresholds)
        self.next_raw: np.ndarray | None = None

    def _raw(self, matrix: np.ndarray) -> np.ndarray:
        if self.next_raw is None:
            raise RuntimeError("PresetClassifier needs next_raw before predict")
        return np.asarray(self.next_raw, dtype=float).reshape(1, -1)


def decisions(clf: PresetClassifier, rows, raw: np.ndarray, records: dict[str, dict],
              bars_for_row: list[dict[str, float]] | None = None) -> list[tuple[str, str]]:
    """(decided label or ABSTAIN, decision source) for each row."""
    out = []
    base_bars = dict(clf.class_thresholds)
    for i, r in enumerate(rows):
        clf.next_raw = raw[i]
        clf.class_thresholds = bars_for_row[i] if bars_for_row is not None else base_bars
        pred = runtime_decision(clf, r["features"], records.get(r["row_id"]))
        out.append((ABSTAIN if pred.abstained else pred.top_label, pred.decision_source))
    clf.class_thresholds = base_bars
    return out


# ------------------------------------------------------------------ metrics

def class_stats(truth: list[str], pred: list[str], cls: str) -> dict[str, Any]:
    tp = sum(t == cls and p == cls for t, p in zip(truth, pred))
    fp = sum(t != cls and p == cls for t, p in zip(truth, pred))
    fn = sum(t == cls and p != cls for t, p in zip(truth, pred))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    p_lo, p_hi = wilson(tp, tp + fp)
    r_lo, r_hi = wilson(tp, tp + fn)
    return {
        "support": tp + fn, "flagged": tp + fp, "tp": tp,
        "precision": round(prec, 4), "precision_95": [_r(p_lo), _r(p_hi)],
        "recall": round(rec, 4), "recall_95": [_r(r_lo), _r(r_hi)],
        "f1": round(f1, 4), "estimable": tp + fn >= MIN_SUPPORT,
    }


def _r(x: float) -> float | None:
    return None if x is None or math.isnan(x) else round(x, 4)


def macro_f1(truth: list[str], pred: list[str]) -> float:
    """Mean F1 over the classes present in `truth`; an abstention is a miss."""
    def f1(cls: str) -> float:
        tp = sum(t == cls and p == cls for t, p in zip(truth, pred))
        miss = sum((t == cls) != (p == cls) for t, p in zip(truth, pred))
        return 2 * tp / (2 * tp + miss) if tp + miss else 0.0

    labels = sorted(set(truth))
    return float(np.mean([f1(c) for c in labels])) if labels else 0.0


def estimable_classes(truth: list[str]) -> list[str]:
    """Classes with at least MIN_SUPPORT rows in `truth`."""
    counts = Counter(truth)
    return sorted(c for c, n in counts.items() if n >= MIN_SUPPORT)


def macro_f1_over(truth: list[str], pred: list[str], classes: list[str]) -> float:
    """Mean F1 over a fixed class list (an abstention is a miss)."""
    if not classes:
        return 0.0
    vals = []
    for cls in classes:
        tp = sum(t == cls and p == cls for t, p in zip(truth, pred))
        miss = sum((t == cls) != (p == cls) for t, p in zip(truth, pred))
        vals.append(2 * tp / (2 * tp + miss) if tp + miss else 0.0)
    return float(np.mean(vals))


def false_alarm(truth: list[str], pred: list[str]) -> dict[str, Any]:
    other = [p for t, p in zip(truth, pred) if t == OTHER_LABEL]
    k = sum(p not in (OTHER_LABEL, ABSTAIN) for p in other)
    lo, hi = wilson(k, len(other))
    return {"k": k, "n": len(other), "value": round(k / len(other), 4) if other else None,
            "ci95": [_r(lo), _r(hi)]}


def stage_fires(rows, decided: list[tuple[str, str]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for stage in ("class_rule", "repair", "narrow_repair"):
        entry = {}
        for scope, keep in (("real", True), ("synthetic", False)):
            hits = [(r, d) for r, d in zip(rows, decided) if d[1] == stage and r["real"] == keep]
            right = sum(d[0] == r["label"] for r, d in hits)
            entry[scope] = {"fires": len(hits), "right": right,
                            "wrong_rows": sorted(r["row_id"] for r, d in hits if d[0] != r["label"])[:20]}
        out[stage] = entry
    return out


def score(rows, decided: list[tuple[str, str]], classes: list[str]) -> dict[str, Any]:
    real = [i for i, r in enumerate(rows) if r["real"]]
    truth_r = [rows[i]["label"] for i in real]
    pred_r = [decided[i][0] for i in real]
    truth_a = [r["label"] for r in rows]
    pred_a = [d[0] for d in decided]
    return {
        "real_rows": len(real), "all_rows": len(rows),
        "macro_f1_real": round(macro_f1(truth_r, pred_r), 4),
        # The selection score from P1 on: classes with a single real row move the plain mean by 0.09
        # per prediction, so it averages only the classes with MIN_SUPPORT real rows or more.
        "macro_f1_real_estimable": round(macro_f1_over(truth_r, pred_r, estimable_classes(truth_r)), 4),
        "macro_f1_all": round(macro_f1(truth_a, pred_a), 4),
        "false_alarm_real_other": false_alarm(truth_r, pred_r),
        "abstain_rate_real": round(sum(p == ABSTAIN for p in pred_r) / max(len(pred_r), 1), 4),
        "per_class_real": {c: class_stats(truth_r, pred_r, c) for c in classes},
        "per_class_all": {c: class_stats(truth_a, pred_a, c) for c in classes},
        "rule_stages": stage_fires(rows, decided),
    }


# ------------------------------------------------------------------ bars

def cross_fit_bars(clf: PresetClassifier, rows, raw: np.ndarray, folds: np.ndarray) -> list[dict[str, float]]:
    """Per row, the bars `tune_class_thresholds.tune` picks on the OTHER folds' rows only."""
    from tune_class_thresholds import tune

    from backend.app.diagnosis.applicability import move_ruled_out_mass, ruled_out

    calibrated = mask_rule_only(rescale(raw, clf.temperature), clf.classes)
    for i, r in enumerate(rows):
        out = ruled_out({k: (None if math.isnan(v) else v) for k, v in r["features"].items()})
        calibrated[i] = move_ruled_out_mass(calibrated[i], clf.classes, out)
    legacy = [(r["row_id"], r["label"], r["features"], r["real"]) for r in rows]
    per_row: list[dict[str, float]] = [{} for _ in rows]
    for k in sorted(set(folds.tolist())):
        fit = np.flatnonzero(folds != k)
        bars, _ = tune([legacy[i] for i in fit], calibrated[fit], clf.classes, clf.threshold)
        for i in np.flatnonzero(folds == k):
            per_row[i] = bars
    return per_row


# ------------------------------------------------------------------ run

def evaluate(cand: dict[str, Any], models_dir: Path = DS / "models", ds: Path = DS) -> dict[str, Any]:
    model = ModelClassifier.load(cand["variant"], models_dir)
    metrics = json.loads((models_dir / "metrics_v1.json").read_text(encoding="utf-8"))
    served_profile = (metrics.get("profile") or {}).get("name", "default")
    profile = configure_trainer(cand, served_profile)
    try:
        features = [f for f in model.features if f not in set(cand["drop_features"])]
        rows = load_rows(cand, profile, ds)
        reps, fold_of, y = oof_probabilities(rows, features, model.classes, cand)
        # The served classifier never names a rule-only class (RULE_ONLY_CLASSES), so calibration
        # and bars are fitted on probabilities with that mass already on OTHER_ERROR.
        reps = mask_rule_only(reps, model.classes)
    finally:
        T.set_profile("default")
        T.set_balance("none")

    temperature, threshold = model.temperature, model.threshold
    if cand["calibration"] == "refit":
        from calibration import calibrate_variant

        real = np.array([r["real"] for r in rows])
        cal = calibrate_variant(list(reps), y, np.array([r["cluster"] for r in rows]), real, cand["seed"],
                                other_idx=model.classes.index(OTHER_LABEL))
        temperature, threshold = float(cal["temperature"]), float(cal["threshold"])
    elif cand["calibration"] != "served":
        raise ValueError(f"calibration must be served or refit, not {cand['calibration']!r}")

    bars_spec = cand["bars"]
    fixed_bars = (model.class_thresholds if bars_spec == "served" else {} if bars_spec in ("none", "cross_fit")
                  else {str(k): float(v) for k, v in dict(bars_spec).items()})
    clf = PresetClassifier(model, features=features, temperature=temperature, threshold=threshold,
                           class_thresholds=fixed_bars)
    records = load_run_records(RUN_RECORDS) if cand["run_records"] else {}

    def run(raw: np.ndarray, folds: np.ndarray) -> tuple[dict[str, Any], list[tuple[str, str]]]:
        per_row = cross_fit_bars(clf, rows, raw, folds) if bars_spec == "cross_fit" else None
        decided = decisions(clf, rows, raw, records, per_row)
        return score(rows, decided, model.classes), decided

    per_repeat = [run(reps[k], fold_of[k])[0] for k in range(cand["repeats"])]
    pooled, pooled_decided = run(reps.mean(axis=0), fold_of[0])
    real_f1 = [s["macro_f1_real"] for s in per_repeat]
    est_f1 = [s["macro_f1_real_estimable"] for s in per_repeat]
    real_idx = [i for i, r in enumerate(rows) if r["real"]]
    all_f1 = [s["macro_f1_all"] for s in per_repeat]
    composition = Counter((r["label"], "real" if r["real"] else "synthetic") for r in rows)
    return {
        "candidate": cand,
        "served_model": {"variant": cand["variant"], "model_sha256": model.model_sha256[:12], "profile": served_profile},
        "trained_profile": profile,
        "n_features": len(features),
        "temperature": temperature, "threshold": threshold,
        "bars": fixed_bars if bars_spec != "cross_fit" else "cross_fit (per fold)",
        "run_records": len(records),
        "rows": {"real": sum(r["real"] for r in rows), "synthetic": sum(not r["real"] for r in rows),
                 "by_split": dict(Counter(r["split"] for r in rows))},
        "composition": {c: {"real": composition[(c, "real")], "synthetic": composition[(c, "synthetic")]}
                        for c in model.classes},
        "summary": {
            "macro_f1_real_mean": round(float(np.mean(real_f1)), 4),
            "macro_f1_real_sd": round(float(np.std(real_f1, ddof=1)) if len(real_f1) > 1 else 0.0, 4),
            "macro_f1_real_per_repeat": real_f1,
            "macro_f1_real_pooled": pooled["macro_f1_real"],
            "macro_f1_real_estimable_pooled": pooled["macro_f1_real_estimable"],
            "macro_f1_real_estimable_mean": round(float(np.mean(est_f1)), 4),
            "macro_f1_real_estimable_sd": round(float(np.std(est_f1, ddof=1)) if len(est_f1) > 1 else 0.0, 4),
            "real_clusters": len({rows[i]["cluster"] for i in real_idx}),
            "macro_f1_all_mean": round(float(np.mean(all_f1)), 4),
            "macro_f1_all_pooled": pooled["macro_f1_all"],
            "false_alarm_real_other_pooled": pooled["false_alarm_real_other"],
        },
        "pooled": pooled,
        "per_repeat": [{k: s[k] for k in ("macro_f1_real", "macro_f1_real_estimable", "macro_f1_all",
                                          "false_alarm_real_other", "abstain_rate_real")} for s in per_repeat],
        # The mean-of-repeats decision on every real row, for paired comparisons between candidates.
        "real_predictions": {
            "row_id": [rows[i]["row_id"] for i in real_idx],
            "cluster": [rows[i]["cluster"] for i in real_idx],
            "truth": [rows[i]["label"] for i in real_idx],
            "pred": [pooled_decided[i][0] for i in real_idx],
        },
    }


BOOTSTRAP = 2000
BOOTSTRAP_SEED = 20261122


def paired_difference(ref: dict[str, Any], cand: dict[str, Any], n: int = BOOTSTRAP,
                      seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    """Candidate minus reference on the same real rows, with a cluster bootstrap 95% interval.

    The real rows come from few problem clusters (24 on the train split), so rows of one problem
    are not independent: whole clusters are resampled. The class list of the estimable macro-F1
    is fixed from the full rows, so every resample averages the same classes.
    """
    a, b = ref["real_predictions"], cand["real_predictions"]
    if a["row_id"] != b["row_id"]:
        raise ValueError("candidates were scored on different real rows")
    truth, pa, pb, clusters = a["truth"], a["pred"], b["pred"], a["cluster"]
    classes = estimable_classes(truth)

    def fa(pred, idx):
        other = [i for i in idx if truth[i] == OTHER_LABEL]
        return sum(pred[i] not in (OTHER_LABEL, ABSTAIN) for i in other) / max(len(other), 1)

    def stats(idx):
        t = [truth[i] for i in idx]
        return (macro_f1_over(t, [pb[i] for i in idx], classes) - macro_f1_over(t, [pa[i] for i in idx], classes),
                fa(pb, idx) - fa(pa, idx))

    by_cluster: dict[str, list[int]] = {}
    for i, c in enumerate(clusters):
        by_cluster.setdefault(c, []).append(i)
    names = sorted(by_cluster)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n):
        idx = [i for j in rng.integers(0, len(names), len(names)) for i in by_cluster[names[j]]]
        draws.append(stats(idx))
    d = np.array(draws)
    point = stats(list(range(len(truth))))
    return {
        "macro_f1_estimable_diff": round(point[0], 4),
        "macro_f1_estimable_diff_95": [round(float(np.percentile(d[:, 0], 2.5)), 4),
                                       round(float(np.percentile(d[:, 0], 97.5)), 4)],
        "false_alarm_diff": round(point[1], 4),
        "false_alarm_diff_95": [round(float(np.percentile(d[:, 1], 2.5)), 4),
                                round(float(np.percentile(d[:, 1], 97.5)), 4)],
        "clusters": len(names), "resamples": n,
    }


def verdict(diff: dict[str, Any]) -> str:
    """Better only when the macro-F1 interval is above 0 and false alarm does not rise."""
    lo, hi = diff["macro_f1_estimable_diff_95"]
    if lo > 0 and diff["false_alarm_diff"] <= 0:
        return "better"
    if hi < 0:
        return "worse"
    return "no difference shown"


# ------------------------------------------------------------------ comparison table

def _cell(stats: dict[str, Any]) -> str:
    if not stats["estimable"]:
        return f"not estimable ({stats['support']})"
    return f"{stats['f1']:.2f} (R {stats['recall_95'][0]:.2f}-{stats['recall_95'][1]:.2f}, n={stats['support']})"


def compare(directory: Path = OUT, reference: str | None = None, prefix: str = "",
            name: str = "candidates.md") -> str:
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob(f"{prefix}*.json"))]
    ref = next((r for r in results if r["candidate"]["name"] == reference), None) if reference else None
    lines = ["# Candidates, grouped out-of-fold on real training-side rows", "",
             "Generated by `scripts/eval_candidate_oof.py compare`. Do not edit by hand.", "",
             "The selection score is real-row macro-F1 (mean and spread over the repeats); the all-row",
             "figure is shown beside it, never instead of it. A candidate counts as better only when it",
             "beats the served model by more than the spread of both (docs/MODEL_IMPROVEMENT_PLAN.md).", "",
             "| Candidate | Real rows | Real macro-F1 (mean ± sd) | Real macro-F1, mean of repeats | "
             "All-row macro-F1 | False alarm, real OTHER | Bars |",
             "|---|---|---|---|---|---|---|"]
    for r in results:
        s = r["summary"]
        fa = s["false_alarm_real_other_pooled"]
        lines.append(f"| {r['candidate']['name']} | {r['rows']['real']} | {s['macro_f1_real_mean']:.3f} ± "
                     f"{s['macro_f1_real_sd']:.3f} | {s['macro_f1_real_pooled']:.3f} | {s['macro_f1_all_pooled']:.3f} | "
                     f"{fa['value']} ({fa['k']}/{fa['n']}) | {r['candidate']['bars'] if isinstance(r['candidate']['bars'], str) else 'given'} |")
    if ref is not None:
        lines += ["", f"## Against `{reference}` (paired, same real rows)", "",
                  "Macro-F1 over the classes with at least 10 real rows, candidate minus reference, with a 95% "
                  "interval from resampling whole problem clusters. A candidate is better only when the "
                  "interval is above 0 and false alarm is not higher.", "",
                  "| Candidate | Estimable macro-F1 | Difference (95%) | False alarm difference (95%) | Verdict |",
                  "|---|---|---|---|---|"]
        for r in results:
            if r is ref or "real_predictions" not in r:
                continue
            d = paired_difference(ref, r)
            lines.append(f"| {r['candidate']['name']} | {r['summary']['macro_f1_real_estimable_pooled']:.3f} | "
                         f"{d['macro_f1_estimable_diff']:+.3f} ({d['macro_f1_estimable_diff_95'][0]:+.3f} to "
                         f"{d['macro_f1_estimable_diff_95'][1]:+.3f}) | {d['false_alarm_diff']:+.3f} "
                         f"({d['false_alarm_diff_95'][0]:+.3f} to {d['false_alarm_diff_95'][1]:+.3f}) | {verdict(d)} |")
    if results:
        classes = list(results[0]["pooled"]["per_class_real"])
        lines += ["", "## Per class on real rows (mean of repeats)", "",
                  f"F1, the 95% interval on recall, and the real support; under {MIN_SUPPORT} real rows the cell "
                  "reads \"not estimable\". The composition column is the first candidate's training rows.", "",
                  "| Class | Real / synthetic rows | " + " | ".join(r["candidate"]["name"] for r in results) + " |",
                  "|---|---|" + "---|" * len(results)]
        for c in classes:
            comp = results[0]["composition"][c]
            cells = [_cell(r["pooled"]["per_class_real"][c]) for r in results]
            lines.append(f"| {c.removeprefix('CPP_')} | {comp['real']} / {comp['synthetic']} | " + " | ".join(cells) + " |")
        lines += ["", "## Rule stages (mean of repeats)", "",
                  "| Candidate | Stage | Real fires (right) | Synthetic fires (right) | Wrong real rows |",
                  "|---|---|---|---|---|"]
        for r in results:
            for stage, e in r["pooled"]["rule_stages"].items():
                lines.append(f"| {r['candidate']['name']} | {stage} | {e['real']['fires']} ({e['real']['right']}) | "
                             f"{e['synthetic']['fires']} ({e['synthetic']['right']}) | "
                             f"{', '.join(e['real']['wrong_rows']) or '-'} |")
    text = "\n".join(lines) + "\n"
    (directory / name).write_text(text, encoding="utf-8", newline="\n")
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="score one candidate")
    r.add_argument("candidate", help="candidate JSON file")
    r.add_argument("--models-dir", default=str(DS / "models"))
    r.add_argument("--out", default=str(OUT))
    c = sub.add_parser("compare", help="write candidates.md from every result")
    c.add_argument("--out", default=str(OUT))
    c.add_argument("--reference", help="candidate every other one is compared with, paired")
    c.add_argument("--prefix", default="", help="only results whose file name starts with this")
    c.add_argument("--name", default="candidates.md", help="output file name")
    a = ap.parse_args(argv)

    if a.cmd == "compare":
        print(compare(Path(a.out), a.reference, a.prefix, a.name))
        return 0
    cand = load_candidate(a.candidate)
    result = evaluate(cand, Path(a.models_dir))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{cand['name']}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    s = result["summary"]
    print(f"{cand['name']}: real macro-F1 {s['macro_f1_real_mean']:.3f} ± {s['macro_f1_real_sd']:.3f} "
          f"(mean of repeats {s['macro_f1_real_pooled']:.3f}); all rows {s['macro_f1_all_pooled']:.3f}; "
          f"false alarm {s['false_alarm_real_other_pooled']['value']}; {result['rows']['real']} real rows -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
