# Remaining work plan (2026-10-29)

Source of truth: `docs/master_plan_dataset.md` v4.1 (gates G0-G10, H1-H3), the FYP
blueprint §19/§22 (December prototype), `docs/dataset_progress_log.md`.
Repo state: `main` @ `0668d6d` (PR #5, Umaima's real-label work merged).

## Where things stand

| Area | Status |
|---|---|
| Lanes A/B/C, merge, splits, trainer, features (schema 1.1) | built; G1, G7 pass; 573 root tests pass or skip cleanly on Windows except `tests/test_progpedia_oracle.py` (`fcntl`) |
| G4 Tier-0 floors | **fail**: every class UNDER (floors 200-300; OFF_BY_ONE 46, UNINIT 35, OTHER_ERROR 13, etc.) |
| G5 Tier-1 weak, LF audits | pre-reviewed, **awaiting human sign-off** |
| G6 gold / dev-gold | 4 dev-gold rows in model; 220 gold + 60 dev-gold **not annotated** |
| G8 training | 3/4: **synthetic mass fails** (0.91 by weight per Umaima; 0.59 by row share) |
| G3 pilot go/no-go, G3b, G5b, G9, G10 | **not run** |
| Backend (blueprint §12 inference contract) | **no XGBoost call anywhere in `backend/app`**; diagnosis is rules-only |
| Backend tests | 24 failed + 20 errors on this Windows host (execution/security/sandbox: likely Linux-only, unconfirmed) |
| Docs | T10 `DATASET_CARD.md` / `final_evaluation.md` not final |

## Phase 0 - Baseline hygiene (0.5 day, no humans)

| # | Task | Gate / test |
|---|---|---|
| 0.1 | Skip `fcntl`-dependent `tests/test_progpedia_oracle.py` on Windows (same pattern as `tests/misconception_dataset/conftest.py`) | `pytest tests` collects with 0 errors on Windows and Linux |
| 0.2 | Triage the 44 backend failures/errors: label each `env-linux-only` vs `real bug`; mark env ones `skipif`, fix real ones | backend suite: 0 unexplained failures; run once under WSL/CI to confirm |
| 0.3 | Decide the stash: `stash@{0}` holds the 2026-10-24 trainer outputs (superseded by v0.6 on main); drop or keep | models dir clean vs `HEAD` |
| 0.4 | Pin a one-command gate runner `scripts/run_gates.py` printing G0-G10 status from existing verifiers | prints a table; exits non-zero on any hard-gate red |

## Phase 1 - Data floors, no humans needed (G4, G5-machine part)

| # | Task | Gate / test |
|---|---|---|
| 1.1 | Full `expand_mutants.py` run for the starved classes (needs WSL g++ and G: drive; run on Rayaan's machine) | G4: each class >= floor in `verify_dataset --per-class-report`; rejection < 50% with logged reasons; each class >= 15 clusters; <= 3 mutants/seed (or logged G0c relaxation) |
| 1.2 | Decoy generation for OTHER_ERROR (>= 100 per class pool, subsampled) | `OTHER_ERROR` floor met; decoys labeled OTHER only |
| 1.3 | Pre-review the 65 discovery rows (`review/progpedia_exec_review.jsonl`) for classes with no natural train rows | per-class discovery counts recorded for G3b |
| 1.4 | Re-run lanes (cached) -> `merge_dataset.py` -> trainer | G1 0 orphans; G7 straddles/twins = 0; tests `test_merge_dataset`, `test_expand_mutants`, `test_train_xgb_misconception` green |

## Phase 2 - Human gates (blocking; schedule now)

| # | Task | Owner | Gate |
|---|---|---|---|
| 2.1 | Sign the spot-check rows in the five sheets; run `apply_prereview_signoff.py` | Umaima/Rayaan | H2: mislabel < 10% per lane; >= 10 human-confirmed rows/class; each LF >= 50 audited fires at >= 90% (`lf_loop_boundary`, `output_pm1` expected to fail -> tighten or retire) |
| 2.2 | Calibration round (15 items) then gold annotation: 220 (150 floor) + 60 dev-gold, blind forms | all + external | G6: Fleiss kappa >= 0.6 (4 raters), intra-rater duplicates >= 8/10, >= 12 of 15 test clusters, >= 30 users |
| 2.3 | Adjudication + H3 merge meeting; waive or fix every red gate in `DATASET_CARD.md` | all | H3: no silent floor gap |
| 2.4 | Rayaan reviews `splits/README.md` split change | Rayaan | recorded sign-off |

## Phase 3 - Modeling gates (needs Phase 1; gold-dependent parts wait for 2.2)

| # | Task | Gate / test |
|---|---|---|
| 3.1 | **G8 synthetic mass**: with 2.1 + 1.3 done, retrain; do not tune the cap | G8 4/4, or documented waiver at H3 with projection (0.75-0.81) |
| 3.2 | **G3 pilot go/no-go** with bootstrap CIs: macro-F1 >= 0.40; transfer S+R >= R-only and S-only >= 0.30; adversarial AUC < 0.75; behavioral gate (full beats runtime+tests-only by >= 0.02 and beats static+warnings-only); pre-registered merges if pair confusion > 30% or kappa < 0.4 | new `scripts/run_ablations.py` + `tests/test_ablations.py` on fixtures; results in `reports/g3_pilot.md` |
| 3.3 | **G3b**: classes 4, 8, 9, 10 with < 12 verified real rows -> family-level only via `label_mapping.csv` join | join test: remap changes labels, not rows |
| 3.4 | **G5b** PROGpedia/CPG keep-drop on train-side CodeStream validation (+0.02 or analysis-only) | decision recorded in `DATASET_CARD.md` |
| 3.5 | Source-shortcut test (dataset_source from missingness > 90% -> common variant forced) | unit test with synthetic missingness |
| 3.6 | Calibration: global threshold + temperature on 60 dev-gold (isotonic banned) | trainer test: < 10 dev-gold -> explicit uncalibrated fallback (exists); ECE reported |

## Phase 4 - Final evaluation (needs gold locked)

| # | Task | Gate / test |
|---|---|---|
| 4.1 | One-shot test-gold evaluation: per-class P/R/F1 + Wilson intervals, confusion (fine + family), paired bootstrap vs rule baseline (resampled by problem), McNemar exact, open-set false-alarm <= 30%, per-source and firing_count slices, SHAP by group | **G9**; `scripts/evaluate_holdout.py` extended; `tests/test_final_evaluation.py` on fixtures; scope statement "gold is CodeStream-only" on page 1 |
| 4.2 | Write `final_evaluation.md` + finish `DATASET_CARD.md` (tier claims, V2 scope, G0c/G3b fallbacks) | Definition of Done §15 checklist all ticked or disclosed |
| 4.3 | **G10** clean-checkout rerun by someone other than Rayaan | numbers match within tolerance |

## Phase 5 - Product integration (blueprint §12, §19, §22; can start after 3.2 passes)

| # | Task | Gate / test |
|---|---|---|
| 5.1 | `backend/app/diagnosis/xgb_classifier.py`: load `xgb_*_v1.json` + `label_encoder`, build vector in FEATURE_SCHEMA order via `tracelearn_features`, return calibrated probabilities | unit: vector order/NaN contract; golden prediction fixture |
| 5.2 | Inference router per §12: compile fail / all pass / timeout -> deterministic paths (no model); else sandbox_runner -> features -> model; below threshold -> UNCERTAIN -> rules fallback; OTHER_ERROR messaging | tests for every branch in `backend/tests/test_diagnosis.py` |
| 5.3 | Feature flag + model/config versioning in submission records; common-feature variant when runtime unavailable | test: flag off = current rules behavior, byte-identical |
| 5.4 | Evidence + SHAP top features surfaced to hints and teacher view | contract test on API schema |
| 5.5 | Learner-model and hint policy regression: no-future-leakage, five hint levels | existing `test_state_transitions`, `test_history_model` green; add leakage test |
| 5.6 | Deployment hardening on Linux/Docker (security + sandbox tests actually executing) | `backend/tests/test_security.py` and `test_execution.py` green in CI, not skipped |

## Ordering and parallelism

- Start now, in parallel: Phase 0, 1.1-1.3 (Rayaan's machine), 2.1 (humans), 5.1 (Eman, on fixtures).
- Critical path: 1.1 -> 2.1 -> 3.1/3.2 -> 2.2 (gold) -> 4.1 -> 4.3. Gold annotation (2.2) is the long pole; schedule the calibration round first.
- Cut-lines (master plan §10): G4/G5 unmet after the full run -> ship at >= 150/class; drop order PROGpedia -> CPG -> SHAP polish; the 150-row gold floor is non-negotiable.
- If XGBoost does not beat the rule baseline with a CI above zero, report that and keep the rule engine as default (blueprint §19.2).

## Definition of done

`scripts/run_gates.py` shows G0-G10 green or waived in `DATASET_CARD.md`; root and backend suites green on Linux CI; `final_evaluation.md` published; backend serves model-backed diagnosis behind a flag with a verified rules fallback.
