# Evaluation protocol

Written 16 November 2026, before any new evaluation run, in answer to the supervisor's
"freeze protocol first" (action plan and claims audit of 15 November 2026). Baseline: tag
`audit-2026-11-15` = `c62f8ba`, the commit the supervisor audited.

This file fixes what we measure, on what, and how a model or rule is chosen, **before** the
results are known. Change it only in its own commit, with the reason, and never after looking at
the result the change would affect.

## 1. Populations

Every number names one of these. "The test set" on its own is not allowed.

| Name | What it is | Status | May be used for |
|---|---|---|---|
| **Development set** | The `test` split of `splits.csv`: real failing programs on 22 problems held out of training (664 rows at `c62f8ba`). | **Exposed.** Scored many times; model and data choices have been made with it (see section 8). | Comparing finished candidates, at most once each, logged. Never called "blind", "final" or "untouched". |
| **Historical blind set** | The 84 items of `blind_final_eval` (83 certain, 7 problems, 4 named-class truths). | **Exposed.** Scored four times on 6 November. | History only. Not scored again. |
| **Bank benchmark** | 273 single-edit bugs on the 40 bank problems (`scripts/eval_bank_benchmark.py`, PR #17). | Synthetic, built with the same operators as training rows. | An upper estimate of behaviour on bank problems. Never a headline result. |
| **Confirmatory set** | A new set on problems that appear nowhere in `splits.csv`, labelled blind by the three of us before any model output, then frozen (Gate 5). | Does not exist yet. | Scored **once**, by the frozen system (Gate 6). |

Training-side evidence, used for every choice (section 5): grouped out-of-fold predictions on
the `train` split, and the `dev_gold` split.

## 2. Systems

Every table says which system it scores.

- **Classifier only**: `ModelClassifier.predict`, with its threshold and any per-class bars.
- **Full runtime**: what the backend serves. Class rules, the repair-first rule, the narrow
  repairs, then the classifier, in the order of `backend/app/analysis/model_runner.py`. The
  evaluator must import the backend's own decision functions; it may not re-implement them.

## 3. Label provenance

Every report states, in its header, how many scored rows have each label origin (agent
consensus, blind review, human-signed, weak rule, execution-verified), using the provenance
fields from Gate 1. Every number is **agreement with the recorded labels**, not accuracy against
independently established truth, unless every scored row is human-signed.

## 4. Metrics

Primary: **problem-weighted macro-F1** of the full runtime, with a 95% interval from resampling
whole problems.

Always reported beside it, for both systems:

- precision when a named class is predicted, with counts;
- named-class recall, with counts;
- false alarm rate on OTHER_ERROR rows, with counts;
- abstain rate;
- row-weighted macro-F1;
- per class: support, predicted, correct, precision, recall, F1, Wilson intervals;
- per problem: rows, named positives, correct named predictions;
- **every table again without problem `tl-progpedia-00000039`**, which supplies 282 of the 664
  development rows and 58 of the 75 correct named predictions of the audited model.

Accuracy is shown only next to the always-OTHER_ERROR baseline (0.693 on the 664 rows).
Precision is never quoted without recall.

### The 85% target

The progress report of 1-15 November named an 85% accuracy target. No document in this
repository defines it, and accuracy is a weak measure here: always answering OTHER_ERROR scores
0.693. We propose to drop it and use the criterion the dataset master plan
(`docs/master_plan_dataset.md`, G9 and section 13.7) already pre-registered: the full runtime
against the rule baseline, paired bootstrap difference resampled by problem, with a +0.05
macro-F1 point estimate whose interval spans zero read as "inconclusive-directional".

Agreed with the supervisor on: ____________ . Agreed wording: ____________ .

## 5. Selection rule

- Every choice of training profile, training rows, threshold, per-class bar, repair or rule is
  made on training-side evidence only (section 1).
- A finished candidate is scored on the development set **once**, and the run is logged
  (section 8). Nothing is changed in response to that score except the decision in section 6.
- The confirmatory set never enters training, calibration, threshold fitting or rule design.
- Rejected candidates are logged in `docs/MODEL_LOG.md` too.

## 6. Merge rule for PR #17

Applied at Gate 4 to the Gate 3 report, which scores the audited model and the PR #17 model,
each as classifier only and as full runtime, on the rows both share.

PR #17 is merged only if, for the **full runtime**, **both** with and without problem
`tl-progpedia-00000039`:

1. problem-weighted macro-F1 is higher than the audited model's, **and**
2. precision when a named class is predicted is not lower, **and**
3. the false alarm rate on OTHER_ERROR is not higher.

Otherwise it is closed, and the parts that do not change the served model (the bank benchmark
and the threshold-tuning script, with their tests) go in a separate pull request. No setting of
either model is changed between the Gate 3 report and this decision.

## 7. Known deviations from the dataset master plan

Stated so that nobody has to discover them.

| Master plan | Current practice | Where |
|---|---|---|
| One global threshold plus temperature (G8, section 13.3) | PR #17 adds per-class bars, fitted on grouped out-of-fold training rows | `scripts/tune_class_thresholds.py`, `docs/MODEL_LOG.md` 2026-11-14 |
| Class-mass cap of 15% (G8) | The largest class holds 0.518 of training weight in PR #17 (`max_class_mass_ok: false`) | `models/metrics_v1.json` |
| All tuning on train, val and dev-gold (section 13.7) | The exclusion of the CodeNet RANGE_CHECK mutants was chosen with development-set results | `docs/MODEL_LOG.md` 2026-11-14 and 2026-11-15 |
| Test gold touched exactly once (section 13.7) | The development set has been scored many times (section 8) | `reports/holdout_evaluations.jsonl` |

## 8. Exposure log

Every scoring of the development set, the historical blind set or (later) the confirmatory set
gets one line here, in the same commit as its report. Before this file, scorings were logged
automatically in `data/misconception_dataset/reports/holdout_evaluations.jsonl` (21 entries at
`c62f8ba`) and some only described in `docs/MODEL_LOG.md`.

| Date (UTC) | Set | Model (execution sha256, first 16) | Why | Recorded in |
|---|---|---|---|---|
| 2026-11-06 12:00 | Historical blind set | `best` 93c20933 | First scoring of the frozen set | `holdout_evaluations.jsonl` |
| 2026-11-06 15:27 | Historical blind set | `best` 528d92a6 | Rescored after a retrain | `holdout_evaluations.jsonl` |
| 2026-11-06 16:55 | Historical blind set | `best` 04278cf6 | Rescored after a retrain (committed report) | `holdout_evaluations.jsonl`, `blind_final_eval.md` |
| 2026-11-06 16:55 | Development set | `best` 04278cf6 | First held-out scoring | `holdout_evaluations.jsonl` |
| 2026-11-07 08:00 | Development set | `best` f9cae8d5 | Retrain | `holdout_evaluations.jsonl` |
| 2026-11-07 10:38 | Development set | 6bca6f3a84ec717d | Lane fingerprint found in the per-lane breakdown | `holdout_evaluations.jsonl`, `docs/6-nov.md` |
| 2026-11-07 11:01 | Development set | d73c38a5ce561788 | Rescored after the fingerprint fix | `holdout_evaluations.jsonl` |
| 2026-11-08 11:42 | Development set | 0af477c27ce3955d | Served model, 525 rows | `holdout_evaluations.jsonl` |
| 2026-11-09 05:48 | Development set | 8c7c9a7095ba3724 | CodeNet and sqrt-weight retrain, rejected | `holdout_evaluations.jsonl`, `MODEL_LOG.md` |
| 2026-11-09 05:52 | Development set | 0af477c27ce3955d | Served model, 664 rows (committed report) | `holdout_evaluations.jsonl`, `heldout_eval.md` |
| 2026-11-13 to 14 | Development set | 0af477c27ce3955d and a mutant model | Per-class bars, narrow repairs, mutant model compared | `MODEL_LOG.md` 2026-11-14 only |
| 2026-11-15 | Development set | 8860b506160ed29c and 0af477c27ce3955d | PR #17 candidate; RANGE_CHECK exclusion chosen here | `MODEL_LOG.md` 2026-11-15 only |
| 2026-11-16 | Development set | 8860b506160ed29c | Class rules for MISSING_BASE_CASE and WRONG_LOOP_DIR | `MODEL_LOG.md` 2026-11-16 only |

The `test_iid` split (25 rows) was also scored six times on 6 and 8 November.

## 9. Reports

- Every result is a file written by a script and committed unedited, with the model hash, the
  commit and the date in its header. A wrong report is fixed by fixing the script and rerunning.
- `docs/MODEL_LOG.md` links to reports; it does not carry hand-typed copies of their tables.
- A second team member reproduces each gate's headline numbers from a clean checkout before the
  gate passes.
