# Dataset critique — response plan (Week 1)

Senior review received: 10 Nov 2026. This document tracks the Week 1 fixes.

## Findings and fixes

| # | Finding | Status | File(s) changed |
|---|---|---|---|
| 1 | `tl-progpedia-00000039` supplies 282 / 664 (43 %) of test rows; row-weighted macro-F1 is dominated by one problem | ✅ DONE | `scripts/eval_heldout_rows.py` |
| 2 | LOOP_BOUNDARY / OFF_BY_ONE boundary rule not written down; real rows labelled inconsistently | ✅ rule written; 🔶 queue built (19 rows), relabelling by a person still to do | `ANNOTATION_GUIDELINE.md`, `scripts/find_label_conflicts.py` (repair-evidence signal), `review/label_conflicts/lb_obo_conflicts.csv` |
| 3 | No dataset manifest — model and training data can drift apart silently | ✅ DONE (script; the trainer writes `models/dataset_manifest.json`). CI does not check it yet | `scripts/make_dataset_manifest.py`, `scripts/train_xgb_misconception.py` |
| 4 | Trainer silently overwrites served model | ✅ DONE (`--force` guard on `xgb_execution_v1.json`) | `scripts/train_xgb_misconception.py` |
| 5 | CPP_STALE_EXIT has no proof-based repair generator | ⏸ moved to a separate PR (see below) | — |
| 6 | RANGE_CHECK generator misses while/for loop guard flips | ⏸ moved to a separate PR (see below) | — |
| 7 | UNINITIALIZED_VAR generator misses pointer and 0-init patterns | ⏸ moved to a separate PR (see below) | — |
| 8 | INT_OVERFLOW extra generator missing (cast, LL-suffix, %lld patterns) | ⏸ moved to a separate PR (see below) | — |
| 9 | Calibration threshold unstable across retrains | ✅ the served per-variant threshold was already a 200-resample cluster-bootstrap median (`scripts/calibration.py`; execution p05-p95 0.38-0.69). Added: the trainer warns when a retrain moves a threshold by ≥ 0.10. The dev-gold global threshold now also uses a bootstrap median | `scripts/train_xgb_misconception.py` |
| 10 | No tool to audit near-empty class coverage | ✅ DONE | `scripts/mine_sparse_classes.py` |
| 11 | No real test-set coverage audit | ✅ DONE | `scripts/build_real_test_set.py` |
| 12 | Repair-first inference rule not wired in | ✅ DONE (about 0.9 precision on real rows, not 100%) | `backend/app/diagnosis/xgb_classifier.py`, `backend/app/analysis/model_runner.py` |

## Repair generator changes: held back (review 2026-11-13)

Commits `0b556f0`, `d25b667`, `dcfdb10`, `ae04a5c` changed `repair_verify.py` / `repair_extra.py`.
The live run record copies those two files and runs them on every failing submission, so a change
there changes the served model's input at once, while the model and `features.csv` were built with
the old generators. They are reverted in this PR and come back in their own PR with:

- RANGE_CHECK: do not flip `<`/`<=` in `for`/`while` conditions — that is the LOOP_BOUNDARY repair,
  so loop-boundary bugs would be "fixed" by two classes and the repair-first rule would stop firing;
- INT_OVERFLOW `printf_d_to_lld`: pass the whole spliced program, not only the format string; skip
  `int * p` declarations in the `(long long)` cast pattern;
- STALE_EXIT: add it to `REPAIR_CLASSES` (and the repair-first map) or the generator only costs time;
- then re-run `counterfactual_evidence.py`, retrain into a scratch folder, and compare on the
  held-out set before serving.

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
