#!/usr/bin/env python3
"""Task 9 — XGBoost misconception classifier (master plan §11.5 R6 -> G8).

R6 (training): consumes the merged artifacts (features.csv,
labels.jsonl, splits.csv) and produces the three required variants:

- **full** — every canonical feature; NaN handled natively by XGBoost
  (a lane block gap is missingness, not a value);
- **common-feature** — static+warnings blocks only (the forced-fallback
  variant if the source-shortcut test fails at G3/R4);
- **masked** — `lf_inputs` -> NaN on weak rows **at train time**
  (label_defining_features.json); eval rows stay unmasked, so the
  train/test mismatch is REAL and disclosed in metrics — this variant is
  informational only (v4.1 dropped its gate; G3d's behavioral checks
  replaced it).

Layer-3 weights (§8): `w = w_balance x w_confidence x w_source`,
clipped to [0.1, 10] (clip <= 10). `w_source`'s synthetic multiplier is
CV-selected inside train (grid 0.5-1.0). Global caps (synthetic mass
<= 50%, class mass <= 15%) are RECORDED as G8 checks, never enforced by
silent re-weighting — a violation is a finding, not something to hide.

Discipline (§11.5, G8):
- `assert gold not in train`, in-script: dev-gold clusters must be
  absent from train clusters (held-out clusters, §13.4);
- StratifiedGroupKFold by problem cluster, macro-F1;
- **one global threshold + temperature scaling on dev-gold ONLY**
  (isotonic banned; per-class thresholds infeasible at ~5/class); when
  dev-gold is too small to calibrate (< 10 rows) the calibrator records
  T=1.0/default threshold with an explicit note — probabilities are
  reported uncalibrated rather than overfit;
- deterministic under a fixed seed (single-threaded hist trees).

Outputs (models/): xgb_v1.json, xgb_masked_v1.json, xgb_common_v1.json,
metrics_v1.json (all variants + G8 block), label_encoder.json,
calibrator.json.

Usage:
    python scripts/train_xgb_misconception.py \
        [--dataset-dir data/misconception_dataset] \
        [--models-dir models] [--seed 7] [--cv-folds 3]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tracelearn_features.schema import feature_names  # noqa: E402

DEFAULT_DATASET_DIR = ROOT / "data" / "misconception_dataset"
DEFAULT_MODELS_DIR = DEFAULT_DATASET_DIR / "models"  # plan §7 final layout

WEIGHT_CLIP = (0.1, 10.0)
SYNTH_GRID = (0.5, 0.75, 1.0)
MIN_CALIBRATION_ROWS = 10     # below this, calibration is a fit on noise
DEFAULT_THRESHOLD = 0.5
COMMON_PREFIXES = ("static.", "warnings.")
BEST_PREFIXES = ("static.", "warnings.", "semantics.")


# ------------------------------------------------------------- weights


def compute_weights(
    meta: Any,
    synthetic_multiplier: float,
    clip: tuple[float, float] = WEIGHT_CLIP,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Layer-3 weights: w_balance x w_confidence x w_source, clipped.

    `meta` is a DataFrame with columns label, label_confidence,
    dataset_source. w_balance = n / (K * count) (mean ~1 per class);
    synthetic rows get `synthetic_multiplier`, real rows 1.0.
    """
    labels = meta["label"].to_numpy()
    conf = meta["label_confidence"].astype(float).to_numpy()
    source = meta["dataset_source"].to_numpy()
    n = len(labels)
    k = len(set(labels))
    counts = Counter(labels)
    balance = {lab: n / (k * counts[lab]) for lab in counts}
    w = np.array([balance[lab] for lab in labels], dtype=float) * conf
    w *= np.where(source == "SYNTHETIC", float(synthetic_multiplier), 1.0)
    clip_applied = int((w > clip[1]).sum() + (w < clip[0]).sum())
    w = np.clip(w, clip[0], clip[1])
    return w, {
        "clip_applied": clip_applied,
        "min": round(float(w.min()), 4),
        "max": round(float(w.max()), 4),
        "synthetic_multiplier": float(synthetic_multiplier),
    }


# ------------------------------------------------------------- masking


