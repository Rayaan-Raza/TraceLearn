# Model log

One entry per model worth keeping, newest first. Each entry names the commit that holds the model
files, how it was measured, and how to go back to it.

To restore a logged model (only the model folder changes; the code stays as it is):

```bash
git checkout <commit> -- data/misconception_dataset/models
```

The backend serves the `execution` variant only with `MODEL_DIAGNOSIS=on`, `MODEL_VARIANT=execution`
and `MODEL_RUN_RECORDS=on`.

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

What it means: when this model names a misconception it agrees with the annotators about 4 times in 5,
but it names one for only about 2 in 5 of the programs that have one.

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
