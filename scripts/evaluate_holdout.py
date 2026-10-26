"""Evaluate a trained model on a held-out split (``test`` or ``test_iid``).

    python scripts/evaluate_holdout.py --split test_iid [--variant full|best] [--confirm-one-shot]

Only rows whose label is *certain* are scored: human, repair_verified and
execution-verified synthetic (Layer 4). Silver weak-rule rows are reported
but never scored, because a weak label is not ground truth.

Test discipline (§13.7): every evaluation is appended to
``reports/holdout_evaluations.jsonl`` with its time, model hash and score,
so the number of times a held-out split was looked at is on record. The
``test`` split additionally needs ``--confirm-one-shot``.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
CERTAIN = {"human", "repair_verified", "synthetic"}


def macro_f1(y_true: list[str], y_pred: list[str], labels: list[str]) -> tuple[float, dict]:
    per = {}
    for c in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        per[c] = {"precision": round(prec, 4), "recall": round(rec, 4),
                  "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
                  "support": sum(1 for t in y_true if t == c)}
    present = [c for c in labels if per[c]["support"] > 0]
    score = sum(per[c]["f1"] for c in present) / len(present) if present else float("nan")
    return round(score, 4), per


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["test", "test_iid"])
    ap.add_argument("--variant", default="full", choices=["full", "best"])
    ap.add_argument("--dataset-dir", type=Path, default=DS)
    ap.add_argument("--confirm-one-shot", action="store_true")
    a = ap.parse_args(argv)
    ds = a.dataset_dir
    if a.split == "test" and not a.confirm_one_shot:
        print("REFUSED: the CodeStream test split is evaluated once (§13.7); rerun with --confirm-one-shot")
        return 2

    import xgboost as xgb

    models = ds / "models"
    enc = json.loads((models / "label_encoder.json").read_text(encoding="utf-8"))
    classes = enc["idx_to_class"]
    metrics = json.loads((models / "metrics_v1.json").read_text(encoding="utf-8"))
    model_path = models / ("xgb_v1.json" if a.variant == "full" else "xgb_best_v1.json")
    booster = xgb.Booster()
    booster.load_model(str(model_path))
    calib = json.loads((models / "calibrator.json").read_text(encoding="utf-8"))

    with open(ds / "features" / "features.csv", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        feats = header[2:]
        data = {rec[0]: rec for rec in reader}
    use = metrics[a.variant]["features"] if a.variant == "best" else feats
    col = [feats.index(c) + 2 for c in use]
    splits = {r["row_id"]: r["split"] for r in csv.DictReader(open(ds / "splits" / "splits.csv", encoding="utf-8"))}
    labels = {}
    for line in open(ds / "annotations" / "labels.jsonl", encoding="utf-8"):
        r = json.loads(line)
        labels[r["row_id"]] = r
    rids = [rid for rid, s in splits.items() if s == a.split and rid in data]
    certain = [rid for rid in rids if labels[rid].get("label_source") in CERTAIN]
    silver = Counter(labels[rid].get("label_source") for rid in rids if rid not in certain)
    if not certain:
        print(f"{a.split}: {len(rids)} rows, none with a certain label yet "
              f"(label sources: {dict(Counter(labels[r].get('label_source') for r in rids))}) — "
              "sign off the pre-review sheets first")
        return 1

    def num(v):
        return float(v) if v not in ("", "nan", "NaN") else math.nan
    X = np.array([[num(data[rid][i]) for i in col] for rid in certain], dtype=float)
    probs = booster.predict(xgb.DMatrix(X, missing=math.nan))
    if probs.shape[1] != len(classes):
        raise SystemExit(f"model has {probs.shape[1]} outputs, encoder lists {len(classes)} classes")
    t = float(calib.get("temperature") or 1.0)
    logits = np.log(np.clip(probs, 1e-12, 1.0)) / t
    scaled = np.exp(logits - logits.max(axis=1, keepdims=True))
    scaled /= scaled.sum(axis=1, keepdims=True)
    pred = [classes[i] for i in scaled.argmax(axis=1)]
    truth = [labels[rid]["label"] for rid in certain]
    score, per = macro_f1(truth, pred, classes)
    acc = sum(p == t_ for p, t_ in zip(pred, truth)) / len(truth)
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()[:16]
    rec = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "split": a.split,
           "variant": a.variant, "model_sha256_16": model_hash, "n_scored": len(certain),
           "n_silver_not_scored": dict(silver), "macro_f1_present_classes": score,
           "accuracy": round(acc, 4), "per_class": per}
    log = ds / "reports" / "holdout_evaluations.jsonl"
    with open(log, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec) + "\n")
    n_prev = sum(1 for line in open(log, encoding="utf-8")
                 if json.loads(line)["split"] == a.split) - 1
    print(json.dumps(rec, indent=1))
    print(f"(this split has been evaluated {n_prev} time(s) before)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
