"""How different is unseen real student code from the training rows? (master plan G3c)

    python scripts/eval_shift.py [--unseen dev_gold]

Adversarial validation: a forest tries to tell training rows from unseen real
submissions using only the features a served variant sees. AUC 0.5 means the two
look alike; above 0.85 the model is being asked to work on a different
population (plan: < 0.75 pass, > 0.85 fail). The same test is run against the
real-only training rows, and per feature block, to say WHERE the gap is. Single
features are ranked by how well each alone separates the two groups.

Inputs: data/misconception_dataset/features/features.csv (training rows) and the
gitignored dump written by `eval_real_data.py --features-only`. Writes
reports/shift_<pool>.json / .md. This measures resemblance, not correctness: a
small gap does not make the labels right.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DATASET_DIR = ROOT / "data" / "misconception_dataset"
BLOCKS = ("static", "warnings", "semantics", "tests", "runtime", "cpg", "context")
VARIANT_BLOCKS = {"best": ("static", "warnings", "semantics"), "common": ("static", "warnings")}
PASS_AUC, FAIL_AUC = 0.75, 0.85


def _num(value: str) -> float:
    if value in ("", "nan", "NaN"):
        return math.nan
    try:
        return float(value)
    except ValueError:
        return math.nan


def load_matrix(path: Path, feature_names: Sequence[str], keep=None) -> tuple[np.ndarray, list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if keep is None or keep(r)]
    X = np.array([[_num(r[n]) for n in feature_names] for r in rows], dtype=float)
    return X, rows


def columns_for(names: Sequence[str], blocks: Sequence[str]) -> list[int]:
    return [i for i, n in enumerate(names) if n.split(".", 1)[0] in blocks]


def adversarial_auc(
    Xa: np.ndarray, Xb: np.ndarray, groups_a: np.ndarray, groups_b: np.ndarray, seed: int = 7, folds: int = 4,
) -> dict[str, float]:
    """AUC of telling group A from group B, cross-validated with whole problems held out."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedGroupKFold

    X = np.vstack([Xa, Xb])
    y = np.r_[np.zeros(len(Xa)), np.ones(len(Xb))]
    groups = np.r_[groups_a, groups_b]
    X = SimpleImputer(strategy="median", keep_empty_features=True, add_indicator=True).fit_transform(X)
    scores = np.zeros(len(y))
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    for tr, va in cv.split(X, y, groups):
        # balance the two groups so AUC is not driven by their sizes
        model = RandomForestClassifier(300, random_state=seed, n_jobs=1, class_weight="balanced_subsample",
                                       min_samples_leaf=3).fit(X[tr], y[tr])
        scores[va] = model.predict_proba(X[va])[:, 1]
    return {"auc": round(float(roc_auc_score(y, scores)), 3), "n_a": len(Xa), "n_b": len(Xb)}


def single_feature_separation(Xa: np.ndarray, Xb: np.ndarray, names: Sequence[str], top: int = 12) -> list[dict[str, Any]]:
    """Per-feature AUC of A-vs-B (0.5 = identical); reported as distance from 0.5."""
    from sklearn.metrics import roc_auc_score

    y = np.r_[np.zeros(len(Xa)), np.ones(len(Xb))]
    out = []
    for j, name in enumerate(names):
        col = np.r_[Xa[:, j], Xb[:, j]]
        ok = ~np.isnan(col)
        if ok.sum() < 20 or len(set(y[ok])) < 2 or np.nanstd(col) == 0:
            continue
        auc = float(roc_auc_score(y[ok], col[ok]))
        out.append({"feature": name, "auc": round(auc, 3), "distance": round(abs(auc - 0.5), 3),
                    "median_train": round(float(np.nanmedian(Xa[:, j])), 3) if (~np.isnan(Xa[:, j])).any() else None,
                    "median_unseen": round(float(np.nanmedian(Xb[:, j])), 3) if (~np.isnan(Xb[:, j])).any() else None})
    return sorted(out, key=lambda r: -r["distance"])[:top]


def verdict(auc: float) -> str:
    return "pass" if auc < PASS_AUC else ("FAIL" if auc > FAIL_AUC else "warn")


