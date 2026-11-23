# Class balance plan: no class more than 2x another

23 November 2026 · branch `feat/class-ratio-2x`. Follows `docs/MODEL_IMPROVEMENT_PLAN.md`; every
step is scored with `scripts/eval_candidate_oof.py` on real training-side rows, never on the held-out split.

## The problem

Rows the served model trains on (train split, `plain_reg` row filter):

| Class | Total | Real | Synthetic |
|---|---:|---:|---:|
| OTHER_ERROR | 1,249 | 998 | 251 |
| OFF_BY_ONE | 228 | 92 | 136 |
| LOOP_BOUNDARY | 167 | 26 | 141 |
| RANGE_CHECK | 130 | 27 | 103 |
| ARRAY_BOUNDS | 123 | 92 | 31 |
| STALE_EXIT | 119 | 8 | 111 |
| UNINITIALIZED_VAR | 119 | 55 | 64 |
| ASSIGN_VS_COMPARE | 119 | 1 | 118 |
| INT_OVERFLOW | 108 | 66 | 42 |
| WRONG_LOOP_DIR (rule-only) | 74 | 1 | 73 |
| MISSING_BASE_CASE (rule-only) | 39 | 1 | 38 |

OTHER_ERROR is 11.6 times the smallest class the model predicts. It holds half of the training
weight, so the trees spend most of their splits telling OTHER_ERROR apart.

## Target

In every set of rows a booster is fitted on (each cross-validation fold and the final fit):

- **largest class / smallest class <= 2**, over the 9 classes the model predicts;
- the two rule-only classes are left out of training (weight 0, `drop_rule_only`), since the model
  never names them.

The check is computed and stored in `metrics_v1.json`, so a retrain shows whether it holds.

## How

1. **Bring the small classes up** to a floor (200 rows by default) with `augment_real_rows`, now
   counting all rows of the class. Parents are the class's real rows. A class with fewer than 5
   real rows (ASSIGN_VS_COMPARE, STALE_EXIT in a fold) uses all its rows as parents, since there
   is nothing else.
2. **Bring OTHER_ERROR down** to `max_ratio` x the smallest class: synthetic OTHER rows go first,
   then real ones, at random. Any other class above that cap is cut the same way.
3. **Bagging, so no OTHER row is wasted.** One subsample throws away about 600 real OTHER
   programs. With `bags: k`, each of k boosters gets a different OTHER subsample and the same
   other rows, and their probabilities are averaged. Every bag meets the 2x rule.
4. **Score** single-subsample and bagged variants against `p6_rule_only` (the served
   configuration), paired on the same 1,367 real rows: estimable macro-F1, per-class recall, and
   false alarm on real OTHER_ERROR.

## What to watch

- **False alarm.** Class weights (sqrt, full) raised rare-class recall and false alarms on real
  code before (MODEL_LOG 9 and 14 Nov). Row balancing pushes the same way. A balanced model is
  expected to name a misconception more often; the question is how much precision that costs.
- **Plain accuracy will drop.** 73% of real failing programs are OTHER_ERROR, so always answering
  OTHER already scores 0.73. Macro-F1 and per-class recall are the measures that matter here.
- **Serving bagged models** needs one booster file per bag, or one merged file. That is only
  worth building if bagging wins in the harness.
- Balance cannot add signal the features lack. RANGE_CHECK and OFF_BY_ONE may stay weak (P2).

## Results (23 Nov, `reports/candidates/cb_*.json`)

All runs are paired against `p6_rule_only`, the served configuration: estimable macro-F1 0.608,
false alarm 0.064, abstain 0.117. Every fold of every candidate met max/min = 2.00.

**Balancing alone breaks the decision.** Trained on a 2:1 OTHER mix, the booster believes only
about 20% of programs are OTHER_ERROR, against 73% in real code. Its probabilities spread out, the
refitted threshold rises to 0.76-0.84, and it **abstains on 44-55% of real programs**. OTHER_ERROR
recall falls from 0.81 to 0.32-0.44:

| Candidate | Estimable macro-F1 (diff, 95%) | False alarm | Abstain |
|---|---|---|---|
| cb_f150 | +0.012 (-0.039 to +0.075) | 0.062 | 0.46 |
| cb_f200 | -0.028 (-0.082 to -0.003), worse | 0.049 | 0.55 |
| cb_f300 | -0.021 (-0.076 to +0.018) | 0.056 | 0.50 |
| cb_f200_bag5 | -0.037 (-0.081 to -0.004), worse | 0.086 | 0.41 |
| cb_f300_bag5 | -0.021 (-0.067 to +0.012) | 0.066 | 0.44 |

**With prior correction** (`prior_correction`: probabilities rescaled to the real class mix before
the decision) the collapse is gone:

