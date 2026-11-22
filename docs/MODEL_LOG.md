# Model log

Full guide (getting, training, evaluating, confusion matrices): [`MODEL_GUIDE.md`](MODEL_GUIDE.md).

One entry per model worth keeping, newest first. Each entry names the commit that holds the model
files, how it was measured, and how to go back to it.

To restore a logged model (only the model folder changes; the code stays as it is):

```bash
git checkout <commit> -- data/misconception_dataset/models
```

The backend serves the `execution` variant only with `MODEL_DIAGNOSIS=on`, `MODEL_VARIANT=execution`
and `MODEL_RUN_RECORDS=on`.

Held-out results are generated, not typed. The current figures for the served model and for any
candidate are in [`reports/heldout_eval.md`](../data/misconception_dataset/reports/heldout_eval.md),
written by `scripts/eval_heldout_rows.py`. Tables in the entries below are the record of what was
measured at the time. Where an entry and the report disagree, the report is current.

---

## 2026-11-22: P0 baseline on real rows (no model change)

No new model. This entry records the baseline that every later candidate in
`docs/MODEL_IMPROVEMENT_PLAN.md` is compared against, measured with the new harness
`scripts/eval_candidate_oof.py`. The harness runs grouped out-of-fold on the train split: 3 folds by
problem cluster, 3 repeats, 1,367 real and 1,107 synthetic rows. Each row goes through
`runtime_decision`. The held-out split was not read. Full tables are in
[`reports/candidates/candidates.md`](../data/misconception_dataset/reports/candidates/candidates.md).

| Candidate | Real macro-F1, per repeat (mean ± sd) | Real macro-F1, mean of repeats | All rows | False alarm, real OTHER |
|---|---|---|---|---|
| `served`: served bars, no narrow-repair records | 0.516 ± 0.034 | 0.495 | 0.805 | 0.033 (33/998) |
| `served_runtime`: plus narrow-repair records | 0.539 ± 0.037 | 0.522 | 0.813 | 0.034 (34/998) |
| `served_crossfit`: bars refitted per fold | 0.526 ± 0.034 | 0.506 | 0.804 | 0.070 (70/998) |

- **The P0 check passes.** `served` gives 0.495 on the mean of the repeats. That is the
  configuration the 15 Nov entry measured as 0.50 ± 0.03.
- **The served bars are optimistic.** They were fitted on these same out-of-fold rows.
  Refitting them per fold on the other folds keeps macro-F1, but false alarm doubles to 0.070.
  New candidates use `cross_fit`.
- **Narrow-repair records.** They come from the untracked cache
  `cache/counterfactual/evidence_extra.jsonl`. The narrow-repair stage fired on 26 real rows and
  was right on 22. It lifts OFF_BY_ONE real F1 from 0.33 to 0.51.
- **Class rules.** On real rows they fired twice, both wrong (`bl-t2-tr-223`, `bl-tr-016`). On
  synthetic rows they were right 86 of 87 times. This matches the plan's diagnosis (P4).
- **Classes too small to score.** ASSIGN_VS_COMPARE, MISSING_BASE_CASE and WRONG_LOOP_DIR have 1
  real row each and STALE_EXIT has 8, so the reports mark them "not estimable".
- **Real/synthetic split from the next retrain.** `metrics_v1.json` gains per-class out-of-fold
  scores split into real and synthetic rows (`per_class_real`, `per_class_synthetic`,
  `macro_f1_oof_real`). The served file is unchanged until then.

---

## 2026-11-22: Gate 4 decision: PR #17 merges (served model becomes 8860b506)

