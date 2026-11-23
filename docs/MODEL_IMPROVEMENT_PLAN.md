# TraceLearn model improvement plan

22 November 2026 · Rayaan. Working copy of the shared plan document; changes are made here by pull request.

## Goal

The model does well on classes it has seen in real code and poorly on classes it has mostly seen in synthetic code. The fix is to close that synthetic-to-real gap class by class, and to measure every class in a way that can be trusted, without spending the development set to do it.

"Fixed" means all of the following, measured on **real rows only**:

| Measure | Now (served model, 8860b506) | Target | Where it is measured |
| --- | --- | --- | --- |
| Macro-F1, grouped out-of-fold, real training-side rows | 0.50 (±0.03 between trainings) | 0.55 or more | Phase 0 harness, training side |
| Recall at precision 0.70 or more, OFF_BY_ONE | 0.22 (at precision 0.77) | 0.35 | same |
| Recall at precision 0.70 or more, RANGE_CHECK | 0.08 on the development set; out-of-fold not yet measured | 0.30 | same |
| False alarm on real OTHER_ERROR rows | 0.011 on the development set | 0.03 or less | same, and the one development-set read |
| Gap between all-row and real-row out-of-fold F1, per class | up to 0.50 (RANGE_CHECK) | under 0.15 for every class with 20+ real rows | same |
| False alarm of the class rules on real code | 2 wrong fires in 1,584 real rows | 0 confirmed wrong fires after review | Phase 4 |
| Per-class reporting | single numbers, even on 3 rows | interval on every cell; under 10 rows marked "not estimable" | every report |

The targets are proposals for the supervisor to agree. The +0.05 on macro-F1 is the dataset master plan's own minimal meaningful difference. The final, independent check is the confirmatory set at Gate 6; nothing in this plan replaces it.

The plan does not promise a number on the development set. That set has been read many times, so it is used once per finished candidate, to confirm a direction that the training-side numbers already show.

## Diagnosis

The weak classes are the ones whose training rows are mostly synthetic. The model learns what the generator's bugs look like and does not recognise students' bugs.

| Class | Real / synthetic training rows | Out-of-fold F1 (all rows) | Development-set F1 (real) | Gap |
| --- | --- | --- | --- | --- |
| ARRAY_BOUNDS | 102 / 31 | 0.70 | 0.70 | 0.00 |
| LOOP_BOUNDARY | 26 / 175 | 0.88 | 0.86 | 0.02 |
| INT_OVERFLOW | 66 / 67 | 0.93 | 0.62 | 0.31 |
| OFF_BY_ONE | 92 / 167 | 0.53 | 0.20 | 0.33 |
| UNINITIALIZED_VAR | 55 / 89 | 0.71 | 0.42 | 0.29 |
| STALE_EXIT | 8 / 141 | 0.77 | 0.33 (4 rows) | 0.44 |
| RANGE_CHECK | 27 / 191 | 0.65 | 0.15 | 0.50 |
| ASSIGN_VS_COMPARE | 1 / 131 | 0.97 | 1.00 (3 rows) | not estimable |
| WRONG_LOOP_DIR | 1 / 100 | 0.90 | no rows | not estimable |
| MISSING_BASE_CASE | 2 / 67 | 0.76 | no rows | not estimable |
| OTHER_ERROR | 998 / 257 | 0.86 | 0.88 | none |

The out-of-fold column scores all training rows together, so for synthetic-heavy classes it mostly measures the synthetic rows. That number has been the one used to choose models, and it hides the gap. LOOP_BOUNDARY is the exception: it probably transfers well because its repair-first rule decides it from execution, not from code style.

### Five findings behind the plan

