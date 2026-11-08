"""How much each served model variant loses when feature blocks are missing at inference.

    python scripts/variant_skew_check.py

Feeds the runtime-features decision (docs/decisions/inference_runtime_features.md).
For the held-out pools (dev_gold, test_iid) it scores, with the trained boosters:

* ``full`` with every block it was trained on;
* ``full`` with ``runtime`` set to NaN (no sandbox_runner at inference), then
  also ``cpg``, then also ``tests`` (blocks the live path may not compute
  with training parity);
* the ``best`` (static + warnings + semantics) and ``common`` (static + warnings)
  variants, which need none of those blocks.

Scores are macro-F1 over the classes present, on the pools' **current labels**
(most are still weak labels until the sheets are signed), so read them as the
direction and size of the loss, not as accuracy. Writes
``reports/inference_variant_skew.json``.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "reports" / "inference_variant_skew.json"
FILES = {"full": "xgb_v1.json", "common": "xgb_common_v1.json", "best": "xgb_best_v1.json"}
SCENARIOS = [
    ("full", ()), ("full", ("runtime",)), ("full", ("runtime", "cpg")), ("full", ("runtime", "cpg", "tests")),
    ("best", ()), ("common", ()),
]


def macro_f1(truth: list[str], pred: list[str]) -> float:
    scores = []
    for c in set(truth):
        tp = sum(t == c and p == c for t, p in zip(truth, pred))
        fp = sum(t != c and p == c for t, p in zip(truth, pred))
        fn = sum(t == c and p != c for t, p in zip(truth, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return round(sum(scores) / len(scores), 3) if scores else float("nan")


def main() -> int:
    import xgboost as xgb
    metrics = json.loads((DS / "models" / "metrics_v1.json").read_text(encoding="utf-8"))
    classes = json.loads((DS / "models" / "label_encoder.json").read_text(encoding="utf-8"))["idx_to_class"]
    splits = {r["row_id"]: r["split"] for r in csv.DictReader(open(DS / "splits" / "splits.csv", encoding="utf-8"))}
    labels = {}
    for line in open(DS / "annotations" / "labels.jsonl", encoding="utf-8"):
        r = json.loads(line)
        labels[r["row_id"]] = r
    with open(DS / "features" / "features.csv", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        feats = next(reader)[2:]
        data = {rec[0]: rec for rec in reader}

    def num(v: str) -> float:
        return float(v) if v not in ("", "nan", "NaN") else math.nan

    boosters = {}
    for var, fname in FILES.items():
        b = xgb.Booster()
        b.load_model(str(DS / "models" / fname))
        boosters[var] = b

    def predict(var: str, rids: list[str], blank: tuple[str, ...]) -> list[str]:
        use = metrics[var].get("features") or feats
        X = np.array([[math.nan if c.split(".")[0] in blank else num(data[r][feats.index(c) + 2]) for c in use]
                      for r in rids], dtype=float)
        return [classes[i] for i in boosters[var].predict(xgb.DMatrix(X, missing=math.nan)).argmax(axis=1)]

    report = {"note": "macro-F1 on current labels (mostly weak); direction and size of loss, not accuracy",
              "cv_macro_f1": {v: metrics[v].get("cv_macro_f1_mean") for v in FILES},
              "blocks": {v: dict(Counter(c.split(".")[0] for c in (metrics[v].get("features") or feats)))
                         for v in FILES},
              "pools": {}}
    for split in ("dev_gold", "test_iid"):
        rids = [r for r, s in splits.items() if s == split and r in data]
        truth = [labels[r]["label"] for r in rids]
        rows = {}
        for var, blank in SCENARIOS:
            name = var + (" without " + " + ".join(blank) if blank else "")
            rows[name] = macro_f1(truth, predict(var, rids, blank))
        same = sum(a == b for a, b in zip(predict("full", rids, ()), predict("full", rids, ("runtime",))))
        report["pools"][split] = {"n": len(rids), "sources": dict(Counter(labels[r]["dataset_source"] for r in rids)),
                                  "label_sources": dict(Counter(labels[r]["label_source"] for r in rids)),
                                  "macro_f1": rows, "full_top_label_unchanged_without_runtime": f"{same}/{len(rids)}"}
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