Decided by the rule in `docs/EVAL_PROTOCOL.md` section 6, written on 16 Nov before any of these
numbers existed, applied to the Gate 3 report (`reports/heldout_eval.md`, 662 shared rows of the
development set; reproduced to three decimals by Umaima on #21). Nothing in either model was
changed between that report and this decision.

| Full runtime | Problem-weighted macro-F1 | Precision when it names a class | False alarm on OTHER |
|---|---|---|---|
| audited (0af477c2), all rows | 0.627 | 0.804 (86/107) | 0.026 (12/460) |
| **#17 (8860b506), all rows** | **0.679** | **0.895 (85/95)** | **0.011 (5/460)** |
| audited, without tl-progpedia-00000039 | 0.641 | 0.683 (28/41) | 0.031 (9/290) |
| **#17, without tl-progpedia-00000039** | **0.695** | **0.806 (29/36)** | **0.017 (5/290)** |

Rule: higher problem-weighted macro-F1, precision not lower, false alarm not higher, in both
scopes. All six hold, so #17 merges. Row-weighted macro-F1 agrees (0.574 against 0.484; 0.541
against 0.480), so the 0.468 floor of the problem-weighted metric does not decide it.

What the decision does not establish, and what comes with the model:

- **Development evidence only.** The set has been scored many times, and the exclusion of the
  CodeNet RANGE_CHECK mutants (`stu-cn-rc-`) was chosen with its results (2026-11-14 and 11-15
  entries). The independent number is Gate 6, on the confirmatory set.
- **Recall is unchanged.** Named-class recall is 0.421 against 0.426 (85/202 against 86/202); #17
  abstains on 7.7% of rows against 0.5%. OFF_BY_ONE and RANGE_CHECK are still rarely caught.
