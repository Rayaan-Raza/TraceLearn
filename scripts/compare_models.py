"""Compare model families on the same data and the same held-out problems.

    wsl python3 scripts/compare_models.py

Train rows: the `train` and `dev_gold` splits. Test rows: every human-labelled row of the
`test` split (whole unseen problems, the set `eval_heldout_rows.py` scores). Nothing is tuned
on the test rows: every model uses fixed, ordinary hyper-parameters, and the abstain rule is a
fixed confidence of 0.6 (the served model's operating point is a different, calibrated one).

Two training sets: `all` (real + synthetic, weighted by label confidence) and `real` (non-
synthetic rows only). Reported on the test rows: accuracy (abstain = miss), false alarm on
OTHER rows, precision when flagged, misconception recall, abstain rate, macro-F1; and the same
without abstaining (argmax). Writes reports/model_comparison.{json,md}.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
OTHER = "CPP_OTHER_ERROR"
THRESHOLD = 0.6


def load():
    labels = {}
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            labels[r["row_id"]] = r
    splits = {r["row_id"]: r for r in csv.DictReader((DS / "splits" / "splits.csv").open(newline="", encoding="utf-8"))}
    rows = []
    with (DS / "features" / "features.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        for rec in reader:
            m = labels[rec[0]]
            rows.append({"id": rec[0], "y": rec[1], "src": m["dataset_source"], "ls": m.get("label_source"),
                         "conf": float(m.get("label_confidence") or 0.6), "split": splits[rec[0]]["split"],
                         "x": [float(v) if v not in ("", "nan", "NaN") else math.nan for v in rec[2:]]})
    return rows, header[2:]


def metrics(truth, pred):
    n = len(truth)
    other = [i for i in range(n) if truth[i] == OTHER]
    mis = [i for i in range(n) if truth[i] != OTHER]
    flagged = [i for i in range(n) if pred[i] not in (OTHER, "ABSTAIN")]
    right = [i for i in flagged if pred[i] == truth[i]]
    classes = sorted(set(truth) | set(p for p in pred if p != "ABSTAIN"))
    f1s = []
    for c in classes:
        tp = sum(1 for i in range(n) if pred[i] == c and truth[i] == c)
        fp = sum(1 for i in range(n) if pred[i] == c and truth[i] != c)
        fn = sum(1 for i in range(n) if truth[i] == c and pred[i] != c)
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0)
    return {"accuracy": round(sum(t == p for t, p in zip(truth, pred)) / n, 3),
            "false_alarm": round(sum(1 for i in other if pred[i] not in (OTHER, "ABSTAIN")) / max(len(other), 1), 3),
            "precision_flagged": round(len(right) / len(flagged), 3) if flagged else None, "n_flagged": len(flagged),
            "recall": round(sum(1 for i in mis if pred[i] == truth[i]) / max(len(mis), 1), 3),
            "abstain": round(sum(p == "ABSTAIN" for p in pred) / n, 3), "macro_f1": round(float(np.mean(f1s)), 3)}


def main() -> int:
    from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier

    rows, names = load()
    featsets = {"best (static+warnings+semantics)": ("static.", "warnings.", "semantics."),
                "best+runtime+tests": ("static.", "warnings.", "semantics.", "runtime.", "tests."),
                "all features": ("",)}
    test = [r for r in rows if r["split"] == "test" and r["ls"] == "human"]
    train_all = [r for r in rows if r["split"] in ("train", "dev_gold")]
    sets = {"all": train_all, "real": [r for r in train_all if r["src"] != "SYNTHETIC"]}
    classes = sorted({r["y"] for r in rows})
    cidx = {c: i for i, c in enumerate(classes)}
    Xte_full = np.array([r["x"] for r in test], dtype=float)
    truth = [r["y"] for r in test]

    def impute(model):
        return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), model)

    zoo = {
        "xgboost": lambda: XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8,
                                         objective="multi:softprob", tree_method="hist", n_jobs=1, verbosity=0, random_state=7),
        "random_forest": lambda: impute(RandomForestClassifier(n_estimators=400, min_samples_leaf=2, class_weight="balanced_subsample", n_jobs=1, random_state=7)),
        "extra_trees": lambda: impute(ExtraTreesClassifier(n_estimators=400, min_samples_leaf=2, class_weight="balanced_subsample", n_jobs=1, random_state=7)),
        "logistic_regression": lambda: impute(make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced"))),
        "knn": lambda: impute(make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=7, weights="distance"))),
        "mlp": lambda: impute(make_pipeline(StandardScaler(), MLPClassifier((64, 32), alpha=1e-2, max_iter=800, random_state=7))),
    }
    report = {"test_rows": len(test), "truth": {c: truth.count(c) for c in sorted(set(truth))}, "threshold": THRESHOLD, "results": {}}
    always = metrics(truth, [OTHER] * len(truth))
    report["results"]["always OTHER"] = {"all": {"abstain_rule": always, "argmax": always}}
    for name, make in zoo.items():
      for fname, prefixes in featsets.items():
        cols = [i for i, f in enumerate(names) if f.startswith(prefixes)]
        Xte = Xte_full[:, cols]
        for sname, tr in sets.items():
            sname_full = f"{sname} | {fname}"
            Xtr = np.array([r["x"] for r in tr], dtype=float)[:, cols]
            ytr_raw = np.array([cidx[r["y"]] for r in tr])
            present = np.unique(ytr_raw)
            ytr = present.searchsorted(ytr_raw)
            w = np.array([r["conf"] for r in tr])
            model = make()
            try:
                if name == "xgboost":
                    model.fit(Xtr, ytr, sample_weight=w)
                else:
                    model.fit(Xtr, ytr)
                proba = model.predict_proba(Xte)
            except Exception as e:  # noqa: BLE001
                print(name, sname_full, "failed:", e)
                continue
            top = proba.argmax(axis=1)
            conf = proba.max(axis=1)
            lab = [classes[int(present[t])] for t in top]
            gated = [l if c >= THRESHOLD else "ABSTAIN" for l, c in zip(lab, conf)]
            report["results"].setdefault(name, {})[sname_full] = {"abstain_rule": metrics(truth, gated), "argmax": metrics(truth, lab)}
            print(name, sname_full, report["results"][name][sname_full]["abstain_rule"], flush=True)
    (DS / "reports" / "model_comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Model families on the held-out problems", "", f"{len(test)} rows, unseen problems; fixed hyper-parameters; abstain below {THRESHOLD}.", "",
             "| Model | Train set | Mode | Accuracy | False alarm | Precision flagged (n) | Recall | Abstain | Macro-F1 |", "|---|---|---|---|---|---|---|---|---|"]
    for name, d in report["results"].items():
        for sname, modes in d.items():
            for mode, m in modes.items():
                lines.append(f"| {name} | {sname} | {mode} | {m['accuracy']} | {m['false_alarm']} | {m['precision_flagged']} ({m['n_flagged']}) | {m['recall']} | {m['abstain']} | {m['macro_f1']} |")
    (DS / "reports" / "model_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
