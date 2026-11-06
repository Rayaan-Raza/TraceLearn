"""Baselines and evidence-source ablations on the training pool (blueprint §9.5, §15.2).

    python scripts/eval_baselines.py [--cv-repeats 3] [--seed 7]

Everything runs on the same grouped folds as the trainer (StratifiedGroupKFold
by problem cluster, train rows only; dev-gold is never inside a fold). It
answers two questions the panel will ask:

1. Does XGBoost beat transparent baselines (majority, logistic regression)?
2. Which evidence blocks carry signal (static, warnings, semantics, tests,
   runtime, cpg, context), alone and removed one at a time?

The numbers are cross-validation on a pool that is mostly synthetic by
weight, so they rank methods against each other; they are not an estimate of
accuracy on real student code (see docs/6-nov.md §9).

Writes reports/baselines.json and reports/baselines.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import train_xgb_misconception as trainer  # noqa: E402

DATASET_DIR = trainer.DEFAULT_DATASET_DIR
BLOCKS = ("static", "warnings", "semantics", "tests", "runtime", "cpg", "context")


def load_training_pool(ds: Path) -> dict[str, Any]:
    """Train + dev-gold rows exactly as the trainer sees them."""
    import pandas as pd

    meta_by_rid: dict[str, dict] = {}
    with (ds / "annotations" / "labels.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                meta_by_rid[row["row_id"]] = row
    splits = {}
    with (ds / "splits" / "splits.csv").open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            splits[rec["row_id"]] = (rec["cluster_id"], rec["split"])

    rids, labels, rows = [], [], []
    with (ds / "features" / "features.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        features = header[2:]
        for rec in reader:
            if splits[rec[0]][1] not in ("train", "dev_gold"):
                continue
            rids.append(rec[0])
            labels.append(rec[1])
            rows.append([float(v) if v not in ("", "nan", "NaN") else math.nan for v in rec[2:]])
    classes = sorted(set(labels))
    y = np.array([classes.index(s) for s in labels])
    split = np.array([splits[r][1] for r in rids])
    meta = pd.DataFrame({
        "label": [meta_by_rid[r]["label"] for r in rids],
        "label_confidence": [float(meta_by_rid[r].get("label_confidence") or 0.6) for r in rids],
        "dataset_source": [meta_by_rid[r]["dataset_source"] for r in rids],
    })
    return {
        "features": features, "X": np.array(rows, dtype=float), "y": y, "classes": classes,
        "cluster": np.array([splits[r][0] for r in rids]), "split": split, "meta": meta,
        "source": np.array(meta["dataset_source"]),
    }


def columns_for(features: list[str], blocks: tuple[str, ...]) -> list[int]:
    return [i for i, name in enumerate(features) if name.split(".", 1)[0] in blocks]


def folds(y, cluster, seed: int, repeats: int, n_splits: int = 3):
    from sklearn.model_selection import StratifiedGroupKFold

    for rep in range(repeats):
        cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed + rep)
        for tr, va in cv.split(np.zeros(len(y)), y, cluster):
            yield rep, tr, va


def _logreg():
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(max_iter=3000, C=0.5, class_weight="balanced"),
    )


def evaluate(pool: dict[str, Any], cols: list[int], kind: str, seed: int, repeats: int) -> dict[str, Any]:
    X, y, k = pool["X"], pool["y"], len(pool["classes"])
    train_idx = np.flatnonzero(pool["split"] == "train")
    Xt, yt, ct = X[train_idx], y[train_idx], pool["cluster"][train_idx]
    meta = pool["meta"].iloc[train_idx].reset_index(drop=True)
    all_classes = list(range(k))
    fold_scores: list[float] = []
    real_scores: list[float] = []
    oof = [np.full(len(yt), -1) for _ in range(repeats)]
    src = pool["source"][train_idx]
    for rep, tr, va in folds(yt, ct, seed, repeats):
        if kind == "majority":
            pred = np.full(len(va), np.bincount(yt[tr], minlength=k).argmax())
        elif kind == "logreg":
            model = _logreg().fit(Xt[tr][:, cols], yt[tr])
            pred = np.asarray(model.classes_)[model.predict_proba(Xt[va][:, cols]).argmax(axis=1)]
        else:
            w, _ = trainer.compute_weights(meta.iloc[tr].reset_index(drop=True), 1.0)
            proba = trainer._fit_predict(Xt[tr][:, cols], yt[tr], w, Xt[va][:, cols], seed + rep, k)
            pred = proba.argmax(axis=1)
        oof[rep][va] = pred
        present = sorted(set(yt[va].tolist()))
        fold_scores.append(trainer.macro_f1(yt[va], pred, present))
        real = src[va] != "SYNTHETIC"
        if real.sum() >= 10:
            rp = sorted(set(yt[va][real].tolist()))
            real_scores.append(trainer.macro_f1(yt[va][real], pred[real], rp))
    oof_f1 = float(np.mean([trainer.macro_f1(yt, o, all_classes) for o in oof]))
    return {
        "cv_macro_f1_mean": round(float(np.mean(fold_scores)), 4),
        "cv_macro_f1_std": round(float(np.std(fold_scores)), 4),
        "oof_macro_f1": round(oof_f1, 4),
        "cv_macro_f1_real_rows_only": round(float(np.mean(real_scores)), 4) if real_scores else None,
        "n_features": len(cols),
    }


SHORTCUT_LIMIT = 0.90   # master plan R4: source predictable from missingness alone above this -> forced fallback


def source_shortcut(pool: dict[str, Any], seed: int) -> dict[str, Any]:
    """Can the dataset source (or the class) be read off which features are missing?

    Uses only the NaN pattern of each variant's columns, grouped CV by cluster.
    A high source accuracy means a model could learn "which lane produced this
    row" instead of the misconception (master plan R4 source-shortcut test).
    """
    from sklearn.ensemble import RandomForestClassifier

    train_idx = np.flatnonzero(pool["split"] == "train")
    sources = sorted(set(pool["source"]))
    s_idx = np.array([sources.index(s) for s in pool["source"]])
    out: dict[str, Any] = {}
    for name, blocks in (("full", BLOCKS), ("best", ("static", "warnings", "semantics")),
                         ("common", ("static", "warnings"))):
        mask = np.isnan(pool["X"][:, columns_for(pool["features"], blocks)]).astype(float)[train_idx]
        scores: dict[str, float] = {}
        for target_name, target in (("source", s_idx[train_idx]), ("class", pool["y"][train_idx])):
            accs = []
            for _, tr, va in folds(target, pool["cluster"][train_idx], seed, 1):
                rf = RandomForestClassifier(200, random_state=seed, n_jobs=1).fit(mask[tr], target[tr])
                accs.append(float((rf.predict(mask[va]) == target[va]).mean()))
            scores[target_name] = round(float(np.mean(accs)), 3)
        majority = {t: round(float(np.bincount(v).max() / len(v)), 3)
                    for t, v in (("source", s_idx[train_idx]), ("class", pool["y"][train_idx]))}
        out[name] = {
            "source_from_missingness": scores["source"], "source_majority": majority["source"],
            "class_from_missingness": scores["class"], "class_majority": majority["class"],
            "passes_r4": scores["source"] <= SHORTCUT_LIMIT,
        }
        print(f"shortcut {name:7s} source {scores['source']:.3f} (majority {majority['source']:.3f})"
              f"  class {scores['class']:.3f} (majority {majority['class']:.3f})"
              f"  R4 {'pass' if out[name]['passes_r4'] else 'FAIL -> common-feature variant forced'}")
    return out


def run(ds: Path, seed: int, repeats: int) -> dict[str, Any]:
    pool = load_training_pool(ds)
    feats = pool["features"]
    results: dict[str, Any] = {}

    def add(name: str, kind: str, blocks: tuple[str, ...]) -> None:
        cols = columns_for(feats, blocks)
        results[name] = {"kind": kind, "blocks": list(blocks), **evaluate(pool, cols, kind, seed, repeats)}
        print(f"{name:34s} {results[name]['cv_macro_f1_mean']:.3f} +/- {results[name]['cv_macro_f1_std']:.3f}"
              f"  real-only {results[name]['cv_macro_f1_real_rows_only']}")

    add("majority", "majority", BLOCKS)
    add("logreg: static+warnings", "logreg", ("static", "warnings"))
    add("logreg: best (+semantics)", "logreg", ("static", "warnings", "semantics"))
    add("logreg: all", "logreg", BLOCKS)
    add("xgb: all", "xgb", BLOCKS)
    add("xgb: best (static+warn+sem)", "xgb", ("static", "warnings", "semantics"))
    add("xgb: common (static+warn)", "xgb", ("static", "warnings"))
    for block in BLOCKS:
        add(f"xgb: only {block}", "xgb", (block,))
    for block in BLOCKS:
        add(f"xgb: all minus {block}", "xgb", tuple(b for b in BLOCKS if b != block))
    return {
        "seed": seed, "cv_repeats": repeats, "n_train_rows": int((pool["split"] == "train").sum()),
        "protocol": "StratifiedGroupKFold(3) by problem cluster, train rows only, same weights as the trainer",
        "caveat": "cross-validation on a mostly synthetic pool; ranks methods, does not estimate real-student accuracy",
        "source_shortcut": source_shortcut(pool, seed),
        "results": results,
    }


def write_reports(out: dict[str, Any], ds: Path) -> None:
    reports = ds / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "baselines.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = [
        "# Baselines and evidence ablations", "",
        "Generated by `scripts/eval_baselines.py`. Do not edit by hand.", "",
        f"- Protocol: {out['protocol']}",
        f"- Train rows: {out['n_train_rows']} · repeats: {out['cv_repeats']} · seed: {out['seed']}",
        f"- Caveat: {out['caveat']}", "",
        "| Model | Blocks | Features | CV macro-F1 | OOF macro-F1 | Real-rows-only F1 |",
        "|---|---|---:|---|---:|---:|",
    ]
    for name, r in out["results"].items():
        real = "" if r["cv_macro_f1_real_rows_only"] is None else f"{r['cv_macro_f1_real_rows_only']:.3f}"
        lines.append(
            f"| {name} | {', '.join(r['blocks'])} | {r['n_features']} | "
            f"{r['cv_macro_f1_mean']:.3f} ± {r['cv_macro_f1_std']:.3f} | {r['oof_macro_f1']:.3f} | {real} |"
        )
    lines += [
        "", "## Source-shortcut test (master plan R4)", "",
        f"Source predicted from the NaN pattern alone; above {SHORTCUT_LIMIT:.0%} the common-feature variant is forced.", "",
        "| Variant | Source from missingness | Source majority | Class from missingness | Class majority | R4 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, r in out["source_shortcut"].items():
        lines.append(
            f"| {name} | {r['source_from_missingness']:.3f} | {r['source_majority']:.3f} | "
            f"{r['class_from_missingness']:.3f} | {r['class_majority']:.3f} | {'pass' if r['passes_r4'] else 'FAIL'} |"
        )
    (reports / "baselines.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--cv-repeats", type=int, default=3)
    args = ap.parse_args(argv)
    out = run(args.dataset_dir, args.seed, args.cv_repeats)
    write_reports(out, args.dataset_dir)
    print("wrote reports/baselines.json and reports/baselines.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
