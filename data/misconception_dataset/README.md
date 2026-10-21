# TraceLearn Misconception Dataset

**Taxonomy:** `tl-cpp-v2` · **Schema:** `1.0` · **Status:** in-progress

## Layout

```
data/misconception_dataset/
├── README.md
├── DATASET_CARD.md           (filled at G9)
├── ANNOTATION_GUIDELINE.md   (filled at U5)
├── HOURS_LOG.md
├── raw_recovery/
│   └── recovery_manifest.json
├── fixtures/                 (unit-test fixtures per lane)
├── annotations/
│   ├── tier0_mutants.jsonl       (Eman — synthetic)
│   ├── tier1a_codestream.jsonl   (Umaima — real CodeStream)
│   ├── tier1b_progpedia.jsonl    (Rayaan — PROGpedia)
│   ├── labels.jsonl              (merged, post-G7)
│   ├── gold.jsonl                (G6 — locked test set)
│   └── dev_gold.jsonl            (G6 — calibration set)
├── features/
│   ├── features.csv
│   ├── FEATURE_SCHEMA.md
│   └── label_defining_features.json
├── splits/
│   └── splits.csv
├── models/
│   └── (xgb artefacts at G8)
└── reports/
    ├── pilot_ablation.md
    ├── selection_report.md
    └── final_evaluation.md
```

## Row IDs

| Prefix | Lane | Script |
|--------|------|--------|
| `mut-*` | Eman (synthetic) | `scripts/generate_mutants.py` |
| `cs-*`  | Umaima (CodeStream real) | `scripts/label_weak_codestream.py` |
| `pg-*`  | Rayaan (PROGpedia) | `scripts/label_weak_progpedia.py` |

## Anti-collision matrix

- CodeStream labels: **Umaima only** (Eman reads seeds + diffs, never writes `cs-*`)
- PROGpedia: **Rayaan only**
- Bank + mutants: **Eman only**
- Matrix/splits/model: **Rayaan only**
- Statements: all lanes read-only