def mask_weak_inputs(
    X: np.ndarray,
    feature_list: Sequence[str],
    meta_rows: Sequence[dict[str, Any]],
    lf_features: dict[str, Sequence[str]],
) -> np.ndarray:
    """The masked variant (§11.5): NaN each weak row's firing LFs'
    `lf_inputs` columns. Synthetic and human rows are untouched — their
    labels never came from feature values."""
    Xm = np.array(X, dtype=float, copy=True)
    column = {name: i for i, name in enumerate(feature_list)}
    for i, row in enumerate(meta_rows):
        if row.get("label_source") != "weak_rule":
            continue
        to_mask: set[str] = set()
        for lf in row.get("firing_functions") or []:
            to_mask.update(lf_features.get(lf, ()))
        for name in to_mask:
            if name in column:
                Xm[i, column[name]] = np.nan
    return Xm


# --------------------------------------------------------- calibration


def _nll(probs: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(probs[np.arange(len(y)), y], 1e-12, 1.0)
    return float(-np.log(p).mean())


def _rescale(probs: np.ndarray, temperature: float) -> np.ndarray:
    logp = np.log(np.clip(probs, 1e-12, 1.0)) / temperature
    ex = np.exp(logp - logp.max(axis=1, keepdims=True))
    return ex / ex.sum(axis=1, keepdims=True)


def fit_temperature(probs: np.ndarray, y: np.ndarray) -> float:
    """Temperature scaling on held-out data (isotonic banned, §11.5)."""
    grid = np.concatenate([[1.0], np.arange(0.1, 5.01, 0.1)])
    scores = [(_nll(_rescale(probs, float(t)), y), float(t)) for t in grid]
    best = min(scores)
    return best[1]


def tune_threshold(
    probs: np.ndarray,
    y: np.ndarray,
    grid: Sequence[float] | None = None,
) -> float:
    """ONE global threshold maximizing macro-F1 on held-out rows;
    abstention (max prob < t) counts as an error; ties break HIGHEST
    (most conservative abstention)."""
    if grid is None:
        grid = [round(x, 2) for x in np.arange(0.1, 0.951, 0.05)]
    pred = probs.argmax(axis=1)
    conf = probs.max(axis=1)
    classes = sorted(set(y.tolist()))
    best = (-1.0, DEFAULT_THRESHOLD)
    for t in grid:
        keep = conf >= t
        per_class = []
        for c in classes:
            tp = int(((pred == c) & (y == c) & keep).sum())
            fp = int(((pred == c) & (y != c) & keep).sum())
            fn = int(((y == c) & ~keep).sum()) + int(((pred != c) & (y == c) & keep).sum())
            denom = 2 * tp + fp + fn
            per_class.append(2 * tp / denom if denom else 0.0)
        macro = float(np.mean(per_class)) if per_class else 0.0
        if macro > best[0] or (macro == best[0] and t > best[1]):
            best = (macro, t)
    return float(best[1])


def ece(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error, confidence-decile bins."""
    conf = probs.max(axis=1)
    correct = (probs.argmax(axis=1) == y).astype(float)
    if len(y) == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (conf >= lo) & (conf <= hi if b == n_bins - 1 else conf < hi)
        if not mask.any():
            continue
        total += (mask.sum() / len(y)) * abs(correct[mask].mean() - conf[mask].mean())
    return float(total)


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, classes: Sequence[int]) -> float:
    vals = []
    for c in classes:
        tp = int(((y_pred == c) & (y_true == c)).sum())
        fp = int(((y_pred == c) & (y_true != c)).sum())
        fn = int(((y_pred != c) & (y_true == c)).sum())
        denom = 2 * tp + fp + fn
        vals.append(2 * tp / denom if denom else 0.0)
    return float(np.mean(vals)) if vals else 0.0


# --------------------------------------------------------------- model


def _make_model(seed: int):
    from xgboost import XGBClassifier

    return XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="multi:softprob",
        eval_metric="mlogloss",
        tree_method="hist",
        random_state=seed,
        n_jobs=1,          # single-threaded -> bit-deterministic trees
        verbosity=0,
    )


def _fit_model(X_train, y_train, w, seed: int):
    """Fit one booster; returns (model, classes_present).

    XGBoost requires contiguous 0..k-1 labels, but a CV fold-train split
    can lack a class entirely (rare classes land in one validation fold).
    y is remapped for the fit — mapping probabilities back to the global
    class list is the caller's job (`_to_global`), where an absent class
    simply carries probability 0.
    """
    uniq = np.unique(y_train)
    model = _make_model(seed)
    model.fit(X_train, uniq.searchsorted(y_train), sample_weight=w)
    return model, uniq


def _to_global(proba: np.ndarray, classes_present: np.ndarray, n_classes: int) -> np.ndarray:
    if len(classes_present) == n_classes:
        return proba
    padded = np.zeros((proba.shape[0], n_classes), dtype=float)
    for j, cls in enumerate(classes_present):
        padded[:, int(cls)] = proba[:, j]
    return padded


def _fit_predict(X_train, y_train, w, X_eval, seed: int, n_classes: int) -> np.ndarray:
    model, present = _fit_model(X_train, y_train, w, seed)
    return _to_global(model.predict_proba(X_eval), present, n_classes)


def _load_registry(dataset_dir: Path) -> dict[str, list[str]]:
    path = dataset_dir / "features" / "label_defining_features.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        lf: list(entry.get("features") or [])
        for lf, entry in (data.get("entries") or {}).items()
    }


def train(
    dataset_dir: Path,
    models_dir: Path,
    seed: int = 7,
    cv_folds: int = 3,
    cv_repeats: int = 1,
    synth_grid: Sequence[float] = SYNTH_GRID,
) -> dict[str, Any]:
    """Train the three variants; write models/ artifacts; return metrics."""
    import pandas as pd
    from sklearn.model_selection import StratifiedGroupKFold

    ds = Path(dataset_dir)
    models = Path(models_dir)
    models.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------- load
    meta_by_rid: dict[str, dict[str, Any]] = {}
    with (ds / "annotations" / "labels.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                meta_by_rid[row["row_id"]] = row

    with (ds / "features" / "features.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        feature_list = header[2:]
        rids, y_str, matrix = [], [], []
        for rec in reader:
            rids.append(rec[0])
            y_str.append(rec[1])
            matrix.append([float(v) if v not in ("", "nan", "NaN") else math.nan for v in rec[2:]])
    X = np.array(matrix, dtype=float)

    splits: dict[str, tuple[str, str]] = {}
    with (ds / "splits" / "splits.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        seen: set[str] = set()
        for rec in reader:
            if rec["row_id"] in seen:
                raise ValueError(f"gold discipline: duplicate row_id in splits.csv: {rec['row_id']}")
            seen.add(rec["row_id"])
            splits[rec["row_id"]] = (rec["cluster_id"], rec["split"])
    missing = [r for r in rids if r not in splits]
    if missing:
        raise ValueError(f"no split for rows: {missing[:5]}")

    # ------------------------------------------- gold-not-in-train assert
    gold_clusters = {splits[r][0] for r in rids if splits[r][1] == "dev_gold"}
    train_clusters = {splits[r][0] for r in rids if splits[r][1] == "train"}
    overlap = sorted(gold_clusters & train_clusters)
    if overlap:
        raise ValueError(
            f"gold in train: dev-gold cluster(s) {overlap[:3]} also appear in train — "
            "held-out clusters must not be shared (§13.4)"
        )

    keep = [i for i, r in enumerate(rids) if splits[r][1] in ("train", "dev_gold")]
    rids = [rids[i] for i in keep]
    y_str = [y_str[i] for i in keep]
    X = X[keep]
    meta = [meta_by_rid[r] for r in rids]
    cluster = np.array([splits[r][0] for r in rids])
    split = np.array([splits[r][1] for r in rids])

    classes = sorted(set(y_str))
    class_to_idx = {c: i for i, c in enumerate(classes)}
    y = np.array([class_to_idx[s] for s in y_str])
    train_mask = split == "train"
    dev_mask = split == "dev_gold"

    meta_df = pd.DataFrame({
        "label": [m["label"] for m in meta],
        "label_confidence": [float(m.get("label_confidence") or 0.6) for m in meta],
        "dataset_source": [m["dataset_source"] for m in meta],
    })

    # ------------------------------- CV: synthetic multiplier (train-only)
    # Dev-gold is NEVER inside CV folds: it is the calibration pool (§11.5).
    tr_idx = np.flatnonzero(train_mask)
    y_tr = y[tr_idx]
    cluster_tr = cluster[tr_idx]
    meta_tr = meta_df.iloc[tr_idx].reset_index(drop=True)

    def oof_for(X_train_src: np.ndarray, X_val_src: np.ndarray,
                multiplier: float,
                repeats: int = 1) -> tuple[np.ndarray, list[float]]:
        """OOF probabilities over the TRAIN rows. For the masked variant
        the fold-train matrix is masked while the fold-validation matrix
        is not — mirroring deployment (disclosed in metrics).

        Repeated grouped CV averages each row's predicted probabilities
        across repeats, which stabilises a 3-fold estimate on a small,
        cluster-scarce dataset. Every repeat uses a different fold seed.
        """
        oof_sum = np.zeros((len(tr_idx), len(classes)))
        oof_count = np.zeros(len(tr_idx), dtype=float)
        fold_scores = []
        for rep in range(max(1, int(repeats))):
            folds = StratifiedGroupKFold(
                n_splits=cv_folds, shuffle=True, random_state=seed + rep
            )
            for tr, va in folds.split(X_train_src, y_tr, groups=cluster_tr):
                w, _ = compute_weights(meta_tr.iloc[tr], multiplier)
                probs = _fit_predict(
                    X_train_src[tr], y_tr[tr], w, X_val_src[va], seed, len(classes)
                )
                oof_sum[va] += probs
                oof_count[va] += 1.0
                fold_scores.append(
                    macro_f1(y_tr[va], probs.argmax(axis=1), range(len(classes)))
                )
        oof = oof_sum / np.maximum(oof_count[:, None], 1.0)
        return oof, fold_scores

    grid_scores: dict[float, float] = {}
    for m in synth_grid:
        _, scores = oof_for(X[tr_idx], X[tr_idx], m, repeats=cv_repeats)
        grid_scores[float(m)] = float(np.mean(scores))
    best_mult = min(grid_scores, key=lambda m: (-grid_scores[m], m))

    def variant_metrics(oof: np.ndarray, fold_scores: list[float]) -> dict[str, Any]:
        pred = oof.argmax(axis=1)
        per_class = {}
        for i, c in enumerate(classes):
            tp = int(((pred == i) & (y_tr == i)).sum())
            fp = int(((pred == i) & (y_tr != i)).sum())
            fn = int(((y_tr == i) & (pred != i)).sum())
            prec = tp / (tp + fp) if tp + fp else 0.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
            per_class[c] = {"precision": round(prec, 4), "recall": round(rec, 4),
                            "f1": round(f1, 4), "support": int((y_tr == i).sum())}
        conf = [[int(((y_tr == i) & (pred == j)).sum()) for j in range(len(classes))]
                for i in range(len(classes))]
        return {
            "macro_f1_oof": round(macro_f1(y_tr, pred, range(len(classes))), 4),
            "per_class": per_class,
            "confusion": conf,
            "ece_oof": round(ece(oof, y_tr), 4),
            "cv_macro_f1_mean": round(float(np.mean(fold_scores)), 4),
            "cv_macro_f1_std": round(float(np.std(fold_scores)), 4),
        }

    # ------------------------------------------------- the three variants
    oof_full, fold_full = oof_for(
        X[tr_idx], X[tr_idx], best_mult, repeats=cv_repeats
    )
    full_metrics = variant_metrics(oof_full, fold_full)
    full_metrics["features"] = list(feature_names())

    common_idx = [i for i, f in enumerate(feature_list) if f.startswith(COMMON_PREFIXES)]
    X_common = X[:, common_idx]
    oof_common, fold_common = oof_for(
        X_common[tr_idx], X_common[tr_idx], best_mult, repeats=cv_repeats
    )
    common_metrics = variant_metrics(oof_common, fold_common)
    common_metrics["features"] = [feature_list[i] for i in common_idx]

    best_idx = [i for i, f in enumerate(feature_list) if f.startswith(BEST_PREFIXES)]
    X_best = X[:, best_idx]
    oof_best, fold_best = oof_for(
        X_best[tr_idx], X_best[tr_idx], best_mult, repeats=cv_repeats
    )
    best_metrics = variant_metrics(oof_best, fold_best)
    best_metrics["features"] = [feature_list[i] for i in best_idx]
    best_metrics["role"] = (
        "accuracy-oriented: static + warnings + source semantics; "
        "G8 still rides on full"
    )

    lf_features = _load_registry(ds)
    X_masked = mask_weak_inputs(X, feature_list, meta, lf_features)
    oof_masked, fold_masked = oof_for(
        X_masked[tr_idx], X[tr_idx], best_mult, repeats=cv_repeats
    )
    masked_metrics = variant_metrics(oof_masked, fold_masked)
    masked_metrics["role"] = (
        "informational only (v4.1): lf_inputs NaN'd on weak rows at train "
        "time; eval rows unmasked — the train/test mismatch is real and "
        "disclosed, no gate rides on this variant"
    )
    masked_metrics["train_test_mismatch"] = (
        "weak-row lf_inputs masked during training folds; validation-fold "
        "and dev-gold rows are unmasked, mirroring deployment"
    )
    masked_metrics["features"] = list(feature_list)

    # ------------------------------------------- final fit + calibration
    w_final, weight_stats = compute_weights(meta_df[train_mask], best_mult)
    final_model, final_present = _fit_model(X[train_mask], y[train_mask], w_final, seed)

    def final_proba(A: np.ndarray) -> np.ndarray:
        return _to_global(final_model.predict_proba(A), final_present, len(classes))

    n_dev = int(dev_mask.sum())
    calibrator: dict[str, Any] = {
        "temperature": 1.0,
        "threshold": DEFAULT_THRESHOLD,
        "fitted_on": {"n": n_dev, "split": "dev_gold"},
        "isotonic_used": False,
        "scope": "one global threshold + temperature",
    }
    dev_metrics: dict[str, Any] = {"n": n_dev, "calibrated": False}
    if n_dev >= MIN_CALIBRATION_ROWS:
        dev_probs = final_proba(X[dev_mask])
        temperature = fit_temperature(dev_probs, y[dev_mask])
        threshold = tune_threshold(_rescale(dev_probs, temperature), y[dev_mask])
        calibrator["temperature"] = round(float(temperature), 4)
        calibrator["threshold"] = round(float(threshold), 4)
        calibrator["note"] = f"fitted on {n_dev} dev-gold rows"
        dev_metrics["calibrated"] = True
        scaled = _rescale(dev_probs, temperature)
        pred_dev = np.where(scaled.max(axis=1) >= threshold, scaled.argmax(axis=1), -1)
        dev_metrics["macro_f1"] = round(
            macro_f1(y[dev_mask], pred_dev, range(len(classes))), 4)
        dev_metrics["ece"] = round(ece(dev_probs, y[dev_mask]), 4)
    else:
        calibrator["note"] = (
            f"dev-gold too small for calibration ({n_dev} < {MIN_CALIBRATION_ROWS} rows); "
            "probabilities reported uncalibrated (temperature=1.0, threshold="
            f"{DEFAULT_THRESHOLD}) — isotonic banned, no overfit calibration"
        )
        if n_dev:
            dev_probs = final_proba(X[dev_mask])
            dev_metrics["ece"] = round(ece(dev_probs, y[dev_mask]), 4)
            dev_metrics["macro_f1_uncalibrated"] = round(
                macro_f1(y[dev_mask], dev_probs.argmax(axis=1), range(len(classes))), 4)

    # ---------------------------------------------------------- G8 block
    majority = Counter(y[train_mask].tolist()).most_common(1)[0][0]
    majority_pred = np.full(int(train_mask.sum()), majority)
    majority_baseline = macro_f1(y[train_mask], majority_pred, range(len(classes)))
    train_weights = w_final
    total_mass = float(train_weights.sum())
    synthetic_mask = (meta_df[train_mask]["dataset_source"] == "SYNTHETIC").to_numpy()
    synthetic_mass = float(train_weights[synthetic_mask].sum() / total_mass) if total_mass else 0.0
    class_mass = {}
    for i, c in enumerate(classes):
        m = (y[train_mask] == i)
        class_mass[c] = round(float(train_weights[m].sum() / total_mass), 4) if total_mass else 0.0
    margin = full_metrics["cv_macro_f1_mean"] - majority_baseline

    g8 = {
        "gold_not_in_train": not overlap,
        "weight_clip": WEIGHT_CLIP[1],
        "weight_stats": weight_stats,
        "synthetic_mass": round(synthetic_mass, 4),
        "synthetic_mass_ok": synthetic_mass <= 0.50,
        "max_class_mass": max(class_mass.values()) if class_mass else 0.0,
        "max_class_mass_ok": all(v <= 0.15 for v in class_mass.values()),
        "class_mass": class_mass,
        "cv_beats_majority_by_0.25": bool(margin >= 0.25),
        "cv_margin": round(margin, 4),
        "threshold_scope": "one global threshold + temperature",
        "isotonic_used": False,
        "dev_gold_n": n_dev,
        "note": "caps recorded, not silently enforced — a violation is a "
                "finding for the team, per §8 Layer-3",
    }

    metrics: dict[str, Any] = {
        "seed": seed,
        "n_rows": len(y),
        "n_train": int(train_mask.sum()),
        "n_dev_gold": n_dev,
        "classes": classes,
        "cv": {
            "folds": cv_folds,
            "repeats": int(cv_repeats),
            "grouped_by": "problem_cluster",
            "synthetic_multiplier": best_mult,
            "grid_scores": {str(k): round(v, 4) for k, v in grid_scores.items()},
            "macro_f1_mean": full_metrics["cv_macro_f1_mean"],
            "macro_f1_std": full_metrics["cv_macro_f1_std"],
            "majority_baseline": round(majority_baseline, 4),
        },
        "full": full_metrics,
        "masked": masked_metrics,
        "common": common_metrics,
        "best": best_metrics,
        "dev_gold": dev_metrics,
        "g8": g8,
    }

    # ---------------------------------------------------------- outputs
    final_model.save_model(str(models / "xgb_v1.json"))
    masked_model, _ = _fit_model(X_masked[train_mask], y[train_mask], w_final, seed)
    masked_model.save_model(str(models / "xgb_masked_v1.json"))
    common_model, _ = _fit_model(X_common[train_mask], y[train_mask], w_final, seed)
    common_model.save_model(str(models / "xgb_common_v1.json"))
    best_model, _ = _fit_model(X_best[train_mask], y[train_mask], w_final, seed)
    best_model.save_model(str(models / "xgb_best_v1.json"))

    (models / "label_encoder.json").write_text(
        json.dumps({"class_to_idx": class_to_idx, "idx_to_class": classes}, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    (models / "calibrator.json").write_text(
        json.dumps(calibrator, indent=2) + "\n", encoding="utf-8", newline="\n")
    (models / "metrics_v1.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8", newline="\n")

    return metrics


# ------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--cv-folds", type=int, default=3)
    parser.add_argument("--cv-repeats", type=int, default=3)
    args = parser.parse_args(argv)

    try:
        metrics = train(
            dataset_dir=args.dataset_dir,
            models_dir=args.models_dir,
            seed=args.seed,
            cv_folds=args.cv_folds,
            cv_repeats=args.cv_repeats,
        )
    except ValueError as exc:
        print(f"FAIL  {exc}")
        return 1

    cv = metrics["cv"]
    print(f"rows: {metrics['n_rows']} (train={metrics['n_train']}, dev_gold={metrics['n_dev_gold']}), "
          f"classes={len(metrics['classes'])}")
    print(f"CV ({cv['folds']} StratifiedGroupKFold by cluster): "
          f"macro-F1 {cv['macro_f1_mean']} +/- {cv['macro_f1_std']} "
          f"vs majority {cv['majority_baseline']} (margin {metrics['g8']['cv_margin']})")
    print(f"synthetic multiplier: {cv['synthetic_multiplier']} (grid {cv['grid_scores']})")
    for variant in ("full", "masked", "common", "best"):
        v = metrics[variant]
        extra = f", role={v['role'][:40]}..." if "role" in v else ""
        print(f"  {variant:8s} OOF macro-F1={v['macro_f1_oof']} ece={v['ece_oof']}{extra}")
    g8 = metrics["g8"]
    for check, ok in (
        ("gold not in train", g8["gold_not_in_train"]),
        ("CV beats majority by >=0.25", g8["cv_beats_majority_by_0.25"]),
        ("synthetic mass <= 50%", g8["synthetic_mass_ok"]),
        ("class mass <= 15%", g8["max_class_mass_ok"]),
    ):
        print(f"G8 {'PASS' if ok else 'FAIL'}  {check}")
    print(f"calibrator: {json.loads((Path(args.models_dir) / 'calibrator.json').read_text(encoding='utf-8'))['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