| Candidate | Estimable macro-F1 (diff, 95%) | Misconception recall | Precision when it names one | False alarm | Abstain |
|---|---|---|---|---|---|
| served config (`p6_rule_only`) | 0.608 | 0.558 | 0.687 | 0.064 | 0.117 |
| cb_f200_pc10 | +0.014 (-0.043 to +0.034) | 0.547 | 0.727 | 0.050 | 0.161 |
| cb_f300_pc05 | +0.022 (-0.030 to +0.060) | **0.580** | 0.686 | 0.065 | 0.177 |
| cb_f300_pc10 | +0.012 (-0.038 to +0.048) | 0.577 | 0.642 | 0.083 | 0.053 |
| cb_f300_bag5_pc10 | +0.008 (-0.036 to +0.038) | 0.558 | **0.725** | **0.050** | 0.122 |

Per class: `cb_f300_pc05` lifts RANGE_CHECK F1 from 0.31 to 0.41 and UNINITIALIZED_VAR from 0.37 to
0.42. `cb_f300_bag5_pc10` finds as many bugs as the served configuration, with precision up from
0.69 to 0.73 and false alarm down from 0.064 to 0.050. No balanced candidate clears the paired
bootstrap, and OFF_BY_ONE (about 0.49) does not move.

**What this says about the cause.** The 11.6x imbalance is real, but it is not what holds accuracy
down: with the 2x rule enforced and priors corrected, the model lands where it was, within noise.
The classes that fail (OFF_BY_ONE, RANGE_CHECK, STALE_EXIT) fail because their real programs look
like OTHER_ERROR to the current features. That is P2 (features) and P3 (more real rows) in
`MODEL_IMPROVEMENT_PLAN.md`.

**Next (done, see below):** train `cb_f300_bag5_pc10` (best precision and false
alarm) or `cb_f300_pc05` (best recall). Bagging needs the five boosters served together (one file
per bag, or merged); the single-bag variant needs only the prior-correction vector stored in
`calibrator.json`. Either needs one development-set read and the section 6 rule before serving.

## Trained and gated (23 Nov): not served

`cb_f300_bag5_pc10` was trained as a full model (`--class-balance '{"max_ratio": 2, "floor": 300,
"bags": 5, "aug_weight": 1.0, "prior_correction": 1.0}'`, commit `344ad48`, five bags, final-fit
class ratio 2.00). The backend can now serve a bagged model (`combine_bags`, `<file>.bagN.json`).

| | Served 8860b506 | Balanced 2x (acbdd3a3) |
|---|---|---|
| **Training side**, 1,367 real rows: estimable macro-F1 | 0.635 | 0.660 (+0.025, 95% -0.004 to +0.047) |
| misconception recall / precision | 0.556 / 0.782 | 0.583 / 0.782 |
| false alarm on real OTHER | 33/998 | 33/998 |
| **Held-out** (one read, tag `cb2x`, 662 rows): problem-weighted macro-F1 | 0.679 | 0.674 |
| precision when it names a class | 0.895 (85/95) | 0.736 (92/125) |
| false alarm on OTHER | 0.011 (5/460) | **0.052 (24/460)** |
| recall | 0.421 | 0.455 |
| without tl-progpedia-00000039: F1 / precision / false alarm | 0.695 / 0.806 / 0.017 | 0.690 / 0.627 / 0.059 |
| **Bank benchmark**, 273 programs: accuracy / false alarm | 0.963 / 0/40 | 0.934 / 4/40 |
| bank, solution style held out | 0.958 / 0/40 | 0.934 / 2/40 |

Held-out F1 per class, served to balanced: ARRAY_BOUNDS 0.70 to 0.71, RANGE_CHECK 0.15 to 0.16,
STALE_EXIT 0.33 to 0.40 (4 rows), LOOP_BOUNDARY 0.86 to 0.77, OTHER_ERROR 0.88 to 0.85,
ASSIGN_VS_COMPARE 1.00 to 0.80 (3 rows). OFF_BY_ONE (0.21), INT_OVERFLOW and UNINITIALIZED_VAR
are unchanged.

**It fails all three parts of the section 6 rule, in both scopes, and the bank benchmark is worse.**
The served model is restored. On the training problems the balanced model looked level on false
alarms. On problems it had not seen, it flags almost five times as many OTHER_ERROR programs. A
model that has seen OTHER_ERROR as one class in three no longer recognises unfamiliar wrong
answers as "something else". This is the same failure the class-weight experiments showed on 9
and 14 Nov, now with row balancing, bagging and prior correction.

**Conclusion.** Bringing OTHER_ERROR down to 2x the smallest class does not fix accuracy; it
trades precision on new problems for a few more caught bugs. The data imbalance mirrors the real
mix of student errors, and the model needs that mix to judge unfamiliar code. The weak classes
need signal (P2 features) or more real examples (P3), not a different class mix.

Tooling gap, only for a future bagged model: `eval_heldout_rows.py` records the hash of
`xgb_execution_v1.json` alone, while `ModelClassifier` hashes every bag, so the two disagree for a
bagged model (`acbdd3a3` against `8aa8dcac`).
