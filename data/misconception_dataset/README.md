# TraceLearn Misconception Dataset

**Taxonomy:** `tl-cpp-v2` · **Schema:** `1.1` · **Version:** `0.4` · **Status:** active

11-class C++ misconception classifier dataset. See [DATASET_CARD.md](DATASET_CARD.md) for full provenance, splits, model performance, and limitations.

## Quick start

```bash
# Train XGBoost classifier (3-repeat CV)
python scripts/train_xgb_misconception.py --cv-repeats 3

# Re-merge after annotation updates
python scripts/merge_dataset.py   # requires submissions.csv on Rayaan's machine

# Expand synthetic mutants (needs Kali WSL + g++)
python scripts/expand_mutants.py --raw-root /path/to/Datasets_RAW
```

## Current model (v0.4)

| Variant | OOF macro-F1 | CV macro-F1 |
|---------|-------------|-------------|
| best (`static + warnings + semantics`) | 0.757 | 0.704 ± 0.048 |
| common (`static + warnings`) | 0.754 | — |
| full (all 90 features) | 0.729 | — |

Majority baseline: 0.053. G8: 3/4 PASS (synthetic mass 0.59 > 0.50 cap — structural, not tunable).

## Layout

```
data/misconception_dataset/
├── README.md
├── DATASET_CARD.md           (v0.4 — filled)
├── ANNOTATION_GUIDELINE.md
├── HOURS_LOG.md
├── raw_recovery/
│   └── recovery_manifest.json
├── fixtures/                 (unit-test fixtures per lane)
├── annotations/
│   ├── tier0_mutants.jsonl       (Eman — 406 rows, full expansion done)
│   ├── tier1a_codestream.jsonl   (Umaima — real CodeStream)
│   ├── tier1b_progpedia.jsonl    (Rayaan — PROGpedia)
│   ├── labels.jsonl              (merged, post-G7)
│   ├── gold.jsonl                (G6 — locked test set)
│   └── dev_gold.jsonl            (G6 — 4 rows; needs ≥60 for calibration)
├── features/
│   ├── features.csv              (448 rows, schema v1.1)
│   ├── FEATURE_SCHEMA.md
│   └── label_defining_features.json
├── splits/
│   └── splits.csv
├── models/
│   ├── xgb_best.json
│   ├── xgb_common.json
│   ├── xgb_full.json
│   └── metrics_v1.json
└── reports/
    ├── pilot_ablation.md
    ├── selection_report.md
    └── final_evaluation.md
```

## Row IDs

| Prefix | Lane | Script |
|--------|------|--------|
| `mut-*` | Eman (synthetic) | `scripts/expand_mutants.py` |
| `cs-*`  | Umaima (CodeStream real) | `scripts/label_weak_codestream.py` |
| `pg-*`  | Rayaan (PROGpedia) | `scripts/label_weak_progpedia.py` |

## Anti-collision matrix

- CodeStream labels: **Umaima only** (Eman reads seeds + diffs, never writes `cs-*`)
- PROGpedia: **Rayaan only**
- Bank + mutants: **Eman only**
- Matrix/splits/model: **Rayaan only**
- Statements: all lanes read-only

## Blocked on Rayaan

- `scripts/merge_dataset.py` requires `submissions.csv` (153k-row normalized index, built by the full normalization pipeline on Rayaan's machine)
- After Rayaan re-runs merge: pull main, retrain, commit updated `metrics_v1.json` + model artifacts
- 119 new `mut-*` rows (full expansion) are committed to `tier0_mutants.jsonl` and ready to merge
