# Sign-off round 1: findings (8 Nov 2026)

Signed by Umaima on the blind sign-off page: 135 rows over the five sheets. Applied with
`apply_prereview_signoff.py` (see `signoff_report.md` for the per-sheet table).

## What it produced

| | Result |
|---|---|
| Decisions on existing rows | 64 confirm, 42 relabel (41 distinct rows; `cs-000666` is on two sheets with the same label) |
| New human rows (`tier1d`, `hr-*`) | 29 CodeStream dev-gold items, re-executed in the sandbox |
| Dev-gold after a re-merge | **67 rows, all certain** (64 human + 3 synthetic): the ≥ 60 target is met |
| IID test after a re-merge | **36 rows, all human-labelled** |
| LF audits (`lf_audits.csv`) | `pg-3` 44/63 correct · `lf_loop_boundary` 5/16 · `lf_array_bounds` 6/12 · `lf_off_by_one` 5/8 · `lf_int_overflow` 8/10 · repair-verified 11/11 |

The merge applies cleanly (`MERGE PASS`, G7 0/0/0, 0 unknown row ids). Model outputs are **not**
retrained on this branch: the next retrain belongs with the model work in progress.

## First real IID number

`evaluate_holdout.py --split test_iid` (logged in `reports/holdout_evaluations.jsonl`) on the 36
human-labelled IID rows, with the model on `main`:

| Variant | Macro-F1 (present classes) | Accuracy |
|---|---:|---:|
| full | 0.402 | 0.556 |
| best | 0.364 | 0.500 |

(After the corrections below. Before them it was 0.335 / 0.303: IID-PG-006's
`MISSING_BASE_CASE` was a one-row class the model could not score on. Accuracy did not change.)

On the old weak labels the same rows scored about 0.67–0.73. Every one of the 11 rows a person
labelled `OTHER_ERROR` is missed: the model never predicts it. ARRAY_BOUNDS (13 rows, F1 0.69–0.71)
and INT_OVERFLOW (6 rows, 0.77–0.86) hold up.

## Anchoring: read before relying on these labels

The page records when a label was changed after the model's answer was shown.

| Sheet | Signed | Changed after reveal | Agreement with the model, final | before the reveal |
|---|---:|---:|---:|---:|
| weak_labels_progpedia | 63 | 28 | 100% | 56% |
| weak_labels_codestream | 8 | 4 | 100% | 50% |
| dev_gold_progpedia | 17 | 5 | 88% | 59% |
| iid_test_progpedia | 17 | 5 | 88% | 59% |
| dev_gold_codestream | 30 | 3 | 97% | 90% |

45 of 135 labels moved to the model's answer after the reveal. Some of these are legitimate
corrections (the rationale points at execution evidence a reader can miss), but together they
mean these labels are **single-rater and partly anchored**. So:

- spot-check acceptance now uses **independent** (pre-reveal) agreement. Neither weak-label sheet
  reaches 90% that way, so the 112 unsigned weak rows were **not** accepted on the model's word
  and keep their weak labels;
- the gold claims (G6) still need the blind 4-rater forms. These sheet labels support dev-gold
  calibration and the IID check; they do not replace the gold round.

## Rows double-checked

| Item | Row | Signed | Why it looked off | Resolution (Umaima, 8 Nov) |
|---|---|---|---|---|
| IID-PG-006 | pgx-000803 | disagree → `CPP_MISSING_BASE_CASE` | Greedy segment cover with no recursion at all; likely a mis-click (model said OTHER_ERROR) | corrected to `CPP_OTHER_ERROR` |
| DG-019 / DG-020 | cs-002517 / cs-002520 | `RANGE_CHECK` / `OTHER_ERROR` | Same bug (chained `65<=ch<=90`) labelled two different ways; pick one for both | both `CPP_RANGE_CHECK` |
| DG-030 | cs-003390 | agree → `RANGE_CHECK` | Note argues for OTHER_ERROR ("classified as OTHER_ERROR"); label and note disagree | corrected to `CPP_OTHER_ERROR` |
| WL-CS-002, -017, -022, -023 | cs-000373, cs-001902, cs-002448, cs-002449 (test clusters) | human labels | Four CodeStream rows in the one-shot **test** split got human labels through this non-blind page. Re-label them on the blind gold forms before the test is scored | open: keep for the gold round |
