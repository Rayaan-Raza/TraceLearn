# TraceLearn Misconception Dataset

**Taxonomy:** `tl-cpp-v2` · **Schema:** `1.1` · **Version:** `0.6` · **Status:** active

11-class C++ misconception classifier dataset. See [DATASET_CARD.md](DATASET_CARD.md) for full provenance, splits, model performance, and limitations.

## Quick start

```bash
# Train XGBoost classifier (3-repeat CV)
python scripts/train_xgb_misconception.py --cv-repeats 3

# Re-merge after annotation updates
python scripts/merge_dataset.py   # requires submissions.csv on Rayaan's machine

# Expand synthetic mutants (needs Kali WSL + g++)
python scripts/expand_mutants.py --raw-root /path/to/Datasets_RAW

# PROGPedia: oracle tests, then execute WA/RE submissions on them (g++, ASan/UBSan, valgrind)
python scripts/progpedia_oracle_tests.py --raw-root /path/to/Datasets_RAW
python scripts/label_progpedia_exec.py --raw-root /path/to/Datasets_RAW --index-csv <submissions.csv>

# Human sign-off of the model pre-review sheets -> decisions, audits, human rows
python scripts/apply_prereview_signoff.py --raw-root /path/to/Datasets_RAW   # --dry-run to preview

# Held-out evaluation (certain labels only; every run is logged)
python scripts/evaluate_holdout.py --split test_iid
python scripts/evaluate_holdout.py --split test --confirm-one-shot
```

After signing sheets: `apply_prereview_signoff.py` → re-run the labeling lanes (cached,
seconds; picks up the new `lf_audits.csv` confidences) → `merge_dataset.py` →
`train_xgb_misconception.py`.

## Current model (v0.6)

| Variant | OOF macro-F1 | CV macro-F1 |
|---------|-------------|-------------|
| full (all 90 features) | 0.713 | 0.724 ± 0.030 |
| best (`static + warnings + semantics`) | 0.703 | 0.711 ± 0.037 |
| common (`static + warnings`) | 0.696 | 0.705 ± 0.045 |

702 rows (train 588 · dev_gold 45 · test 33 · test_iid 36). Majority baseline 0.035.
G8: 3/4 PASS; synthetic mass 0.91 by weight > 0.50 cap (see DATASET_CARD).

## Layout

```
data/misconception_dataset/
├── README.md
├── DATASET_CARD.md           (v0.6)
├── ANNOTATION_GUIDELINE.md
├── HOURS_LOG.md
├── raw_recovery/
│   └── recovery_manifest.json
├── fixtures/                 (unit-test fixtures per lane)
├── annotations/
│   ├── tier0_mutants.jsonl       (Eman — 406 rows, full expansion done)
│   ├── tier1a_codestream.jsonl   (Umaima — real CodeStream)
│   ├── tier1b_progpedia.jsonl    (Rayaan — PROGpedia)
│   ├── tier1c_progpedia_exec.jsonl (PROGPedia executed on oracle tests — pgx-*)
│   ├── tier1d_human_review.jsonl (hr-* — written by apply_prereview_signoff.py)
│   ├── label_review_decisions.jsonl (signed confirm / relabel / reject; applied by the merge)
│   ├── lf_audits.csv             (per-LF audit counts -> weak-label confidence)
│   ├── labels.jsonl              (merged, post-G7)
│   ├── gold.jsonl                (G6 — locked test set)
│   └── dev_gold.jsonl            (G6 adjudicated forms; dev-gold now also comes from signed pre-review sheets)
├── features/
│   ├── features.csv              (702 rows, schema v1.1)
│   ├── FEATURE_SCHEMA.md
│   └── label_defining_features.json
├── splits/
│   ├── README.md                 (the four pools + change log)
│   ├── cluster_assignments.csv
│   ├── iid_holdout.csv
│   └── splits.csv
├── oracle_tests/progpedia/       (12 problems, gzipped; big inputs regenerated from seeds)
├── review/
│   ├── model_prereview/          (model pre-review sheets — sign here; README inside)
│   ├── progpedia_exec_review.jsonl (multi-signal / discovery rows awaiting a person)
│   └── progpedia_exec_tier1b_evidence.jsonl
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
| `pgx-*` | PROGPedia executed on oracle tests | `scripts/label_progpedia_exec.py` |
| `hr-*`  | human-labeled via pre-review sign-off (any natural source) | `scripts/apply_prereview_signoff.py` |

## Anti-collision matrix

- CodeStream labels: **Umaima only** (Eman reads seeds + diffs, never writes `cs-*`)
- PROGpedia: **Rayaan only**
- Bank + mutants: **Eman only**
- Matrix/splits/model: **Rayaan only**
- Statements: all lanes read-only

**Needs Rayaan's review before merging `feature/umaima-real-labels`:** this branch
adds a new PROGPedia lane (`tier1c`, `pgx-*`; `tier1b` / `pg-*` untouched) and
changes splits. It moves `clu-049` and `clu-051` to dev_gold, adds `iid_holdout.csv`,
and retrains (`models/`). Reasons are in `splits/README.md` and DATASET_CARD.

## Blocked on Rayaan

- `scripts/merge_dataset.py` requires `submissions.csv` (153k-row normalized index, built by the full normalization pipeline on Rayaan's machine)
- After Rayaan re-runs merge: pull main, retrain, commit updated `metrics_v1.json` + model artifacts
- 119 new `mut-*` rows (full expansion) are committed to `tier0_mutants.jsonl` and ready to merge