1. **Style separates synthetic from real code almost perfectly.** The adversarial check (`scripts/eval_shift.py`, 6 Nov) told training rows from unseen real code with AUC 0.98, and 0.96 using real training rows only; the gate is under 0.75. The strongest single features were loop count, increments and indentation depth. Those are style, not bugs. It was run on the retired `best` and `common` variants and has not been run on the served `execution` model.
2. **Reweighting has been tried and does not help.** Square-root and full class weights raised rare-class recall on training folds and lost on real code twice (`docs/MODEL_LOG.md`, 9 and 14 November). Class weight is not the lever. OTHER_ERROR holds 0.518 of the training weight, which is a symptom, not the cause.
3. **Thresholds do not buy OFF_BY_ONE recall.** Lowering its bar to 0.1 moves precision from 0.77 to 0.14 for recall from 0.22 to 0.27 on real out-of-fold rows. The features do not separate those programs. Some off-by-one evidence already exists (`evidence.all_deltas_pm1`, `evidence.fr_pm1`, `tests.boundary_fail_count`), so the first question is whether those signals reach the served model, not which new ones to add.
4. **Regularisation helped once.** `plain` fits real training rows at macro-F1 0.99 and scores 0.48 out-of-fold; `plain_reg` fits at 0.80 and scores 0.53. Overfitting to the training rows is real, and it was measured the right way, on real rows.
5. **The rule classes are untested on real code.** On training-side rows the MISSING_BASE_CASE and WRONG_LOOP_DIR rules are right 115 of 116 times on synthetic rows. On 1,584 real rows they fired twice, both against the recorded label (`bl-t2-tr-223`, `bl-tr-016`, both OTHER_ERROR), and caught none of the 3 real positives. Their served confidence of 0.934 rests on synthetic evidence.

### Why tables showed perfect scores

A cell like ASSIGN_VS_COMPARE 1.00 is 3 correct out of 3. Its 95% interval runs from 0.44 to 1.00. That is not overfitting, it is a sample too small to say anything, and it should not be printed as a single number.

## Ground rules

Every choice in this plan is made on training-side real rows. The development set is read once per finished candidate, and the confirmatory set only at Gate 6. These follow `docs/EVAL_PROTOCOL.md` sections 5 and 8.

- **The selection score is real-row out-of-fold.** Grouped by problem cluster, 3 folds, 3 repeats, scored on non-synthetic train and dev-gold rows only. All-row out-of-fold is still reported, beside it, never instead of it.
- **Two numbers on every candidate.** Real-row macro-F1 with its spread across repeats, and the false alarm on real OTHER_ERROR rows. A candidate that raises one and breaks the other is rejected.
- **A change has to beat the noise.** Two trainings that differed by one row moved real-row macro-F1 by 0.03. A candidate counts as better only if it beats the served model by more than the spread of both across repeats.
- **One development-set read per finished candidate.** Logged in `holdout_evaluations.jsonl` and the protocol's exposure table. Nothing is changed in response to that read except the merge decision, which uses the protocol's section 6 rule.
- **Every candidate gets a `docs/MODEL_LOG.md` entry, rejected ones included.** Training composition (real and synthetic counts per class), what changed, both numbers.
- **Synthetic data is allowed, but must earn its place on real rows.** A synthetic family stays only if removing it lowers real-row out-of-fold F1.
- **Nothing is fitted on the rows a class is scored on.** For per-class decisions (bars, caps, multipliers) the inner folds choose and the outer folds score.

## Phases

```
P0 Measure ──┬── P1 Synthetic to real (share, weight, style features) ──┐
(real-row    ├── P2 Features (off-by-one and range signals) ────────────┤
 harness,    ├── P3 Real rows (mine repair-verified bugs) ──────────────┼── P5 Candidate ── Gate 6
 reports)    └── P4 Rule classes (real false alarms, fresh test) ───────┘   (one dev read,   (confirmatory,
                                                                             merge rule)      scored once)
```

P0 comes first because every later phase is judged by its harness. P1 to P4 are independent and can be split between the three of you. P5 combines whatever passed into one candidate and spends one development-set read on it; the confirmatory set at Gate 6 gives the independent number.

## Phase details

### P0. Measure on real rows

**Context.** Models have been chosen on all-row out-of-fold scores, which for synthetic-heavy classes mostly score synthetic rows. `scripts/select_model_profile.py` already computes a real-row score, but only for profiles and only on the retired `best` columns. `scripts/tune_class_thresholds.py` has the grouped out-of-fold loop for the `execution` variant.

**How.**

