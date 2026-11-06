"""Temperature + abstain threshold from out-of-fold predictions (master plan §11, G8).

Why this exists. The first calibrator was fitted on the 45 dev-gold rows, most of
them weak labels. Retraining alone moved its threshold from 0.30 to 0.45, and on
real CodeStream code the model then abstained on about 70% of failures. A
threshold estimated from 45 rows is mostly noise.

What this does instead. The grouped cross-validation the trainer already runs
gives out-of-fold (OOF) probabilities for every training row, one matrix per
repeat. Each repeat is one model predicting rows it did not see, which is how the
deployed single model meets new data (averaging repeats would make the
probabilities look less confident than the deployed model is). From those:

1. Temperature: the NLL-optimal T, applied ONLY if it lowers expected
   calibration error on the same rows; otherwise T = 1.
2. Threshold: the smallest t whose answered NON-SYNTHETIC rows are right at
   least TARGET_PRECISION of the time (selective classification), because real
   code is the population the product serves and mutants are easy. If there are
   too few real rows, all rows are used and the report says so.
3. Stability: clusters are resampled with replacement; the shipped threshold is
   the median over resamples and the 5th-95th percentile range is stored. A wide
   range is a finding, not something to hide.

Constraints kept from the master plan: one global threshold and one temperature
per variant, no isotonic regression, no per-class thresholds, nothing tuned on
the test pool.

Pre-registration, written before looking at any real-code abstain rate: the
target precision is 0.80 and the bootstrap has 200 resamples. The OOF risk
table was inspected before 0.80 was chosen, so the target is a stated policy, not
a discovered optimum. Sensitivity (0.70 / 0.90) is stored next to the result.

Change after seeing the enlarged real set (2026-11-07). With 105 real OTHER_ERROR
rows in training, the 80%-agreement rule above could only be met at thresholds of
0.86-0.92, where the served model abstained on 95% of real rows. When the caller
passes `other_idx`, the threshold is instead the one that maximises F-beta (beta 0.5,
precision weighted twice as heavily as recall) of "flagged with the right
misconception name" on the non-synthetic rows. A wrong name costs a student more than
a missed one, and the criterion does not collapse. The old rule remains the default
when `other_idx` is omitted. This was decided after looking at out-of-fold results on
the real rows, and is disclosed as such.

Limits stated in the output: "correct" means "agrees with the row's label"; for
non-synthetic rows those are mostly weak-rule labels, so precision here measures
agreement with the rules, not with a human. Out-of-fold real rows are also more
familiar than brand-new classrooms (observed: mean top probability 0.61 out of
fold versus 0.42 on unseen CodeStream clusters), so calibration here cannot
remove domain shift.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np

TARGET_PRECISION = 0.80
SENSITIVITY_TARGETS = (0.70, 0.90)
BOOTSTRAP_RESAMPLES = 200
MIN_REAL_ROWS = 40          # below this the real-row criterion is not usable
MIN_ANSWERED_REAL = 20      # a threshold must keep at least this many real rows answered
GRID = tuple(round(x, 2) for x in np.arange(0.10, 0.951, 0.01))
TEMPERATURE_GRID = tuple(np.concatenate([[1.0], np.arange(0.5, 3.01, 0.1)]).round(2).tolist())


def rescale(probs: np.ndarray, temperature: float) -> np.ndarray:
    """Temperature scaling; identical to the trainer's and the classifier's."""
    logp = np.log(np.clip(probs, 1e-12, 1.0)) / temperature
    ex = np.exp(logp - logp.max(axis=1, keepdims=True))
    return ex / ex.sum(axis=1, keepdims=True)


def expected_calibration_error(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    conf = probs.max(axis=1)
    correct = (probs.argmax(axis=1) == y).astype(float)
    if len(y) == 0:
        return math.nan
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (conf >= lo) & (conf <= hi if b == n_bins - 1 else conf < hi)
        if mask.any():
            total += (mask.sum() / len(y)) * abs(correct[mask].mean() - conf[mask].mean())
    return float(total)


def _nll(probs: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(probs[np.arange(len(y)), y], 1e-12, 1.0)).mean())


def stack(prob_list: Sequence[np.ndarray], y: np.ndarray, *aligned: np.ndarray) -> tuple[np.ndarray, ...]:
    """Stack per-repeat OOF matrices into one sample (rows repeat across repeats)."""
    reps = len(prob_list)
    return (np.vstack(list(prob_list)), np.tile(y, reps), *[np.tile(a, reps) for a in aligned])


def fit_temperature_if_it_helps(probs: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """NLL-optimal T, kept only when it lowers ECE; otherwise T = 1."""
    ece_raw = expected_calibration_error(probs, y)
    best_t = min(TEMPERATURE_GRID, key=lambda t: (_nll(rescale(probs, t), y), t))
    ece_scaled = expected_calibration_error(rescale(probs, best_t), y)
    use = best_t != 1.0 and ece_scaled < ece_raw
    return {
        "temperature": float(best_t if use else 1.0),
        "nll_optimal_temperature": float(best_t),
        "ece_raw": round(ece_raw, 4),
        "ece_at_nll_optimal": round(ece_scaled, 4),
        "applied": bool(use),
    }


def select_threshold(conf: np.ndarray, correct: np.ndarray, is_real: np.ndarray, target: float) -> dict[str, Any]:
    """Smallest grid threshold whose answered rows reach `target` precision."""
    use_real = int(is_real.sum()) >= MIN_REAL_ROWS
    mask_pop = is_real if use_real else np.ones_like(is_real, dtype=bool)
    chosen = None
    for t in GRID:
        answered = mask_pop & (conf >= t)
        if answered.sum() < (MIN_ANSWERED_REAL if use_real else MIN_ANSWERED_REAL * 2):
            break  # higher thresholds only answer fewer rows
        if correct[answered].mean() >= target:
            chosen = t
            break
    return {
        "threshold": chosen,
        "population": "non_synthetic" if use_real else "all_rows (too few real rows)",
        "reached": chosen is not None,
    }


def risk_coverage(conf: np.ndarray, correct: np.ndarray, is_real: np.ndarray,
                  thresholds: Sequence[float] = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)) -> list[dict[str, Any]]:
    rows = []
    for t in thresholds:
        a = conf >= t
        ar = a & is_real
        rows.append({
            "threshold": t,
            "coverage_all": round(float(a.mean()), 3),
            "precision_all": round(float(correct[a].mean()), 3) if a.any() else None,
            "coverage_real": round(float(ar.sum() / max(is_real.sum(), 1)), 3),
            "precision_real": round(float(correct[ar].mean()), 3) if ar.any() else None,
        })
    return rows


def bootstrap_threshold(
    probs: np.ndarray, y: np.ndarray, cluster: np.ndarray, is_real: np.ndarray,
    target: float, seed: int, resamples: int = BOOTSTRAP_RESAMPLES,
) -> list[float]:
    """Thresholds from resampling whole clusters (rows of one problem move together)."""
    rng = np.random.default_rng(seed)
    clusters = np.unique(cluster)
    by_cluster = {c: np.flatnonzero(cluster == c) for c in clusters}
    conf = probs.max(axis=1)
    correct = (probs.argmax(axis=1) == y)
    draws: list[float] = []
    for _ in range(resamples):
        picked = rng.choice(clusters, size=len(clusters), replace=True)
        idx = np.concatenate([by_cluster[c] for c in picked])
        t = select_threshold(conf[idx], correct[idx], is_real[idx], target)["threshold"]
        if t is not None:
            draws.append(float(t))
    return draws


FBETA = 0.5


def fbeta_threshold(scaled: np.ndarray, y: np.ndarray, is_real: np.ndarray, other_idx: int,
                    beta: float = FBETA) -> dict[str, Any]:
    """Threshold maximising F-beta of "flagged with the right misconception name" on real rows."""
    conf, top = scaled.max(axis=1), scaled.argmax(axis=1)
    real = is_real if int(is_real.sum()) >= MIN_REAL_ROWS else np.ones_like(is_real, dtype=bool)
    misc_truth = real & (y != other_idx)
    best = {"threshold": None, "fbeta": -1.0}
    for t in GRID:
        flagged = real & (conf >= t) & (top != other_idx)
        correct = flagged & (top == y)
        precision = correct.sum() / flagged.sum() if flagged.any() else 0.0
        recall = correct.sum() / misc_truth.sum() if misc_truth.any() else 0.0
        denom = beta * beta * precision + recall
        f = (1 + beta * beta) * precision * recall / denom if denom else 0.0
        if f > best["fbeta"] + 1e-12:
            other_rows = real & (y == other_idx)
            best = {"threshold": t, "fbeta": round(float(f), 4), "precision": round(float(precision), 3),
                    "recall": round(float(recall), 3),
                    "false_alarm": round(float((flagged & other_rows).sum() / max(other_rows.sum(), 1)), 3)}
    return best


def bootstrap_fbeta_threshold(scaled: np.ndarray, y: np.ndarray, cluster: np.ndarray, is_real: np.ndarray,
                              other_idx: int, seed: int, resamples: int = BOOTSTRAP_RESAMPLES) -> list[float]:
    rng = np.random.default_rng(seed)
    clusters = np.unique(cluster)
    by_cluster = {c: np.flatnonzero(cluster == c) for c in clusters}
    draws = []
    for _ in range(resamples):
        picked = rng.choice(clusters, size=len(clusters), replace=True)
        idx = np.concatenate([by_cluster[c] for c in picked])
        t = fbeta_threshold(scaled[idx], y[idx], is_real[idx], other_idx)["threshold"]
        if t is not None:
            draws.append(float(t))
    return draws


def calibrate_variant(
    prob_list: Sequence[np.ndarray], y: np.ndarray, cluster: np.ndarray, is_real: np.ndarray, seed: int,
    other_idx: int | None = None,
) -> dict[str, Any]:
    """Full calibration record for one variant from per-repeat OOF matrices."""
    probs, ys, clusters, real = stack(prob_list, y, cluster, is_real)
    temp = fit_temperature_if_it_helps(probs, ys)
    scaled = rescale(probs, temp["temperature"])
    conf = scaled.max(axis=1)
    correct = scaled.argmax(axis=1) == ys

    point = select_threshold(conf, correct, real, TARGET_PRECISION)
    if other_idx is not None:
        chosen = fbeta_threshold(scaled, ys, real, other_idx)
        point = {"threshold": chosen["threshold"], "population": "non_synthetic", "reached": True}
        draws = bootstrap_fbeta_threshold(scaled, ys, clusters, real, other_idx, seed)
    else:
        chosen = None
        draws = bootstrap_threshold(scaled, ys, clusters, real, TARGET_PRECISION, seed)
    sensitivity = {
        str(t): select_threshold(conf, correct, real, t)["threshold"] for t in SENSITIVITY_TARGETS
    }
    if draws:
        threshold = float(np.round(np.median(draws), 2))
        spread = {"p05": float(np.percentile(draws, 5)), "p50": float(np.median(draws)),
                  "p95": float(np.percentile(draws, 95)), "resamples_reaching_target": len(draws)}
    else:
        threshold = point["threshold"] if point["threshold"] is not None else 0.5
        spread = {"resamples_reaching_target": 0}
    return {
        "temperature": temp["temperature"],
        "threshold": threshold,
        "method": ("grouped out-of-fold predictions, F-beta (0.5) threshold on real rows, cluster bootstrap"
                   if other_idx is not None else
                   "grouped out-of-fold predictions, selective-precision threshold, cluster bootstrap"),
        "criterion": {"name": "fbeta", "beta": FBETA, **chosen} if chosen else
                     {"name": "selective_precision", "target": TARGET_PRECISION},
        "target_precision": TARGET_PRECISION,
        "target_population": point["population"],
        "target_reached_on_full_sample": point["reached"],
        "point_estimate_threshold": point["threshold"],
        "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": seed, **spread},
        "sensitivity_threshold_by_target_precision": sensitivity,
        "temperature_fit": temp,
        "fitted_on": {
            "rows": int(len(y)), "repeats": len(prob_list), "clusters": int(len(np.unique(cluster))),
            "non_synthetic_rows": int(is_real.sum()),
        },
        "ece_after": round(expected_calibration_error(scaled, ys), 4),
        "ece_after_real_rows": round(expected_calibration_error(scaled[real], ys[real]), 4) if real.any() else None,
        "mean_top_probability": {
            "all": round(float(conf.mean()), 3),
            "non_synthetic": round(float(conf[real].mean()), 3) if real.any() else None,
            "synthetic": round(float(conf[~real].mean()), 3) if (~real).any() else None,
        },
        "risk_coverage": risk_coverage(conf, correct, real),
        "caveat": ("precision is agreement with row labels; non-synthetic labels are mostly weak-rule labels, "
                   "and out-of-fold real rows are more familiar than new classrooms"),
        "isotonic_used": False,
        "scope": "one global threshold + temperature per variant",
    }