def run(unseen_pool: str, ds: Path = DATASET_DIR) -> dict[str, Any]:
    from tracelearn_features.schema import feature_names

    names = list(feature_names())
    splits = {r["row_id"]: r for r in csv.DictReader((ds / "splits" / "splits.csv").open(encoding="utf-8", newline=""))}
    train_all, train_rows = load_matrix(
        ds / "features" / "features.csv", names, keep=lambda r: splits[r["row_id"]]["split"] == "train")
    g_train = np.array([splits[r["row_id"]]["cluster_id"] for r in train_rows])
    real_mask = np.array([not r["row_id"].startswith("mut-") for r in train_rows])

    dump = ds / "cache" / f"real_eval_features_{unseen_pool}.csv"
    unseen, unseen_rows = load_matrix(dump, names, keep=lambda r: r["branch"] == "failing")
    g_unseen = np.array([r["cluster"] for r in unseen_rows])

    out: dict[str, Any] = {
        "unseen_pool": unseen_pool, "n_train": len(train_rows), "n_train_real": int(real_mask.sum()),
        "n_unseen_failing": len(unseen_rows), "limits": "resemblance only; a small gap does not make labels right",
        "adversarial": {},
    }
    for variant, blocks in VARIANT_BLOCKS.items():
        cols = columns_for(names, blocks)
        out["adversarial"][variant] = {
            "train_vs_unseen": adversarial_auc(train_all[:, cols], unseen[:, cols], g_train, g_unseen),
            "real_train_vs_unseen": adversarial_auc(train_all[real_mask][:, cols], unseen[:, cols],
                                                    g_train[real_mask], g_unseen),
        }
        for k in ("train_vs_unseen", "real_train_vs_unseen"):
            out["adversarial"][variant][k]["gate"] = verdict(out["adversarial"][variant][k]["auc"])
    out["per_block_real_train_vs_unseen"] = {}
    for block in BLOCKS:
        cols = columns_for(names, (block,))
        out["per_block_real_train_vs_unseen"][block] = adversarial_auc(
            train_all[real_mask][:, cols], unseen[:, cols], g_train[real_mask], g_unseen)["auc"]
    served = columns_for(names, VARIANT_BLOCKS["best"])
    out["top_separating_features_best"] = single_feature_separation(
        train_all[real_mask][:, served], unseen[:, served], [names[i] for i in served])
    return out


def render(rep: dict[str, Any]) -> str:
    lines = [
        f"# Shift between training rows and unseen real code (`{rep['unseen_pool']}` clusters)", "",
        "Generated by `scripts/eval_shift.py`. Do not edit by hand.", "",
        f"- Training rows: {rep['n_train']} ({rep['n_train_real']} non-synthetic) · unseen failing submissions: "
        f"{rep['n_unseen_failing']}",
        f"- Gate (master plan G3c): AUC < {PASS_AUC} pass, > {FAIL_AUC} fail. {rep['limits']}.", "",
        "| Variant | All training vs unseen | Real-only training vs unseen |", "|---|---|---|",
    ]
    for v, r in rep["adversarial"].items():
        a, b = r["train_vs_unseen"], r["real_train_vs_unseen"]
        lines.append(f"| {v} | {a['auc']} ({a['gate']}) | {b['auc']} ({b['gate']}) |")
    lines += ["", "AUC per block (real-only training vs unseen): " +
              ", ".join(f"{k} {v}" for k, v in rep["per_block_real_train_vs_unseen"].items()), "",
              "| Feature (best variant) | Single-feature AUC | Median in training (real) | Median unseen |", "|---|---:|---:|---:|"]
    for f in rep["top_separating_features_best"]:
        lines.append(f"| {f['feature']} | {f['auc']} | {f['median_train']} | {f['median_unseen']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--unseen", default="dev_gold", choices=("dev_gold", "test"))
    args = ap.parse_args(argv)
    rep = run(args.unseen)
    reports = DATASET_DIR / "reports"
    (reports / f"shift_{args.unseen}.json").write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8", newline="\n")
    (reports / f"shift_{args.unseen}.md").write_text(render(rep), encoding="utf-8", newline="\n")
    print(render(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
