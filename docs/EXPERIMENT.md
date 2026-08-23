# Experiment protocol (stub)

## Holdout evaluation

- **Demo sequences** live under `data/demo_sequences/` (development and walkthroughs).
- **Evaluation sequences** live under `data/evaluation_sequences/` (holdout; do not tune on these).

## Frozen weights

`config/evidence_weights.yaml` is **frozen before holdout evaluation**. Do not adjust weights or
thresholds after observing results on `data/evaluation_sequences/`. Document any pre-registerd
changes in version control before running holdout metrics.

## Ground truth

Labeled misconceptions for evaluation are loaded via `GroundTruthRepository` in
`backend/app/evaluation/labels.py`. Diagnosis modules must not import ground-truth files directly.
