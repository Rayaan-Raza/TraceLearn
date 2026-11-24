# Strategies for the weak classes and the OTHER_ERROR sink

24 November 2026 · branch `feat/weak-class-strategy`. Builds on `MODEL_IMPROVEMENT_PLAN.md` (P2, P3)
and `CLASS_BALANCE_PLAN.md` (branch `feat/class-ratio-2x`).

**Exposure.** The analysis in "What the evidence shows" uses training-side rows only (train and
dev-gold, real programs). But the first table is from the held-out split, and before choosing these
directions its per-row errors were inspected: the confusion of the `pr17` run, and the repair and
warning features of the missed OFF_BY_ONE, RANGE_CHECK and UNINITIALIZED_VAR rows. So the choice of
classes and strategies is **not blind** to the development set. It is in the exposure log
(`EVAL_PROTOCOL.md` section 8); only the confirmatory set (Gate 6) can give an independent number.

## The problem in one table

Held-out read of the served model (`pr17`, 662 programs): of the 516 programs it called
OTHER_ERROR, 87 were bugs of another class.

| True class | Called OTHER_ERROR | Found |
|---|---:|---:|
| ARRAY_BOUNDS | 27 | 53 of 96 |
| OFF_BY_ONE | 27 | 4 of 35 |
| RANGE_CHECK | 20 | 2 of 24 |
| UNINITIALIZED_VAR | 7 | 5 of 16 |
| INT_OVERFLOW | 4 | 5 of 9 |
| LOOP_BOUNDARY | 2 | 12 of 15 |

OTHER_ERROR rows themselves are mostly right (429 of 460, 5 flagged as another class, 26 abstained). Its precision of 0.83 is these 87
missed bugs. Fixing the weak classes and fixing OTHER_ERROR are the same job.

## What the evidence shows

### 1. The model already has the signals

