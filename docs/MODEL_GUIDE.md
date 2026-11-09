# TraceLearn misconception model: master guide

Everything a teammate needs to get, run, retrain and judge the model. Numbers are as of 2026-11-09
for the served model (revert point `7b92fdc`; every model kept or rejected is in
[`MODEL_LOG.md`](MODEL_LOG.md)).

**Contents**
1. [What the model does](#1-what-the-model-does)
2. [Get the model](#2-get-the-model)
3. [How a submission is diagnosed](#3-how-a-submission-is-diagnosed)
4. [The dataset](#4-the-dataset)
5. [Features](#5-features)
6. [Train the model](#6-train-the-model)
7. [Evaluate the model](#7-evaluate-the-model)
8. [Performance and confusion matrices](#8-performance-and-confusion-matrices)
9. [Settings](#9-settings)
10. [Known weaknesses](#10-known-weaknesses)
11. [File map](#11-file-map)

---

## 1. What the model does

A student submits C++ code for a problem in the bank. If it fails a test, an XGBoost classifier
reads evidence about the code and how it fails, and names one of 11 labels (taxonomy `tl-cpp-v2`):

| Label | Meaning |
|---|---|
| `CPP_ARRAY_BOUNDS` | reads or writes outside an array |
| `CPP_ASSIGN_VS_COMPARE` | `=` where `==` was meant, inside a condition |
| `CPP_INT_OVERFLOW` | a value too big for its integer type |
| `CPP_LOOP_BOUNDARY` | loop runs one step too many or too few (`<=` vs `<`) |
| `CPP_MISSING_BASE_CASE` | recursion with a missing or wrong base case |
| `CPP_OFF_BY_ONE` | an index or count off by one outside the loop condition |
| `CPP_RANGE_CHECK` | wrong or missing check of a value's range |
| `CPP_STALE_EXIT` | a loop exit or flag that is not updated or reset |
| `CPP_UNINITIALIZED_VAR` | a variable used before it is given a value |
| `CPP_WRONG_LOOP_DIR` | loop counts the wrong way |
| `CPP_OTHER_ERROR` | fails for a reason that is none of the above |

The answer goes into both diagnoses (current-only and history-aware) and from there into the
student's learner state. When the model is unsure, the system shows **UNCERTAIN** with teacher
review instead of guessing.

---

## 2. Get the model

The trained model is committed to Git, so a teammate only needs the repository:

```bash
git clone https://github.com/Rayaan-Raza/TraceLearn.git
```

```bash
cd TraceLearn
git checkout feat/synth-v2-agent-programs
pip install -r requirements.txt
```

The model files are in `data/misconception_dataset/models/` (about 13 MB of JSON):

| File | What it is |
|---|---|
| `xgb_execution_v1.json` | **the served model** (needs run records) |
| `xgb_best_v1.json`, `xgb_common_v1.json`, `xgb_v1.json`, `xgb_masked_v1.json` | other variants, kept for comparison, not used by default |
| `calibrator.json` | temperature and abstain threshold for each variant |
| `label_encoder.json` | class index to label name |
| `metrics_v1.json` | training metrics, cross-validation confusion matrices, feature lists |

Check you have the right model. The sha256 of `xgb_execution_v1.json` must be
`0af477c27ce3955dd9343bb5db2f47aa46778c2816c370bdc20af35bb98790e2`:

```bash
python -c "import hashlib;print(hashlib.sha256(open('data/misconception_dataset/models/xgb_execution_v1.json','rb').read()).hexdigest())"
```

To go back to a logged model later (only the model folder changes):

```bash
git checkout 7b92fdc -- data/misconception_dataset/models
```

**Use it from Python**

```python
from backend.app.diagnosis.xgb_classifier import ModelClassifier

clf = ModelClassifier.load("execution")   # reads data/misconception_dataset/models
pred = clf.predict(features)              # features: dict of feature name -> value
print(pred.top_label, pred.top_probability, pred.abstained)
```

`features` must include the run-record features (section 5). In the app they are built for you.

**System needs.** Training and evaluating from `features.csv` need only Python. The full app path
compiles and runs the student's code, so it needs Linux (the model was trained on Ubuntu 24.04 with
g++ 13), `g++`, and in production bubblewrap with unprivileged user namespaces allowed. On Windows
use WSL.

---

## 3. How a submission is diagnosed

```
student submits ──► tests run in the sandbox ──► student sees test results at once
                                                   (diagnosis_pending = true)
background worker (backend/app/analysis/async_diagnosis.py)
   │
   ├─ passes every test? ──► no misconception; the model is not called
   │
   ├─ run record (backend/app/analysis/run_record.py):
   │     compile with sanitizers, run the tests, try single small edits for each
   │     class and record which edits make the failing test pass
   │
   ├─ XGBoost `execution` model ──► temperature-scaled probabilities
   │
   ├─ fusion "model_first" (backend/app/diagnosis/confidence.py):
   │     • names a class above threshold 0.44 → that is the diagnosis
   │     • says OTHER_ERROR                   → UNCERTAIN + teacher review
   │                                            (unless the rules found M02/M03,
   │                                             which the model has no class for)
   │     • abstains                           → the rule engine's weighted vote
   │
   └─ diagnosis saved ──► learner state updated ──► the result page shows it
```

A diagnosis takes from a few seconds to about a minute, mostly for the run record. The result
page polls every 3 s and shows "Analysing your code…" until it is ready.

---

## 4. The dataset

Everything is in `data/misconception_dataset/`. The raw source programs are **not** in the
repository because of their licences. The labels, splits and extracted features are.

**Sources**

| Source | What it is | How it is labelled |
|---|---|---|
| PROGPedia | real university C++ submissions | run on oracle tests; 2-3 independent annotator agents per row plus adjudication |
| CodeStream | real C/C++ student submissions | blind labelling by annotator agents |
| Agent-written programs (`stu-s2-*`, `stu-cp*`) | student-style programs by six author agents, many on our own bank | the author's intended bug, verified by running it |
| Project CodeNet (`cnx-*`, new) | 707 real failing programs on 11 problems | three annotator agents (A, B, adjudicator C) |
| CodeNet mutants (`stu-cn-*`, new) | 268 correct programs with one inserted bug, for rare classes | verified by running; one proof per row in `annotations/mutant_proofs/` |

The two CodeNet lanes are in the dataset, but the served model was trained before they existed.
A model trained with them was worse on unseen real code (section 8.4).

**Training set of the served model:** 1,349 rows, plus 208 dev-gold rows used only for checks. By
label (from the cross-validation in `metrics_v1.json`):

| Label | Rows | | Label | Rows |
|---|---:|---|---|---:|
| OTHER_ERROR | 741 | | LOOP_BOUNDARY | 71 |
| OFF_BY_ONE | 111 | | UNINITIALIZED_VAR | 69 |
| ARRAY_BOUNDS | 107 | | STALE_EXIT | 34 |
| INT_OVERFLOW | 73 | | ASSIGN_VS_COMPARE | 31 |
| RANGE_CHECK | 72 | | MISSING_BASE_CASE | 29 |
| | | | WRONG_LOOP_DIR | 11 |

OTHER_ERROR is more than half of the rows; WRONG_LOOP_DIR has only 11.

**Splits** (`splits/splits.csv`). Whole problems are held out, never single programs, so the test
measures performance on problems the model has never seen:

| Split | Use |
|---|---|
| `train` | training and cross-validation, grouped by problem cluster |
| `dev_gold` | sanity checks only, never in cross-validation |
| `test` | held-out problems: 664 real programs on 22 problems; scored to report, never to choose |
| `test_iid` | a small in-distribution check |

**Labels file.** `annotations/labels.jsonl` has one row per program. `scripts/merge_dataset.py`
builds it from the lane files `annotations/tier*.jsonl`: it checks every row, removes
near-duplicates (token-shingle Jaccard ≥ 0.8), assigns splits and checks that no problem leaks
across splits. More in [`DATASET_CARD.md`](../data/misconception_dataset/DATASET_CARD.md).

---

## 5. Features

`features/features.csv` has one row per program. Every column is described in
[`FEATURE_SCHEMA.md`](../data/misconception_dataset/features/FEATURE_SCHEMA.md). The `execution`
variant uses 187 features in five blocks:

| Block | Count | What it measures | Needs to run the code? |
|---|---:|---|---|
| `source.*` | 37 | code shape: loops, arrays, conditions, recursion | no |
| `semantics.*` | 27 | patterns such as `<=` against an array size, `=` in a condition | no |
| `warnings.*` | 24 | g++ warning counts | compile only |
| `evidence.*` | 50 | test results, sanitizer reports (out of bounds, overflow, uninitialised), timeouts | yes |
| `repair.*` | 49 | for each class, how many single small edits make the failing test (or every test) pass | yes |

The `repair.*` block is what lets the model work on unseen problems: "changing `<=` to `<` fixes
it" means the same thing on any problem. `scripts/counterfactual_evidence.py` builds it for
training rows, and the same code runs live in `run_record.py`.

Missing values are NaN, never 0. Without a run record the `execution` model abstains.

---

## 6. Train the model

Training reads `features/features.csv`, `annotations/labels.jsonl` and `splits/splits.csv`. It does
not need the raw programs or g++.

```bash
python scripts/train_xgb_misconception.py --profile plain --models-dir C:/tmp/new_models
```

What it does:
1. Selects rows from `train` and `dev_gold`: real rows with consensus labels, plus the
   agent-written families allowed for `plain`.
2. Trains every variant (full, masked, common, best, execution) with XGBoost:
   `n_estimators=200, max_depth=4, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8`, seed 7.
   Rows are weighted by label confidence. `--balance none|sqrt|full` adds class weights; `none` is
   served, and `sqrt` was tried and rejected.
3. Runs 3×3 cross-validation grouped by problem cluster and writes out-of-fold confusion matrices
   and per-class scores to `metrics_v1.json`.
4. Fits a temperature and an abstain threshold for each variant from the out-of-fold predictions
   (`scripts/calibration.py`) and writes `calibrator.json`.
5. Records the dataset gates (G8) in `metrics_v1.json`.

It takes several minutes. **Always write a new model to a scratch folder first** (`--models-dir`)
and copy it over the served one only after it beats the served model on the held-out test
(section 7). Then add an entry to `MODEL_LOG.md` and commit the model folder.

**Reproducing the served model.** Use the committed model files; retraining does not give back
the same file. Checked on 2026-11-09: training the current commit without the CodeNet rows gives
1,348 rows (served: 1,349) and macro-F1 0.697 (served: 0.700). One label was corrected after
the served model was trained. At threshold 0.44 that retrained model scores exactly like the
served one on the held-out set: accuracy 0.788, precision 75/104. Its calibration, however,
picked a threshold of 0.67, which gives accuracy 0.720 and precision 63/67 and abstains on 105 of
664 programs. **The automatic threshold is sensitive to small data changes.** After every retrain,
check the threshold in `calibrator.json` and the held-out numbers before serving the model.

Training the current commit as it is also uses the CodeNet rows (`cnx-*`, and `stu-cn-*` through
`PLAIN_SYNTHETIC_PREFIXES`). That is close to the rejected model in section 8.4, so do not serve it
without the held-out check.

**Rebuilding features from raw programs** (only when you change features or add data) needs the
raw datasets and Linux or WSL:

```bash
wsl python3 scripts/counterfactual_evidence.py --raw-root /mnt/g/TraceLearn/Datasets_RAW --workers 10
```

```bash
python scripts/merge_dataset.py --raw-root G:/TraceLearn/Datasets_RAW
```

```bash
python scripts/verify_dataset.py --per-class-report
```

---

## 7. Evaluate the model

Held-out problems (writes `reports/heldout_eval.md`, `heldout_eval.json` and `heldout_predictions.json`):

```bash
wsl python3 scripts/eval_heldout_rows.py --confirm-one-shot
```

Release gates, and which serving mode the model is cleared for:

```bash
python scripts/check_model_release.py
```

Tests:

```bash
python -m pytest -q backend/tests tests
```

Rules we follow:
- Choose models, thresholds and class weights **only** from cross-validation on training problems.
  The held-out test is for reporting. A threshold picked by looking at the test set does not count.
- Compare against the always-OTHER baseline. It scores accuracy 0.69 on the held-out set, because
  most failing programs have no named misconception.
- Report precision (when it names one, is it right), recall (how many real misconceptions it finds)
  and false alarm on OTHER, not accuracy alone.
- Labels come from annotator agents, not independent people, so every number is agreement with
  those annotators.

The model tests are `test_xgb_classifier.py`, `test_model_runner.py`, `test_run_record.py`,
`test_fusion_policy.py` and `test_async_diagnosis.py` in `backend/tests/`. `test_model_runner.py`
checks the served files against `backend/tests/fixtures/model_golden.json`. Regenerate it with
`python scripts/make_model_golden.py` when you change the served model on purpose. On Windows two
sandbox tests fail because there is no g++; run them in WSL.

---

## 8. Performance and confusion matrices

### Summary

| Test | Accuracy | Precision when it names one | Recall of misconceptions | False alarm on OTHER |
|---|---:|---:|---:|---:|
| Held-out real code, 20 unseen problems (525 programs) | **0.785** | **0.807** (71/88) | 0.406 | 0.026 |
| Held-out with the 2 CodeNet problems (664 programs) | 0.788 | 0.721 (75/104) | 0.368 | 0.026 |
| Simulated classroom, failing attempts (116) | 0.759 | 0.787 (63/80) | 0.778 | 9 of 35 |
| Simulated classroom, all attempts (161) | **0.826** | – | – | 0 of 45 correct programs flagged |
| Old default (rules only), same classroom | – | 0.400 | 0.420 | 20 of 35 |

Cross-validation on training problems: macro-F1 0.70. In the classroom, UNCERTAIN counts as right
for a program whose failure is not a named misconception, because that is the behaviour we want.

### 8.1 Training data, cross-validation (out of fold), `execution` variant

1349 training rows; 3 folds grouped by problem cluster, so a problem is never in training and validation at once. Macro-F1 0.70, ECE 0.069.

| True ↓ / Predicted → | ARRAY_BOUNDS | ASSIGN_VS_COMPARE | INT_OVERFLOW | LOOP_BOUNDARY | MISSING_BASE_CASE | OFF_BY_ONE | OTHER_ERROR | RANGE_CHECK | STALE_EXIT | UNINITIALIZED_VAR | WRONG_LOOP_DIR | Total | Recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **ARRAY_BOUNDS** | **82** | · | · | 3 | · | 5 | 16 | · | · | 1 | · | 107 | 0.77 |
| **ASSIGN_VS_COMPARE** | · | **30** | · | · | · | · | 1 | · | · | · | · | 31 | 0.97 |
| **INT_OVERFLOW** | 1 | · | **69** | · | 1 | · | 2 | · | · | · | · | 73 | 0.95 |
| **LOOP_BOUNDARY** | 1 | · | · | **65** | · | 2 | 3 | · | · | · | · | 71 | 0.92 |
| **MISSING_BASE_CASE** | 1 | · | · | · | **26** | · | 2 | · | · | · | · | 29 | 0.90 |
| **OFF_BY_ONE** | · | · | · | 7 | 1 | **47** | 52 | 3 | · | 1 | · | 111 | 0.42 |
| **OTHER_ERROR** | 37 | 4 | · | 2 | · | 15 | **651** | 6 | 3 | 23 | · | 741 | 0.88 |
| **RANGE_CHECK** | · | · | · | · | 1 | 2 | 28 | **41** | · | · | · | 72 | 0.57 |
| **STALE_EXIT** | 6 | · | · | · | 1 | · | 17 | 1 | **9** | · | · | 34 | 0.26 |
| **UNINITIALIZED_VAR** | 5 | · | 2 | 3 | · | · | 11 | 1 | · | **47** | · | 69 | 0.68 |
| **WRONG_LOOP_DIR** | · | · | · | · | · | 2 | 7 | · | · | · | **2** | 11 | 0.18 |
| *Precision* | 0.62 | 0.88 | 0.97 | 0.81 | 0.87 | 0.64 | 0.82 | 0.79 | 0.75 | 0.65 | 1.00 | | |

| Class | Precision | Recall | F1 | Rows |
|---|---:|---:|---:|---:|
| ARRAY_BOUNDS | 0.62 | 0.77 | 0.68 | 107 |
| ASSIGN_VS_COMPARE | 0.88 | 0.97 | 0.92 | 31 |
| INT_OVERFLOW | 0.97 | 0.95 | 0.96 | 73 |
| LOOP_BOUNDARY | 0.81 | 0.92 | 0.86 | 71 |
| MISSING_BASE_CASE | 0.87 | 0.90 | 0.88 | 29 |
| OFF_BY_ONE | 0.64 | 0.42 | 0.51 | 111 |
| OTHER_ERROR | 0.82 | 0.88 | 0.85 | 741 |
| RANGE_CHECK | 0.79 | 0.57 | 0.66 | 72 |
| STALE_EXIT | 0.75 | 0.26 | 0.39 | 34 |
| UNINITIALIZED_VAR | 0.65 | 0.68 | 0.67 | 69 |
| WRONG_LOOP_DIR | 1.00 | 0.18 | 0.31 | 11 |

### 8.2 Held-out real code: 664 programs on 22 problems never used in training (`execution`, threshold 0.44)

| True ↓ / Predicted → | ARRAY_BOUNDS | ASSIGN_VS_COMPARE | INT_OVERFLOW | LOOP_BOUNDARY | OFF_BY_ONE | OTHER_ERROR | RANGE_CHECK | STALE_EXIT | UNINITIALIZED_VAR | ABSTAIN | Total | Recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **ARRAY_BOUNDS** | **61** | · | · | · | · | 32 | · | · | 2 | 1 | 96 | 0.64 |
| **ASSIGN_VS_COMPARE** | · | **3** | · | · | · | · | · | · | · | · | 3 | 1.00 |
| **INT_OVERFLOW** | · | · | **4** | · | · | 5 | · | · | · | · | 9 | 0.44 |
| **LOOP_BOUNDARY** | · | · | · | **1** | 9 | 3 | · | · | · | 2 | 15 | 0.07 |
| **OFF_BY_ONE** | · | · | 2 | · | **1** | 31 | · | · | · | 1 | 35 | 0.03 |
| **OTHER_ERROR** | 6 | 1 | · | · | 2 | **448** | 1 | · | 2 | · | 460 | 0.97 |
| **RANGE_CHECK** | · | · | · | · | · | 24 | **0** | · | · | · | 24 | 0.00 |
| **STALE_EXIT** | 1 | · | · | · | · | 3 | · | **0** | · | · | 4 | 0.00 |
| **UNINITIALIZED_VAR** | 3 | · | · | · | · | 9 | · | · | **5** | 1 | 18 | 0.28 |
| *Precision* | 0.86 | 0.75 | 0.67 | 1.00 | 0.08 | 0.81 | 0.00 | – | 0.56 | – | | |

### 8.3 Simulated classroom through the real backend: 161 attempts, shipped defaults

| True ↓ / Shown → | ARRAY_BOUNDS | ASSIGN_VS_COMPARE | LOOP_BOUNDARY | MISSING_BASE_CASE | OFF_BY_ONE | RANGE_CHECK | STALE_EXIT | UNINITIALIZED_VAR | WRONG_LOOP_DIR | M02_INDEX_VALUE | M03_MISSING_RETURN | NO_MISCONCEPTION | OTHER | INT_OVERFLOW | UNCERTAIN | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **ARRAY_BOUNDS** | **1** | · | · | · | · | · | · | · | · | · | · | · | · | · | · | 1 |
| **ASSIGN_VS_COMPARE** | · | **6** | · | · | · | · | · | · | · | · | · | · | · | · | · | 6 |
| **LOOP_BOUNDARY** | · | · | **9** | · | · | · | · | · | · | · | · | · | · | · | · | 9 |
| **MISSING_BASE_CASE** | · | · | · | **4** | · | · | · | · | · | · | · | · | · | 1 | · | 5 |
| **OFF_BY_ONE** | 2 | · | · | · | **10** | · | · | · | · | · | · | · | · | · | 2 | 14 |
| **RANGE_CHECK** | · | · | · | · | · | **11** | · | · | · | · | · | · | · | · | 3 | 14 |
| **STALE_EXIT** | 1 | · | · | · | · | · | **6** | · | · | · | · | · | · | · | · | 7 |
| **UNINITIALIZED_VAR** | · | · | · | · | · | · | · | **5** | · | · | · | · | · | · | · | 5 |
| **WRONG_LOOP_DIR** | · | · | · | · | · | · | · | · | **1** | · | · | · | · | · | 5 | 6 |
| **M02_INDEX_VALUE** | · | · | · | · | 4 | · | · | · | · | **3** | · | · | · | · | · | 7 |
| **M03_MISSING_RETURN** | · | · | · | · | · | · | · | · | · | · | **7** | · | · | · | · | 7 |
| **NO_MISCONCEPTION** | · | · | · | · | · | · | · | · | · | · | · | **45** | · | · | · | 45 |
| **OTHER** | 1 | · | · | · | · | · | · | · | · | 5 | 3 | 1 | **0** | · | 25 | 35 |


**How to read these**
- **8.1 (cross-validation)** is the optimistic view. Folds keep problems apart, but the training
  data includes agent-written programs that are easier than real code. OFF_BY_ONE, STALE_EXIT and
  WRONG_LOOP_DIR are mostly confused with OTHER_ERROR.
- **8.2 (held-out real code)** is the honest view. The model is strong on ARRAY_BOUNDS (precision
  0.86), ASSIGN_VS_COMPARE and OTHER (0.81), and reasonable on INT_OVERFLOW and UNINITIALIZED_VAR.
  It almost never gets OFF_BY_ONE, LOOP_BOUNDARY or RANGE_CHECK right on these problems. Those
  mostly fall back to OTHER, which is a miss but not a false label.
- **8.3 (classroom)** runs the whole app with production settings on bank-style code from 7
  simulated students. For "OTHER" failures UNCERTAIN (25 of 35) is the intended answer. The 9 named
  ones are false alarms, mostly M02/M03 from the rules, which the model has no class for.
  M02_INDEX_VALUE is often called OFF_BY_ONE (4 of 7).

### 8.4 Models tried and rejected

| Model | Accuracy (664) | Precision | Recall | Why rejected |
|---|---:|---:|---:|---|
| **served: plain, no class weights** | **0.788** | **0.721** | 0.368 | – |
| plain + CodeNet labels + CodeNet mutants + sqrt class weights | 0.595 | 0.902 | 0.363 | abstains on 31% of programs; flags 31% of CodeNet OTHER programs |
| same, no threshold | 0.762 | 0.608 | 0.456 | too many false alarms |
| `best` variant (no execution features) | 0.667 | 0.182 | 0.020 | finds almost nothing |

Cross-validation preferred the rejected model (macro-F1 0.765 against 0.70). That is why the
held-out check is required before replacing the served model.

---

## 9. Settings

Set in `.env`; defaults are in `backend/app/config.py`.

| Setting | Default | Meaning |
|---|---|---|
| `MODEL_DIAGNOSIS` | `on` | `off` = rules only; `shadow` = store the model's answer but do not use it |
| `MODEL_VARIANT` | `execution` | which model file to serve |
| `MODEL_RUN_RECORDS` | `on` | build run records for failing C++ submissions |
| `MODEL_FUSION` | `model_first` | `points` = the model is one weighted vote among the rules |
| `MODEL_ASYNC` | `true` | diagnose on a background worker |
| `MODEL_DIR` | `./data/misconception_dataset/models` | where the model files are |
| `HISTORY_NEEDS_OBSERVED_SUPPORT` | `true` | history evidence alone cannot name a misconception |

To switch the model off quickly, set `MODEL_DIAGNOSIS=off`.

---

## 10. Known weaknesses

- **Recall on unseen real problems is about 0.4.** When it names a misconception it is usually
  right, but it misses more than half, especially OFF_BY_ONE, LOOP_BOUNDARY and RANGE_CHECK.
- **No real students yet.** Classroom attempts were written by agents, and labels come from
  annotator agents. Both need checking against real students and human labels.
- **Unbalanced data.** OTHER_ERROR is 56% of the training weight (the gate asks for at most 15%),
  and WRONG_LOOP_DIR has 11 rows.
- **Speed.** Run records take 5-60 s, up to about 3 minutes in the worst case.
- **Same compiler.** Run records built with another g++ version give different features. Keep the
  server on Ubuntu 24.04 with g++ 13, as in training.
- **Threshold.** 0.60 instead of 0.44 would raise held-out precision to about 0.91, but that number
  was read off the test set. It needs fresh labelled data before it is adopted.

---

## 11. File map

| Path | Role |
|---|---|
| `scripts/train_xgb_misconception.py` | trainer |
| `scripts/calibration.py` | temperature and abstain threshold |
| `scripts/eval_heldout_rows.py` | held-out evaluation |
| `scripts/check_model_release.py` | release gates |
| `scripts/merge_dataset.py`, `scripts/verify_dataset.py` | build and check the dataset |
| `scripts/counterfactual_evidence.py` | run records for training rows |
| `scripts/make_model_golden.py` | golden fixture for the model tests |
| `tracelearn_features/` | feature extraction (`extractor.py`, `execution.py`, `schema.py`) |
| `backend/app/diagnosis/xgb_classifier.py` | loads and runs the model |
| `backend/app/analysis/model_runner.py` | turns a prediction into evidence |
| `backend/app/analysis/run_record.py` | live run records |
| `backend/app/analysis/async_diagnosis.py` | background worker |
| `backend/app/diagnosis/confidence.py` | fusion (`model_first`) |
| `data/misconception_dataset/models/` | model files |
| `data/misconception_dataset/reports/` | evaluation reports |
| `docs/MODEL_LOG.md` | every model kept or rejected, with revert commands |
| `docs/6-nov.md`, sections 15-19 | full history of the model work |