1. Write one candidate harness, `scripts/eval_candidate_oof.py`, from those two scripts. It takes a candidate described as data: profile, synthetic families and weights, feature list, bars. It trains in grouped folds (problem cluster, 3 folds, 3 repeats) and scores the **full runtime** through `runtime_decision`, rules and bars included, with bars fitted in inner folds only.
2. Score on real train and dev-gold rows: macro-F1 with its spread across repeats; per class precision, recall, F1 with Wilson intervals; false alarm on real OTHER_ERROR rows; how often each rule stage fires and how often it is right. Report the all-row numbers beside them.
3. Write one JSON per candidate under `reports/candidates/` and a comparison table.
4. Fix the reports. In `heldout_eval.md` and every per-class table, show the interval and print "not estimable" when support is under 10. Add a column with each class's real and synthetic training rows. Add the rule stages' false alarm on real rows.
5. Split `metrics_v1.json` per-class out-of-fold scores into real and synthetic rows, so the gap is visible on every retrain.

**Passing check.** The harness, run on the served configuration, gives real-row macro-F1 within 0.50 ± 0.03, the figure the 15 Nov training recorded. A second person reproduces it. The report shows "not estimable" for ASSIGN_VS_COMPARE and STALE_EXIT.

### P1. Close the synthetic-to-real gap

**Context.** Adversarial validation separated synthetic from real code with AUC 0.98, mostly on style features. Class weights failed twice; regularisation helped once.

**How.** Each item is a candidate scored by the P0 harness, never by the development set.

1. Re-run `scripts/eval_shift.py` on the `execution` variant, comparing real training rows with synthetic training rows. List the features that separate them most.
2. **Synthetic weight per class.** Sweep the synthetic weight in {0, 0.25, 0.5, 1}. Lower it first for classes that have 50 or more real rows (OFF_BY_ONE, UNINITIALIZED_VAR, INT_OVERFLOW, ARRAY_BOUNDS), and keep it for classes with almost no real rows, where synthetic rows are the only signal.
3. **Synthetic cap.** Limit synthetic to real rows per class, for example 3 to 1, sampling synthetic rows by problem cluster so whole families are kept or dropped together.
4. **Style features.** Train without the features that top the adversarial list (loop count, increment counts, indentation depth and similar), or with them masked for synthetic rows only.
5. **Reference point.** Train a real-only model. If it matches the mixed model on real rows, the synthetic rows are not earning their place.

**Passing check.** At least one configuration beats the served model's real-row macro-F1 by more than the spread of both, with false alarm at or under 0.03, and narrows the gap for at least two of OFF_BY_ONE, RANGE_CHECK and UNINITIALIZED_VAR. Every configuration tried is logged, including the ones that lose.

### P2. Features for the classes the model cannot see

**Context.** The off-by-one and range signals partly exist already: `evidence.all_deltas_pm1`, `evidence.fr_pm1`, `evidence.tok_delta`, `evidence.sign_delta` and `tests.boundary_fail_count`. Lowering the OFF_BY_ONE bar shows the model cannot separate those programs, which means either the signals do not reach the served variant or they are too weak on real code.

**How.**

1. **Audit before adding.** For each existing signal, check that it is in the `execution` feature list (`metrics_v1.json`), how often it is present on real rows, its distribution for the class against OTHER_ERROR on real rows, and its gain in the model.
2. **Add only what the audit says is missing.** Candidates to test, not decisions:
   - **OFF_BY_ONE:** output length off by exactly one element; loop bound written as `n` where `n - 1` is used elsewhere for the same array.
   - **RANGE_CHECK:** the first failing input is the problem's smallest or largest value while the inner tests pass; a comparison against a constant that, flipped from `<` to `<=`, passes the first failing test.
   - **UNINITIALIZED_VAR:** output that changes between `-ftrivial-auto-var-init=zero` and `=pattern`, which `counterfactual_evidence.py` already measures; confirm it is a feature.
   - **STALE_EXIT:** a timeout on the first failing test with a loop whose variable is never written in its body.
3. **Parity first.** A new feature enters the training data and the live run record in the same change, with a test that one program gets the same value both ways. Repair-generator changes alter the served model's input, as the held-back E7 work showed.
4. Score each feature group as a candidate with the P0 harness.

**Passing check.** For the targeted class, real-row recall at precision 0.70 or more rises by more than the spread, and no other class's real-row F1 drops by more than 0.05. The parity test passes in CI.

### P3. More real rows for rare classes

**Context.** STALE_EXIT has 8 real training rows, ASSIGN_VS_COMPARE 1, WRONG_LOOP_DIR 1 and MISSING_BASE_CASE 2. Mining 16,520 CodeNet programs on 9 training problems found 20 repair-verified bugs. The local raw copy holds submissions for 70 CodeNet problems only.

**How.**