The cached run records (`cache/counterfactual/evidence.jsonl`, 3,591 programs) hold per-test results,
output diffs, sanitizer reports and every class's repair attempts. The served features already
carry them: the partial-fix gain (`repair.*_gain`, identical to the cache's `best_gain`), the ±1
output signals (`evidence.fr_pm1`, `all_deltas_pm1`), the sanitizer (`evidence.sa_*`) and the
uninitialised-variable warnings. New features computed from the same cache would add little.

### 2. Some labels may conflict with the guideline's test (a lead, not a finding)

The guideline (section 2): *label the misconception that explains the first failing test; if you fixed
only that one thing, the first failing test would pass*, and it must be the cause. The cache
records whether a class's single edit passes that test (`repair.<class>_fix_first`). Among 1,137 real
OTHER_ERROR rows, exactly one class's edit does on 105 (96 agent consensus, 9 blind review):

| Class of the edit | OTHER_ERROR rows | ...some passing edit breaks no passing test | ...more tests pass overall | ...every test passes |
|---|---:|---:|---:|---:|
| OFF_BY_ONE | 73 | 21 | 25 | 0 |
| LOOP_BOUNDARY | 22 | 8 | 9 | 0 |
| INT_OVERFLOW | 9 | 8 | 8 | 1 |
| UNINITIALIZED_VAR | 1 | 1 | 1 | 0 |

Read it with these limits:

- **Most are probably coincidences.** 52 of the 73 off-by-one cases pass the first failing test only by
  breaking a test that passed, and none fixes the program. The 38 rows in the third column (21 + 8 + 8
  + 1) are the stronger leads.
- **Base rates.** Only-OFF_BY_ONE evidence is on 73 of 1,137 OTHER_ERROR rows (6%) and 21 of 104
  OFF_BY_ONE rows (20%). It still points to OFF_BY_ONE, about three times as often per row; OTHER_ERROR
  has more in absolute terms because it is 11 times larger. So this does not show that the labels
  taught the model the opposite, or explain OFF_BY_ONE recall.
- No label is shown to be wrong until a person reads the program.

### 3. Other classes, measured as rules on real rows

| Evidence | Class | Fires | Precision | Recall |
|---|---|---:|---:|---:|
| array repair gains a failing test (`repair.array_bounds_gain > 0`) | ARRAY_BOUNDS | 40 | **0.95** | 0.27 |
| range repair gains a failing test | RANGE_CHECK | 6 | 0.83 | 0.17 |
| zero-initialising fixes it (`repair.uninit_zero_fixes`) | UNINITIALIZED_VAR | 36 | 0.67 | 0.40 |
| uninit warning and output differs by init | UNINITIALIZED_VAR | 41 | 0.59 | 0.40 |
| sanitizer out-of-bounds report | ARRAY_BOUNDS | 200 | 0.40 | 0.57 |
| off-by-one repair gains a failing test | OFF_BY_ONE | 144 | 0.26 | 0.36 |

The sanitizer's 77 OTHER_ERROR hits are expected: the guideline labels a crash caused by another
bug as OTHER_ERROR. RANGE_CHECK has almost no usable evidence: its repair has a candidate edit on
only 48% of its rows.

## Strategies, in order

### S1. Review the 105 OTHER_ERROR labels in question (cheap; effect unknown)

- **What:** a review sheet of the 105 training-side rows, each showing the code, the first
  failing test, the expected and actual output, and the one edit that makes that test pass.
  The reviewer applies the guideline: is that edit the cause (relabel) or a coincidence (keep
  OTHER_ERROR, with a note)?
- **Who:** the team's manual track (Umaima labels, Eman reviews, as in Gate 1). Model predictions
  are not shown. Relabels are recorded with provenance (`label_origin: human_review`,
  `reviewed_by`) in `label_review_decisions.jsonl`, never by editing labels in place.
- **Expected effect:** unknown. The upper bound is OFF_BY_ONE 104 to 177 rows; the stronger leads give at
  most 21 more. It is worth doing to settle the label question, not as a promised gain.
- **Scored:** re-merge, retrain, the P0 harness on real rows, then one held-out read and the
  section 6 rule.
- **The held-out split was not checked for this.** Its labels came from the same process. Reviewing it is allowed only by a rule written before anyone looks:
  "every held-out row where exactly one class's edit passes the first failing test is
  re-reviewed blind". It goes in `EVAL_PROTOCOL.md` before the review starts, and the
  confirmatory set at Gate 6 stays the independent check.
- **Also check the other direction:** 76 of 104 OFF_BY_ONE rows and 104 of 141 ARRAY_BOUNDS rows
  show no fix-first evidence for their own class. A sample of 20 each tells whether those labels
  are sound or the repair ops are missing patterns.

### S2. Rule stage for partial array repairs (cheap, can start now)

`repair.array_bounds_gain > 0` is right 95% of the time on real rows (38 of 40). If the classifier
is not already naming those rows, a rule stage like the existing repair-first stage would catch
ARRAY_BOUNDS bugs that go to OTHER_ERROR today. Score it in the harness (rule fires on real rows,
false alarm) before adding it. The same test applies to `range_check_gain > 0` (5 of 6); that
rule is too small to matter alone.

### S3. UNINITIALIZED_VAR evidence combinations (cheap, after S1)

No single signal is precise enough for a rule (best: 0.67). A specialist feature that combines
the compiler warning, `uninit_zero_fixes` and `uninit_differs` might separate better than the
trees do now. Test it as a feature group with the harness. Do it after S1, because the labels
decide what "right" means here.

### S4. New evidence for RANGE_CHECK (needs re-execution)

The cache has nothing that separates RANGE_CHECK. Two additions:

- **Input-aware failure:** do the failing tests carry the problem's minimum or maximum values,
  or values just outside a range the code tests? This needs each test's input parsed against the
  problem's stated limits.
- **Wider range repairs:** the range edit finds a candidate on only 48% of RANGE_CHECK rows.
  Add operators for `<` to `<=` against constants, swapped bounds, and missing range checks.

Both need the programs re-run: Docker, or WSL with Ubuntu (installed on this machine). Every
new feature needs a training/live parity test (P2 rule).

### S5. Two-edit repairs for programs with more than one bug (expensive, last)

Real programs often have two problems, so no single edit fixes every test. A bounded search of
pairs (the class's edit plus one other) would show "this class plus something else". It is
costly to run and adds a decision-rule question, so it comes after S1 to S4 show their effect.

## What not to do again

Class balance (weights, caps, 2x row balance, bagging, prior correction) has been measured
and rejected: it trades precision on new problems for little recall (MODEL_LOG 9, 14 and 23 Nov).
Lowering thresholds trades 0.6 of precision for 0.05 of recall on OFF_BY_ONE.

## Order and owners (proposal)

| Step | Needs | Owner | Done when |
|---|---|---|---|
| S1 review sheet for the 105 rows | nothing | Rayaan (sheet), Umaima (labels), Eman (review) | decisions recorded |
| S1 rule for the held-out re-review, in `EVAL_PROTOCOL.md` | supervisor agreement | Rayaan | merged before any held-out review |
| S2 partial array-repair rule, scored | nothing | Rayaan | harness result logged |
| S1 retrain and gate | S1 decisions | Rayaan | MODEL_LOG entry |
| S3 uninit feature group | S1 | Eman | harness result logged |
| S4 range evidence | WSL or Docker | Rayaan, Eman | parity test passes, harness logged |
| S5 two-edit repairs | S1 to S4 | later | — |
