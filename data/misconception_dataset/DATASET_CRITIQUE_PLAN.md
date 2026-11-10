# Dataset critique — response plan (Week 1)

Senior review received: 10 Nov 2026. This document tracks the Week 1 fixes.

## Findings and fixes

| # | Finding | Status | File(s) changed |
|---|---|---|---|
| 1 | `tl-progpedia-00000039` supplies 282 / 664 (43 %) of test rows; row-weighted macro-F1 is dominated by one problem | ✅ DONE | `scripts/eval_heldout_rows.py` |
| 2 | LOOP_BOUNDARY / OFF_BY_ONE boundary rule not written down; ~40 real rows labelled inconsistently | ✅ DONE | `ANNOTATION_GUIDELINE.md`, `scripts/find_label_conflicts.py`, `review/label_conflicts/` |
| 3 | No dataset manifest — model and training data can drift apart silently | ✅ DONE | `scripts/make_dataset_manifest.py`, `scripts/train_xgb_misconception.py` |
| 4 | Trainer silently overwrites served model | ✅ DONE | `scripts/train_xgb_misconception.py` (--force guard) |
| 5 | CPP_STALE_EXIT has no proof-based repair generator | ✅ DONE | `scripts/repair_verify.py` |
| 6 | RANGE_CHECK generator misses while/for loop guard flips | ✅ DONE | `scripts/repair_extra.py` |
| 7 | UNINITIALIZED_VAR generator misses pointer and 0-init patterns | ✅ DONE | `scripts/repair_extra.py` |
| 8 | INT_OVERFLOW extra generator missing (cast, LL-suffix, %lld patterns) | ✅ DONE | `scripts/repair_extra.py` |
| 9 | Calibration threshold unstable across CV seeds | ✅ DONE | `scripts/train_xgb_misconception.py` (bootstrap_threshold) |
| 10 | No tool to audit near-empty class coverage | ✅ DONE | `scripts/mine_sparse_classes.py` |
| 11 | No real test-set coverage audit | ✅ DONE | `scripts/build_real_test_set.py` |
| 12 | Repair-first inference rule not wired in | ✅ DONE | `backend/app/diagnosis/xgb_classifier.py`, `backend/app/analysis/model_runner.py` |

## What is NOT done here (needs data / WSL / Rayaan's machine)

- Relabelling the ~40 LB/OBO conflict rows (requires human review of `review/label_conflicts/lb_obo_conflicts.csv`)
- Mining ≥30 real rows for ASSIGN_VS_COMPARE, MISSING_BASE_CASE, WRONG_LOOP_DIR, STALE_EXIT
- Building real test sets per class (≥15 rows, ≥5 problems each)
- Two-stage classifier ("named vs OTHER" binary first) — deferred; needs training data first
- Re-running eval_heldout_rows.py with --exclude-problems tl-progpedia-00000039 (needs WSL + model files)

## How to verify the problem-39 concentration fix

```bash
# With --exclude-problems p39 is dropped from the score
wsl python3 scripts/eval_heldout_rows.py --confirm-one-shot --exclude-problems tl-progpedia-00000039
```

The problem-weighted column in the new report table is the honest figure.

## How to run the LB/OBO conflict finder

```bash
python scripts/find_label_conflicts.py
# Writes review/label_conflicts/lb_obo_conflicts.csv
# Human annotators: apply ANNOTATION_GUIDELINE §6 to each row
```

## How to check dataset/model sync

```bash
python scripts/make_dataset_manifest.py --check
# 0 exit = all files match; 1 exit = drift detected
```