1. **Reserve before mining.** Gate 5 takes its problems first, from `confirmatory/candidates_v1.csv`. Mining uses only problems that are neither used nor reserved, so the confirmatory set stays untouched.
2. **Label by execution, not by agents.** A row joins as `repair_verified` only when exactly one class's single repair makes every test pass. Its provenance goes in the U1 sidecar, so it is never counted as human-reviewed.
3. **Priority:** RANGE_CHECK, STALE_EXIT, UNINITIALIZED_VAR, ASSIGN_VS_COMPARE, then OFF_BY_ONE. Target problems whose task invites the bug: range validation, loops with an exit condition, recursion, reverse-order output.
4. **More data if needed.** The full CodeNet archive has about 4,000 problems; only 70 are local. Copying more is the same request as Gate 5.
5. Re-merge, regenerate features, manifest and sidecar, and re-run the P0 harness.

**Passing check.** Every priority class has at least 30 real training rows, or the log says how many problems were mined and why it stopped. The new rows sit in training-split clusters only, and a person has spot-checked one in five (the manual track).

### P4. The rule classes: MISSING_BASE_CASE and WRONG_LOOP_DIR

**Context.** Both classes are decided by rules since #17. On real training-side rows the rules fired twice, both against the recorded label, and missed the 3 real positives. Their served confidence (0.934) comes from synthetic rows.

**How.**

1. **Look at the two real fires** (`bl-t2-tr-223`, `bl-tr-016`). Either the rule or the label is wrong. That review is on the manual track; record the outcome either way.
2. **Measure real false alarms everywhere.** Fires on real rows go in every report, split by class rule, repair and narrow repair.
3. **Separate real and synthetic evidence in the confidence.** Count real-row precision separately in `RULE_STAGE_PRECISION`. Proposal for the team: while a stage has fewer than 10 real fires, it keeps its synthetic-based confidence but is flagged "synthetic evidence" in the stored record and the teacher panel.
4. **An independent synthetic test set.** Eman and Umaima write about 20 buggy programs per class by hand on bank-style problems, without looking at the generators, plus about 40 correct or other-error programs that look similar: recursion with a base case, deliberate downward loops. Freeze it with a hash, score it once, and report it as synthetic.
5. **Real positives.** Fold recursion and reverse-order problems into P3's mining.

**Passing check.** The two fires are reviewed; real false alarms appear in the report; the hand-written set is frozen and scored once, with recall and false alarm committed.

### P5. One candidate, one read, one decision

**Context.** This is Gate 4 again for the improved model.

**How.**

1. Combine the changes that passed P1 to P3 into one configuration. Train it into a scratch folder and score it with the P0 harness.
2. If it beats the served model on real rows by more than the spread, run `eval_heldout_rows.py run` once and log the read.
3. Apply the protocol's section 6 rule, write the `MODEL_LOG` entry, and merge or close by that rule. Have it reproduced by a second person.

**Passing check.** The same as Gate 4: the decision quotes the rule and the numbers, CI is green, and the entry exists whichever way it goes.

## Per-class plan

Each class gets the lever that matches why it fails, and a measure it can actually be judged on. Classes with almost no real rows are judged on real false alarms and an independent synthetic set, not on recall from rows that do not exist.

| Class | Why it is weak now | Lever | Judged on |
| --- | --- | --- | --- |
| OFF_BY_ONE | 92 real rows, but features do not separate it from other wrong answers | P2 features, then P1 synthetic weight | Real-row recall at precision 0.70 or more: 0.22 now, target 0.35 |
| RANGE_CHECK | 27 real against 191 synthetic; largest gap | P1 cap and weight, P2 boundary-input features, P3 real rows | Real-row recall at precision 0.70 or more: target 0.30 |
| UNINITIALIZED_VAR | 55 real rows, gap 0.29 | P2 confirm the zero-versus-pattern signal reaches the model, P1 weight | Real-row F1, gap under 0.15 |
| STALE_EXIT | 8 real rows | P3 real rows first, then P2 timeout features | Real-row recall once there are 30 or more rows; until then, not estimable |
| INT_OVERFLOW | 66 real rows, gap 0.31, 9 development-set rows | P1 weight | Real-row F1, gap under 0.15 |
| ARRAY_BOUNDS | No gap; recall 0.55 at precision 0.96 | Leave alone; watch for regressions | Real-row F1 does not drop by more than 0.05 |
| LOOP_BOUNDARY | Transfers well (0.86) | Leave alone; watch for regressions | Real-row F1 does not drop by more than 0.05 |
| ASSIGN_VS_COMPARE | 1 real training row; 3 development-set rows | P3 real rows; P4-style hand-written test | Real false alarm; independent synthetic recall |
| MISSING_BASE_CASE | 2 real rows; rule-decided; real fires untested | P4 | Real false alarm; independent synthetic recall |
| WRONG_LOOP_DIR | 1 real row; rule-decided; one wrong real fire | P4 | Real false alarm; independent synthetic recall |
| OTHER_ERROR | 998 real rows, holds 0.518 of training weight | None directly; it is the false-alarm guard | False alarm on real OTHER_ERROR stays at 0.03 or less |

