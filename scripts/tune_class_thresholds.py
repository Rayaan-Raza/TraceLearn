"""Per-class decision bars for a served variant, tuned on the training problems only.

    python scripts/tune_class_thresholds.py [--variant execution] [--write]

Why: OTHER_ERROR is about three quarters of the real training rows, so a misconception is often
the model's second guess behind OTHER_ERROR. A class with its own bar is reported when its
probability clears that bar, even when OTHER_ERROR is more probable (`decide` in
backend/app/diagnosis/xgb_classifier.py).

How: grouped out-of-fold probabilities over the TRAIN split (3 folds by problem cluster, 3
repeats, the served profile and row selection), temperature-scaled and passed through the
applicability rules like a live prediction. Classes are visited in order; a bar is kept only if,
on the real out-of-fold rows and with the repair-first rule applied, the class reaches precision
0.5, its F1 rises by more than 0.01 and macro-F1 does not fall. The held-out test split is never
read. The master plan (section 11) allows one global threshold because dev-gold has about five
rows per class; these bars are fitted on the ~1,300 out-of-fold training rows instead, which is
a recorded deviation (docs/MODEL_LOG.md, 2026-11-14).

Without --write it prints the bars and changes nothing.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import train_xgb_misconception as T  # noqa: E402

from backend.app.diagnosis.applicability import move_ruled_out_mass, ruled_out  # noqa: E402
from backend.app.diagnosis.xgb_classifier import (  # noqa: E402
    OTHER_LABEL,
    ModelClassifier,
    decide,
    rescale,
    rule_override,
)

DS = ROOT / "data" / "misconception_dataset"
GRID = [round(0.05 * i, 2) for i in range(1, 13)]
MIN_PRECISION, MIN_GAIN, MIN_SUPPORT = 0.5, 0.01, 5


def f1_of(pairs: list[tuple[str | None, str]], cls: str) -> tuple[float, float, float, int]:
    tp = sum(a == cls and b == cls for a, b in pairs)
    fp = sum(a == cls and b != cls for a, b in pairs)
    fn = sum(b == cls and a != cls for a, b in pairs)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return prec, rec, (2 * prec * rec / (prec + rec) if prec + rec else 0.0), tp + fn


def macro_f1(pairs: list[tuple[str | None, str]]) -> float:
    return float(np.mean([f1_of(pairs, c)[2] for c in sorted({b for _, b in pairs})]))


def system_label(probs: np.ndarray, features: dict, classes: list[str], threshold: float,
                 bars: dict[str, float]) -> str | None:
    """Repair-first rule, then the model with its bars; None when it abstains."""
    override = rule_override(features)
    if override:
        return override
    idx, abstained = decide(probs, classes, threshold, bars)
    return None if abstained else classes[idx]


def oof_rows(model: ModelClassifier, profile: str, folds: int = 3, repeats: int = 3, seed: int = 7):
    """(row ids, labels, feature dicts, is_real, calibrated out-of-fold probabilities) for the TRAIN split."""
    import pandas as pd
    from sklearn.model_selection import StratifiedGroupKFold

    T.set_profile(profile)
    meta = {}
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            meta[r["row_id"]] = r
    with (DS / "splits" / "splits.csv").open(newline="", encoding="utf-8") as fh:
        split = {r["row_id"]: (r["cluster_id"], r["split"]) for r in csv.DictReader(fh)}
    rows = []
    with (DS / "features" / "features.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        col = {f: i for i, f in enumerate(header)}
        for rec in reader:
            rid, m = rec[0], meta[rec[0]]
            if split[rid][1] != "train":
                continue
            synthetic = m["dataset_source"] == "SYNTHETIC"
            if profile in T.PLAIN_FAMILY and not T.plain_row_selected(rid, m):
                continue
            feats = {f: (float(rec[col[f]]) if rec[col[f]] not in ("", "nan", "NaN") else math.nan) for f in header[2:]}
            rows.append((rid, rec[1], feats, not synthetic))
    classes = model.classes
    X = np.array([[r[2][f] for f in model.features] for r in rows])
    y = np.array([classes.index(r[1]) for r in rows])
    groups = np.array([split[r[0]][0] for r in rows])
    frame = pd.DataFrame({
        "label": [meta[r[0]]["label"] for r in rows],
        "label_confidence": [float(meta[r[0]].get("label_confidence") or 0.6) for r in rows],
        "dataset_source": [meta[r[0]]["dataset_source"] for r in rows],
    })
    total = np.zeros((len(rows), len(classes)))
    count = np.zeros(len(rows))
    for rep in range(repeats):
        for tr, va in StratifiedGroupKFold(folds, shuffle=True, random_state=seed + rep).split(X, y, groups):
            w, _ = T.compute_weights(frame.iloc[tr].reset_index(drop=True), 1.0)
            total[va] += T._fit_predict(X[tr], y[tr], w, X[va], seed, len(classes))
            count[va] += 1
    probs = rescale(total / count[:, None], model.temperature)
    for i, r in enumerate(rows):
        out = ruled_out({k: (None if math.isnan(v) else v) for k, v in r[2].items()})
        probs[i] = move_ruled_out_mass(probs[i], classes, out)
    return rows, probs


def tune(rows, probs, classes: list[str], threshold: float) -> tuple[dict[str, float], dict]:
    real = [i for i, r in enumerate(rows) if r[3]]

    def pairs_for(bars: dict[str, float]):
        return [(system_label(probs[i], rows[i][2], classes, threshold, bars), rows[i][1]) for i in real]

    bars: dict[str, float] = {}
    for cls in classes:
        if cls == OTHER_LABEL:
            continue
        base = pairs_for(bars)
        if f1_of(base, cls)[3] < MIN_SUPPORT:
            continue
        best_f1, best_bar, base_macro = f1_of(base, cls)[2], None, macro_f1(base)
        for bar in GRID:
            trial = pairs_for({**bars, cls: bar})
            prec, _, f1, _ = f1_of(trial, cls)
            if prec >= MIN_PRECISION and f1 > best_f1 + MIN_GAIN and macro_f1(trial) >= base_macro:
                best_f1, best_bar = f1, bar
        if best_bar is not None:
            bars[cls] = best_bar
    before, after = pairs_for({}), pairs_for(bars)
    report = {
        "method": "grouped out-of-fold on the train split (3 folds by problem cluster x 3 repeats), "
                  "repair-first rule applied, real rows only; greedy per class",
        "criterion": {"min_precision": MIN_PRECISION, "min_f1_gain": MIN_GAIN, "macro_f1_must_not_fall": True},
        "real_rows": len(real),
        "macro_f1_oof": {"global_threshold": round(macro_f1(before), 4), "with_class_thresholds": round(macro_f1(after), 4)},
        "per_class_f1_oof": {c: [round(f1_of(before, c)[2], 3), round(f1_of(after, c)[2], 3)] for c in bars},
    }
    return bars, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="execution")
    ap.add_argument("--models-dir", default=str(DS / "models"))
    ap.add_argument("--write", action="store_true", help="store the bars in calibrator.json")
    args = ap.parse_args(argv)

    models = Path(args.models_dir)
    model = ModelClassifier.load(args.variant, models)
    profile = (json.loads((models / "metrics_v1.json").read_text(encoding="utf-8")).get("profile") or {}).get("name", "default")
    rows, probs = oof_rows(model, profile)
    bars, report = tune(rows, probs, model.classes, model.threshold)
    print(json.dumps({"class_thresholds": bars, **report}, indent=2))
    if args.write:
        path = models / "calibrator.json"
        cal = json.loads(path.read_text(encoding="utf-8"))
        entry = cal.setdefault("variants", {}).setdefault(args.variant, {})
        entry["class_thresholds"] = bars
        entry["class_thresholds_fit"] = report
        path.write_text(json.dumps(cal, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
