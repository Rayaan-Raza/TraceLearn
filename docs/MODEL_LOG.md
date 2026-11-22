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