OFF_BY_ONE and LOOP_BOUNDARY overlap: both repairs pass on the 19 conflict rows. If P2 cannot separate them, reporting them as one family is an option the dataset master plan allows, but it changes the taxonomy and is the supervisor's call.

## Owners and order

Rayaan owns the model side, Eman the measurement and the hand-written test, Umaima the data. Day targets are proposals, counted from the day P0 starts.

| Work | Owner | Reviewer | Needs | Target |
| --- | --- | --- | --- | --- |
| P0 candidate harness (`eval_candidate_oof.py`), baseline reproduced | Rayaan | Umaima reproduces | nothing | Day 3 |
| P0 report fixes: intervals, "not estimable", composition, rule false alarms | Eman | Rayaan | nothing | Day 3 |
| P0 real and synthetic split of per-class out-of-fold in `metrics_v1.json` | Rayaan | Eman | nothing | Day 3 |
| P1 adversarial re-run on `execution`, synthetic weight, cap, style-feature candidates | Rayaan | Umaima | P0 | Day 7 |
| P2 audit of existing signals | Eman | Rayaan | P0 | Day 5 |
| P2 new features with parity tests | Rayaan, Eman | each other | P2 audit | Day 10 |
| P3 reserve Gate 5 problems, then mine training-side problems | Umaima | Rayaan | Gate 5 reservation | Day 10 |
| P4 review of the two real fires | Rayaan (manual track) | Umaima | nothing | Day 2 |
| P4 hand-written test set for MISSING_BASE_CASE, WRONG_LOOP_DIR, ASSIGN_VS_COMPARE | Eman, Umaima | Rayaan | nothing | Day 8 |
| P5 combined candidate, one development-set read, decision | Rayaan | Umaima | P1 to P3 | Day 12 |

P4's review and hand-written set can start at once; they need nothing from the harness. The confirmatory set (Gate 5 and Gate 6) runs on its own track and is not delayed by this plan.

## What we will not do

- **Re-run class weights.** Square-root and full weights lost on real code twice. They come back only with a new reason and a P0 score.
- **Lower thresholds for recall.** For OFF_BY_ONE that trades 0.63 of precision for 0.05 of recall.
- **Tune on the development set.** One read per finished candidate, logged.
- **Fill classes with generated rows to balance counts.** That is what created the gap. Synthetic rows stay only where they raise real-row scores.
- **Quote a per-class number on fewer than 10 rows** without its interval.
- **Take mining rows from the confirmatory problems.**

## Decisions for the supervisor

- [ ] The targets in the Goal table, especially real-row macro-F1 0.55 and the per-class recall targets.
- [ ] Whether real-row out-of-fold macro-F1 replaces all-row out-of-fold as the model-selection score.
- [ ] Copying more of the CodeNet archive, which both P3 and Gate 5 need.
- [ ] Whether rule-decided classes may serve with synthetic-only evidence, flagged as such.
- [ ] Whether OFF_BY_ONE and LOOP_BOUNDARY may be reported as one family if P2 cannot separate them.

## Sources

Figures from `main` at `cf20938` (22 Nov 2026): `reports/heldout_eval.json` (Gate 3 report), `models/metrics_v1.json` and `calibrator.json` (served model `8860b506`), `annotations/labels.jsonl` with `splits/splits.csv`, `reports/shift_dev_gold.md` (6 Nov), and `docs/MODEL_LOG.md` entries of 9, 14, 15 and 22 November. The real-row rule fires were computed on 22 Nov from `features/features.csv` on train and dev-gold rows only.