- **Training composition:** 2,475 training rows, 1,367 real-source and 1,108 synthetic (44.8%,
  up from 40.7%), plus 205 dev-gold rows (`calibrator.json`, `variants.execution.fitted_on`). Row
  ids were not recorded (the model predates the trainer's row list); the manifest says so.
- **Deviations from the dataset master plan,** as listed in the protocol section 7: per-class
  bars (ARRAY_BOUNDS 0.50, INT_OVERFLOW 0.20, LOOP_BOUNDARY 0.20, UNINITIALIZED_VAR 0.55) where
  the plan allows one global threshold; the largest class holds 0.518 of training weight against
  a 0.15 cap; the RANGE_CHECK exclusion chosen with held-out results.
- **Served under the decision-source contract.** #17 was scored through its own code, which
  reported 1.0 for a rule decision. Merged onto main, its three rule stages report their measured
  precision instead: class rules 0.934 (126/129, mostly synthetic rows), repair-first 0.816
  (102/115), narrow repairs 0.722 (36/42). This changes no scored label: no rule decision in the
  run was cancelled by the missing-feature guard, the one place the old and new code differ. A
  narrow-repair decision now starts at hint level 1 (0.722 is under the 0.75 cut).
- **Run-record evidence was a stand-in.** The narrow repairs were scored from the 9 Nov second-set
  cache; the three narrow ops added on 15 Nov never fired in that evaluation.

Revert to the audited model (code stays; the rule stages stay; the bars come from the old
`calibrator.json`):

```bash
git checkout audit-2026-11-15 -- data/misconception_dataset/models
python scripts/make_model_golden.py
python scripts/make_dataset_manifest.py
```

---

## 2026-11-16: held-out report for both systems (no model change)

The held-out report now scores the classifier alone and the full runtime, through the same
`runtime_decision` the backend serves. It covers the served model and the PR #17 candidate on
the 662 rows both data versions share, overall, per class, per problem, and without
`tl-progpedia-00000039`. See `reports/heldout_eval.md`.

- The served model's classifier alone reproduces the supervisor's figures of 15 Nov: 75 of 104
  named predictions right, 75 of 204 named rows found, and 17 of 37 and 17 of 92 without
  problem 39.
- The served full runtime is right on 86 of 107 named predictions and finds 86 of 202 named rows
  (28 of 41 and 28 of 92 without problem 39). The repair-first rule decides 33 rows.
- Two development-set reads, both logged (`holdout_evaluations.jsonl`, tags `audited` and `pr17`).
- Problem-weighted macro-F1 has a floor of 0.468 on this set: 6 of the 22 problems have no named
  row, and always-OTHER scores 1.0 on each.

---

## 2026-11-16: rules for MISSING_BASE_CASE and WRONG_LOOP_DIR (same model files)

Real code almost never shows these two classes: 3 real rows in about 2,600, and none in the
held-out problems, so no model can be trained or scored on them with real data. They are now
decided by rules first (`evidence_rule_override` and `rule_override` in
`backend/app/diagnosis/xgb_classifier.py`); the model still names them when no rule fires.

| Rule | Dataset rows | Bank benchmark |
|---|---|---|
| MISSING_BASE_CASE: the compiler's `-Winfinite-recursion` warning | 43 of 43 right | 6 of 6 |
| MISSING_BASE_CASE: the base-case repair passes every test, the program recurses, and the first failing test crashed or timed out | 17 of 19 | 7 of 7 |
| (not used) the base-case repair passes with no crash or timeout | 4 of 14 | 0 of 1 |
| WRONG_LOOP_DIR: the downward-to-upward repair passes every test, also in a tie | 66 of 67 | 21 of 21 |
| WRONG_LOOP_DIR: the new upward-to-downward repair (`for_run_downward`) passes every test AND the output is the expected output reversed | no real row qualifies | not in the cached records |

- The rules were written from the class definitions and then counted; nothing was fitted. Nearly
  all of the evidence is synthetic, because that is the only evidence there is.
- A lone base-case repair (no crash, no timeout) used to name MISSING_BASE_CASE through the
  repair-first rule. It no longer does: it was right 4 times in 14.
- `for_run_downward` covers a task that wants the reverse order (bank CP11) written with an
  upward loop. On 2,233 real failing programs that edit made every test pass on up to 40, none
  of them WRONG_LOOP_DIR (33 were OTHER_ERROR), so it counts only with a reversed output, which
  none of those 40 printed.
- Scores are unchanged, because no rule fires on a held-out row and the bank programs of these
  classes were already right: held-out accuracy 0.778, macro-F1 0.582; bank 0.963 and 0.965.
- Checked through the live path: a recursion with no base case, a recursion that skips its base
  case for odd inputs, and an upward loop where the task wants a downward one all come out right.

Also measured, on grouped out-of-fold real training rows: lowering the OFF_BY_ONE bar does not
buy recall. From the current rule to a bar of 0.1, precision goes 0.77, 0.50 (0.5), 0.30 (0.3),
0.14 while recall goes 0.22, 0.23, 0.24, 0.27. The misses are not the model being cautious; the
features do not separate those programs from other wrong answers.

Two bank benchmark "errors" are label noise in the benchmark, not model errors: an off-by-one
edit that removes the `- 1` from a recursive call makes the recursion endless, and the system
calls that MISSING_BASE_CASE.

---

## 2026-11-15: regularised model on a wider bank + two more narrow repairs (served)

What changed, in the order it was done:

1. **Two more narrow repairs** (`scripts/repair_extra.py`, `NARROW_REPAIR_OPS`):
   `for_add_missing_step` (a `for` loop with no step whose body never writes the loop variable) for
   STALE_EXIT, and `range_test_swap_and_or` (`x >= 1 || x <= 10`: one variable tested from both
   sides with the wrong joiner) for RANGE_CHECK. On the 707 real CodeNet failures they had a
   candidate on 8 programs and fired on none; on the held-out rows they had a candidate on 68 and
   fired once, correctly.
2. **352 more bank training rows** (`annotations/tier0e_bank_student_cd.jsonl`, rows
   `stu-cpNN-cXX` / `-dXX`): two further beginner-style solutions per bank problem
   (`scripts/student_specs_c.py`), one injected bug per class
   (`scripts/build_bank_synthetic.py`), each verified by running the bank tests. Bank rows per
   class went from (A/B styles) INT_OVERFLOW 2, WRONG_LOOP_DIR 4, ARRAY_BOUNDS 8, STALE_EXIT 11 to
   10, 17, 15, 58. One generated row (`stu-cp26-c01`) was removed: its loop operator had matched
   the call `cost_for(` as a `for` loop, which `test_applicability` caught; the operators now
   require a real loop keyword. ARRAY_BOUNDS, INT_OVERFLOW and MISSING_BASE_CASE stay thin: few bank problems
   use fixed arrays, large values or recursion.
3. **Re-merge.** `merge_dataset.py` was run on the current lane files: 3,697 rows (3,352 before).
   Besides the 352 new rows it drops 7 old ones as `identical_code_tie` (identical programs whose
   labels disagree after the signed relabels of PR #11; the committed files had been edited by
   hand instead of re-merged). No label or split of a remaining row changed. The held-out test
   has 662 human-labelled rows (was 664).
4. **`plain_reg` profile** (`n_estimators=200, max_depth=4, learning_rate=0.1, subsample=0.7,
   colsample_bytree=0.5, min_child_weight=5, reg_lambda=10, gamma=0.5`), same rows and weights as
   `plain`. Why: on the real training rows `plain` fits at macro-F1 0.99 and scores 0.48 grouped
   out-of-fold; `plain_reg` fits at 0.80 and scores 0.53. Chosen among seven settings on two
   train-side checks only (grouped out-of-fold on real rows; bank programs with their solution
   style held out).
5. **The CodeNet RANGE_CHECK mutants are left out** (`PLAIN_EXCLUDED_PREFIXES = ("stu-cn-rc-",)`).
   With them the same profile named RANGE_CHECK at precision 0.31 on the held-out rows and raised
   false alarms to 3.9%; without them 1.00 and 1.5% (measured before the one-row correction above). This choice used held-out results (this
   entry and 2026-11-14), so it is not a blind one.

Served: `execution`, sha256 `8860b506160ed29c…`, temperature 1.0, abstain threshold 0.63, bars
ARRAY_BOUNDS 0.50, INT_OVERFLOW 0.20, LOOP_BOUNDARY 0.20, UNINITIALIZED_VAR 0.55. Trained on
2,680 rows (train 2,475, dev-gold 205); grouped cross-validation macro-F1 0.804 ± 0.022. On the
real out-of-fold rows alone the system scores macro-F1 0.50 with the bars (0.48 without); that
figure moved by 0.03 between two trainings that differed by one row, so read it as 0.50 ± 0.03.

**Bank benchmark** (`scripts/eval_bank_benchmark.py`, 273 verified single-edit bugs on the 40 bank
problems, none of them a training row; `reports/bank_benchmark.md`):

| System | Accuracy | Macro-F1 | Precision when it names one | Recall | False alarm on OTHER |
|---|---|---|---|---|---|
| 2026-11-14 system | 0.828 | 0.881 | 0.984 | 0.798 | 0/40 |
| + two repairs, old model | 0.967 | 0.970 | 0.991 | 0.961 | 0/40 |
| this entry | 0.963 | 0.965 | 0.982 | 0.957 | 0/40 |
| this entry, solution style held out of training | 0.953 | 0.943 | 0.976 | 0.942 | 0/40 |

Per class with the style held out (F1): ASSIGN_VS_COMPARE, INT_OVERFLOW, STALE_EXIT,
UNINITIALIZED_VAR, WRONG_LOOP_DIR 1.00; OTHER_ERROR 0.96; OFF_BY_ONE 0.95; LOOP_BOUNDARY 0.93;
RANGE_CHECK 0.90; ARRAY_BOUNDS 0.88; MISSING_BASE_CASE 0.75 (3 programs). These are upper
estimates: every bug is one clean edit to a correct solution, and the STALE_EXIT bugs have the
shape the new repair was written for.

**Held-out real problems** (662 rows, repair rules included in both columns):

| System | Accuracy | Macro-F1 | Precision when it names one | Recall | False alarm on OTHER | Abstain |
|---|---|---|---|---|---|---|
| old model (`0af477c2…`) | **0.816** | 0.525 | 0.807 (92/114) | 0.455 | 0.026 (12/460) | 0.003 |
| this entry | 0.778 | **0.582** | **0.896** (86/96) | 0.426 | **0.011** (5/460) | 0.077 |

Per class F1, old to new: ASSIGN_VS_COMPARE 0.86 to 1.00, LOOP_BOUNDARY 0.81 to 0.86, STALE_EXIT
0 to 0.33 (4 rows), OFF_BY_ONE 0.19 to 0.21, UNINITIALIZED_VAR 0.40 to 0.42, ARRAY_BOUNDS 0.73 to 0.70,
OTHER_ERROR 0.89 to 0.88; INT_OVERFLOW 0.63 and RANGE_CHECK 0.21 unchanged.

How to read it. The new model is more careful: when it names a misconception it is right more
often and it accuses fewer OTHER programs, but it abstains on 8% of outside programs (the rule
engine then decides), which is why plain accuracy is lower. Macro-F1 is +0.057, above the +0.05
the master plan calls meaningful, on a test set that has been scored many times; RANGE_CHECK and
OFF_BY_ONE on outside code are still caught about one time in ten. On the bank, which is what
students attempt, the two systems are level and both are far better than a week ago.

Revert to the previous model (code stays; the bars then come from the old `calibrator.json`):

```bash
git checkout <commit before this entry> -- data/misconception_dataset/models backend/tests/fixtures/model_golden.json
```

---

## 2026-11-14: per-class bars + narrow second-set repairs (same model files)

- The boosters are unchanged (execution sha256 `0af477c2…`, the 2026-11-09 revert point). Two
  decision rules were added around the model:
  1. **Per-class bars** (`class_thresholds` in `calibrator.json`, `decide` in
     `backend/app/diagnosis/xgb_classifier.py`): INT_OVERFLOW 0.15 and LOOP_BOUNDARY 0.15. A class
     that clears its bar is reported even when OTHER_ERROR is more probable. Fitted by
     `scripts/tune_class_thresholds.py` on grouped out-of-fold predictions over the training
     problems only (1,368 real rows); a bar is kept only at precision 0.5 or more, with a class F1
     gain and no macro-F1 loss. Out-of-fold macro-F1 0.467 to 0.480.
  2. **Narrow second-set repairs** (`NARROW_REPAIR_OPS`; the worker writes `cf_narrow`): when no
     first-set repair passes every test, four `repair_extra` edits may name a class
     (`enlarge_every_array`, `output_+-1_added`, `chained_compare_split_all`, `while_add_update`).
     Chosen from the cached second-set evidence on train + dev problems, where they were right on
     16/18, 17/21, 2/2 and 1/1 real rows. The rest of that set stays unused (it passes every test
     on many OTHER rows, see docs/6-nov.md section 16).
- Held-out problems, same 664 rows, repair-first rule included in every column:

| System | Accuracy | Macro-F1 | Precision when it names one | Recall | False alarm on OTHER |
|---|---|---|---|---|---|
| before | 0.804 | 0.480 | 0.796 (86/108) | 0.422 | 0.026 (12/460) |
| + bars | 0.807 | 0.492 | 0.793 (88/111) | 0.431 | 0.026 |
| + bars + narrow repairs | **0.812** | **0.513** | 0.798 (91/114) | 0.446 | 0.026 |

  Per class (F1 before to after): INT_OVERFLOW 0.53 to 0.63, LOOP_BOUNDARY 0.80 to 0.81,
  OFF_BY_ONE 0.14 to 0.19, RANGE_CHECK 0 to 0.15 (2 of 24), OTHER_ERROR 0.88 to 0.89; ARRAY_BOUNDS
  0.73, ASSIGN_VS_COMPARE 0.86, UNINITIALIZED_VAR 0.37 and STALE_EXIT 0 (4 rows) unchanged.
- How to read it: +0.033 macro-F1 is below the +0.05 the master plan calls meaningful, and this
  held-out set has been scored many times, so treat it as directional. It is kept because both
  rules were fixed on training problems, false alarms did not rise, and each named class comes
  with a reason (a bar, or the edit that passes every test).
- Deviations from the master plan (section 11): it allows one global threshold because dev-gold
  has about five rows per class; these bars are fitted on out-of-fold training rows instead.
- The narrow numbers come from cached evidence where the full second set ran first; live, only
  the narrow edits run, so a narrow edit can fire where an earlier wide edit used to stop the
  search. Expect slightly more narrow hits than measured.
- Revert: remove `class_thresholds` from `calibrator.json` (the model then uses the global
  threshold), and `git checkout <previous commit> -- backend/app/analysis/model_runner.py` to drop
  the narrow rule.

Also tried on 2026-11-13/14 and **not** served:

- Class weights (none / sqrt / full, real-only sqrt, OTHER down-weighted): "none" won on grouped
  cross-validation; the others raise rare-class recall and lower precision.
- Real-code mutants without the RANGE_CHECK ones (`stu-cn-*`, agent CodeNet rows removed):
  cross-validation macro-F1 0.79, but on the held-out rows at its own threshold (0.66) accuracy
  0.753, macro-F1 0.475, INT_OVERFLOW 0 of 9, 11% abstained. Roughly level with the served model
  at 0.44. With RANGE_CHECK mutants it flagged 58% of OTHER programs on the held-out CodeNet
  problems.
- Mining: 16,520 real CodeNet programs on 9 training problems gave 20 new repair-verified bugs
  (13 RANGE_CHECK, 6 ASSIGN_VS_COMPARE, 1 WRONG_LOOP_DIR); served model 15/20, mutant model 16/20.

---

## 2026-11-09: sqrt class weights + CodeNet data (rejected, not served)

- Trained on 2,185 rows: the revert-point data plus 707 agent-labelled CodeNet failures (9 training
  problems) and 268 verified single-edit CodeNet mutants for the rare classes, with sqrt class weights
  (picked over none/full by grouped cross-validation on the training problems only).
- Cross-validation looked better (execution macro-F1 0.765 vs 0.70), and the largest class fell from
  56% to 27% of the training weight.
- On the held-out problems it was worse than the revert point, on the same 664 rows:

| Model | Accuracy | Precision when it names one | Recall | False alarm on OTHER | Abstain |
|---|---|---|---|---|---|
| revert point (threshold 0.44) | **0.788** | 0.721 (75/104) | 0.368 | 0.026 | 0.008 |
| this model (its threshold 0.75) | 0.595 | 0.902 (74/82) | 0.363 | 0.015 | 0.307 |
| this model, no threshold | 0.762 | 0.608 (93/153) | 0.456 | 0.102 | 0 |

  On the two held-out CodeNet problems it flagged 31% of the OTHER programs (the revert point: 3%).
  The mutants and class weights taught patterns that real code does not share. Model sha256
  `8c7c9a7095ba3724…`; files not committed.

---

## 2026-11-09: plain profile, execution variant (revert point)

- Commit: the commit that adds this entry (`git log -- docs/MODEL_LOG.md`).
- Taxonomy tl-cpp-v2, 11 labels; trainer `scripts/train_xgb_misconception.py --profile plain`
  (no class weights); 1,349 training rows.
- Served variant: `execution` (temperature 1.4, abstain threshold 0.44).
- Grouped cross-validation on the training problems: macro-F1 0.70 (out of fold), 0.68 ± fold spread.

Held-out problems (525 real failing programs on 20 problems never seen in training; labels are the
independent annotator agents' consensus; `data/misconception_dataset/reports/heldout_eval.md`):

| System | Accuracy | Precision when it names a misconception | Misconception recall | False alarm on OTHER |
|---|---|---|---|---|
| Always OTHER_ERROR | 0.667 | – | 0.000 | 0.000 |
| **execution** | **0.785** | **0.807** (71/88) [0.71, 0.88] | 0.406 (71/175) | 0.026 (9/350) |
| best (old default) | 0.659 | 0.143 (1/7) | 0.006 | 0.014 |

With the two held-out CodeNet problems added (664 rows, 22 problems): accuracy 0.788, precision
0.721 (75/104), recall 0.368. On those CodeNet problems alone precision is 0.25 (4/16): the model
is weaker on problem styles it has not seen.

What it means: when this model names a misconception it agrees with the annotators about 4 times in 5,
but it names one for only about 2 in 5 of the programs that have one.

Through the real submission path with the shipped defaults (`model_first`, execution variant, run
records on): a simulated classroom of 7 students, 161 verified attempts. On the 116 failing attempts
it reached accuracy 0.759, precision 0.787 (63/80) and recall 0.778 (63/81). Across all 161 attempts
accuracy is 0.826, and every one of the 45 correct programs was left clean. The old rule-engine default
scored precision 0.400 on the same attempts. It still names a misconception for 9 of the 35 OTHER
failures. Each diagnosis takes about 48 s, so it runs on the background worker.

Files (sha256):

| File | sha256 |
|---|---|
| xgb_execution_v1.json | 0af477c27ce3955dd9343bb5db2f47aa46778c2816c370bdc20af35bb98790e2 |
| xgb_best_v1.json | faba7929e8cc617ec9f67154fb828d31898b4ce17b1cf78cf48c2121d60dc5cc |
| xgb_common_v1.json | 98a71f1c1a0dce9f4edfb024b4799afe05359bdcdad74674666382370982006a |
| xgb_v1.json / xgb_masked_v1.json | eb6566ac5e923cc7513e9948a24ed25c66675cc83012614954fb7cc1d34343bc |
| calibrator.json | ddc9489364f39934d101d445439db7d2ed315bddbca46decdd525b9a5ec1190e |
| label_encoder.json | 5b0628c4f9a183d56f4854efe273e32ce14f45e52fc0afcaeef40b2d5551901a |
| metrics_v1.json | d0fd18fdde6528f46dbb0919fde9672562213423e0b61e55fef1a3ebed5e81a7 |

Data files at tag `audit-2026-11-15` (`c62f8ba`), computed with
`git show audit-2026-11-15:<path> | sha256sum` (added 20 November):

| File | sha256 |
|---|---|
| annotations/labels.jsonl | 460729f9fba6ff161d6993c4ea3761b014fc1b0ecabc498519c4e3f046ce58bf |
| features/features.csv | 7e0b6e1291f648bd77a705ab69f58d203afce1ed2e6e85211711b8ea9b8f59ca |
| splits/splits.csv | 8f340a4b7d06a99ab110e85750205183db4563d79ca10c61f4866222720de40f |

What this cannot prove. The served model was trained on 1,349 rows (`n_train` in `metrics_v1.json`,
with 208 dev-gold rows held out, 1,557 in all). The ids of those rows were never recorded. Selecting
rows the way the plain profile does (train split, human-labelled real rows, the three allowed
synthetic families) from the files at the tag gives 2,184 train rows (1,368 real-source, 816
synthetic), not 1,349. The data files were re-merged after the model was trained, so the hashes above
identify the pool as committed, not the rows the model used. The split of the 1,349 into 800
real-source and 549 synthetic comes from the team's work plan of 16 November and cannot be checked
from the committed files. Models trained from now on write `training_row_ids.txt` and list its hash in
`dataset_manifest.json`, so this limit applies to this model only.
