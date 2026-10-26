# Splits

| File | What it is |
|---|---|
| `cluster_assignments.csv` | problem → cluster → split (`train` / `dev_gold` / `test`). A cluster never straddles splits (G7). |
| `iid_holdout.csv` | rows moved from **train** clusters into `test_iid` (from `scripts/build_iid_holdout.py`). |
| `splits.csv` | per-row split written by `merge_dataset.py` (cluster split, then the IID override). |
| `codestream_clusters.csv`, `codestream_problem_flags.csv` | CodeStream clustering inputs (`cluster_codestream_problems.py`). |

## The four pools

* **train**: CV and fitting.
* **dev_gold**: held-out clusters used only for the global threshold and temperature
  (§11.5 / G8). It is never inside CV folds.
* **test**: the frozen, cluster-disjoint CodeStream test, evaluated **once**
  (`evaluate_holdout.py --split test --confirm-one-shot`).
* **test_iid**: a seeded, stratified sample of natural rows from *train* clusters.
  It measures accuracy on new submissions to problems the model has seen, which
  complements `test`'s unseen-problem question. It is excluded from training,
  and rows that seed a synthetic mutant are never drawn (that would leak).

Only rows with a **certain** label are scored on dev_gold / test / test_iid
(human, repair-verified, execution-verified synthetic). Weak labels in these
pools get a human label through the pre-review sheets
(`review/model_prereview/dev_gold_*`, `iid_test_*`); every row in those sheets
needs a person's signature.

## Changes

* **2026-10-26: PROGPedia clusters `clu-049` (00000043, Encomendas) and `clu-051`
  (00000048, connected components) moved `train` → `dev_gold`.** The four
  CodeStream dev-gold clusters hold only 30 failing rows, short of the 60-item
  calibration target (§13.2). These two problems were chosen because, after the
  execution lane, they hold a mix of classes (ARRAY_BOUNDS, LOOP_BOUNDARY,
  OFF_BY_ONE, OTHER_ERROR) rather than one. Both are single-problem clusters, so
  no cluster straddles splits. PROGPedia clusters `clu-039..053` were never
  part of the CodeStream `test` budget, so `test` is unchanged.
* **2026-10-26: `iid_holdout.csv`**: 36 rows (seed 20261026).
