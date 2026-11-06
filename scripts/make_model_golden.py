"""Regenerate the golden prediction fixture for the backend classifier test.

`backend/tests/fixtures/model_golden.json` pins what `ModelClassifier` must
return for one real row per class. When the model is retrained, the test
fails on purpose; run this script, read the diff, and commit it with the new
model so the change is reviewed instead of silent.

    python scripts/make_model_golden.py [--variant best]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.diagnosis.xgb_classifier import ModelClassifier  # noqa: E402

FEATURES_CSV = ROOT / "data" / "misconception_dataset" / "features" / "features.csv"
OUT = ROOT / "backend" / "tests" / "fixtures" / "model_golden.json"


def _cell(value: str) -> float | None:
    if value == "" or value.lower() == "nan":
        return None
    return float(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="best")
    args = parser.parse_args(argv)

    model = ModelClassifier.load(args.variant)
    first_per_class: dict[str, dict[str, str]] = {}
    with FEATURES_CSV.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            first_per_class.setdefault(row["label"], row)

    cases = []
    for label in sorted(first_per_class):
        row = first_per_class[label]
        features = {name: _cell(row[name]) for name in model.features}
        pred = model.predict(features)
        cases.append({
            "row_id": row["row_id"],
            "dataset_label": label,
            "features": features,
            "expected": {
                "top_label": pred.top_label,
                "abstained": pred.abstained,
                "probabilities": {k: round(v, 4) for k, v in pred.probabilities.items()},
            },
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({
            "variant": args.variant,
            "model_sha256": model.model_sha256,
            "temperature": model.temperature,
            "threshold": model.threshold,
            "cases": cases,
        }, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"wrote {len(cases)} cases for {args.variant} ({model.model_sha256[:16]}) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
