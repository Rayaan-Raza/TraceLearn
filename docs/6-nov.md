# TraceLearn status and plan to Iteration 2 (6 Nov 2026)

Written from the repo at `main` @ `6f454d8`, the docs in `docs/` and `Docs_Agents/`, and the metrics files in
`data/misconception_dataset/`. Items marked **(unverified)** are what the code or docs say; I did not run them.
The December deadline date is not stated in any doc, so the schedule below is in weeks from today.

## Progress log and corrections (branch `feat/model-backend-integration`)

**Decided (6 Nov):** the product language is **C++**. The blueprint's "Python primary" wording is out of date, so
decision A1 in section 10 is closed; the Python POC problems stay on the rule engine only.

**Corrections to this file, found while building:**
- The full model uses **107 features** (not 90); `common` uses 44 and `best` 59. The server reads each variant's exact
  feature order from `metrics_v1.json`.
- The "44 backend failures" came from running the root and backend suites in **one** pytest process. Run separately,
  the backend suite has **2 failures**, both of which also fail on clean `main` and both need g++ / the OS sandbox,
  which this Windows host lacks (`test_cpp_correct_solution_passes`, `test_sandbox_timeout_and_output_limits`).
  Treat the combined-run errors as test-isolation noise until Linux CI says otherwise.
- The Docker image did not copy `tracelearn_features/`, so the backend could not have imported the feature code in
  production. Fixed in this branch.

**Done on this branch (Rayaan, week 1):**

| Item | Status | Evidence |
|---|---|---|
| B2 `ModelClassifier` | done | `backend/app/diagnosis/xgb_classifier.py` |
| I2 golden test | green | `backend/tests/test_xgb_classifier.py`, fixture `backend/tests/fixtures/model_golden.json`, regenerate with `scripts/make_model_golden.py` |
| I3 contract tests | green | corrupt/missing/renamed-feature/class-mismatch/bad-calibrator cases all refuse to load |
| B3 label mapping | done | `MODEL_LABEL_TO_BACKEND` in `cpp_mapping.py`; `CPP_OTHER_ERROR` added to the taxonomy as unscored |
| B4 `MODEL` evidence source | done | `analysis/model_evidence.py`, `EvidenceSourceType.MODEL`, fusion branch in `confidence.py` |
| B6 settings (flag defaults to `off`) | partly | `model_diagnosis`, `model_variant`, `model_dir`, `model_evidence_weight` in `config.py`; not yet used by the pipeline |
| B10 dependencies | done | `numpy`, `xgboost>=2.1,<4` in `requirements.txt`; `tracelearn_features/` copied in `Dockerfile` |

33 new tests pass. The model is **not yet in the request path**: that needs Eman's feature builder (B1) and the
router (B5), so nothing a student or teacher sees has changed.

---

## 1. What Iteration 2 requires

Blueprint §19.1 (Nov-Dec, "Complete December prototype") and §22.1 ("Required by December"):

| # | Requirement | Where we are |
|---|---|---|
| 1 | Student + teacher platform with browser editor | Built (React + Monaco, 8 student pages, 11 teacher pages) |
| 2 | Server-side execution, visible/hidden/diagnostic tests | Built for Python and C++ (bubblewrap sandbox, `backend/app/execution`) |
| 3 | 30-40 integrated problems, 8-12 misconception beliefs | C++ diagnostic bank has 40 problems and 8 beliefs (`CPP-M01..M08`); 6 Python problems; 8 more in `data/cpp_problems`. Backend scores 13 codes |
| 4 | Multi-source evidence extraction with provenance | Built (static, test, runtime, diff, history analyzers) |
| 5 | Rule baseline + **XGBoost pipeline; trained XGBoost if data is ready** | Rules: built. XGBoost: **trained but not connected to anything** |
| 6 | Persistent temporal learner model, no-future-leakage tests | Built (`learner_model/`, `HistoryProvider(as_of)`) **(unverified: backend tests do not all run on this Windows machine)** |
| 7 | Five-level adaptive hint policy | Built (`hints/`) **(unverified)** |
| 8 | Teacher evidence + correction workflow | Built (teacher review API + pages) **(unverified)** |
| 9 | Normalized external data ingestion + local data | Ingestion done; no local student data yet |
| 10 | Initial labelled evaluation and reproducible metrics | Partial: CV metrics exist; no signed gold, test split not scored |
| 11 | Full demo: classroom -> submission -> execution -> evidence -> diagnosis -> state -> hint -> teacher | Works on the rules path; **the model is not in the loop** |

**The biggest gap is item 5/11: the model is not wired into the backend or frontend.** Nothing under `backend/app` or
`frontend/src` references XGBoost.

---

## 2. What has been done

| Area | Done |
|---|---|
| Dataset (v0.6) | 702 rows after dedupe: 384 synthetic, 285 PROGPedia, 33 CodeStream. Splits: train 588, dev-gold 45, test 33, test_iid 36. Schema 1.1, 90 features in 7 blocks. G1 and G7 pass |
| Lane A (Eman) | Mutation operator library, verifier with proofs, full 9-class expansion (119 rows), semantics + source-CPG extractors |
| Lane B (Umaima) | `sandbox_runner` (Docker, sanitizers, Valgrind), CodeStream labeling, gold forms, PROGPedia oracle tests + execution lane (199 rows), model pre-review sheets |
| Lane C / training (Rayaan) | Normalizer, merge + G7 gate, XGBoost trainer (full / masked / common / best), IID hold-out, evaluator |
| Platform | FastAPI backend, rule-based fusion, two diagnosis modes (current-only vs history-aware), hints, teacher review, C++ bank, CI/CD workflows |
| Tests | Root suite: 573 pass or skip cleanly on Windows. Backend: 24 failures + 20 errors on this Windows host (security/execution/sandbox, probably Linux-only; **not yet confirmed**) |

---

## 3. Model accuracy, stated honestly

Model v0.6, trained on 588 rows, 11 classes. Source: `models/metrics_v1.json`, `DATASET_CARD.md`.

| Variant | CV macro-F1 (3x3 grouped by problem cluster) | OOF macro-F1 | ECE |
|---|---|---|---|
| full (all features) | **0.724 +/- 0.030** | 0.713 | 0.064 |
| common (static + warnings) | 0.705 +/- 0.045 | 0.696 | 0.087 |
| best (static + warnings + semantics) | 0.711 +/- 0.037 | 0.703 | 0.101 |
| majority-class baseline | 0.035 | | |

Per-class F1 (full, out-of-fold): ASSIGN_VS_COMPARE 0.92, MISSING_BASE_CASE 0.94, RANGE_CHECK 0.90, ARRAY_BOUNDS 0.83,
LOOP_BOUNDARY 0.78, OFF_BY_ONE 0.75, STALE_EXIT 0.67, WRONG_LOOP_DIR 0.67, INT_OVERFLOW 0.61 (recall 0.46),
UNINITIALIZED_VAR 0.58, **OTHER_ERROR 0.20** (precision 0.15, 10 rows).

**What these numbers do and do not mean**

- 0.72 is cross-validation on a training pool that is **91% synthetic by weight**. It measures "can the model recognise
  our own mutants and PROGPedia patterns", not "can it diagnose a real student". Do not present it as classifier accuracy.
- The only number on rows closer to real students is **dev-gold macro-F1 = 0.24 (45 rows, most still weak labels)**.
  That is the number to treat as the current real-world estimate, with a very wide interval.
- `test_iid` (just run): only **8 certain rows scored** (6 INT_OVERFLOW, 2 LOOP_BOUNDARY), macro-F1 1.0. Too small to mean anything.
- The CodeStream `test` split (33 rows) has **not been scored**; it is one-shot, so it stays unopened until gold is signed.
- G8 passes 3 of 4. The failing check is synthetic mass <= 50%.
- Zero human-signed labels so far. Estimated weak-label precision: CodeStream ~45%, PROGPedia pg-3 ~76% (model pre-review, not human).
- Class floors (G4) are unmet: e.g. UNINITIALIZED_VAR 35, OTHER_ERROR 13, against floors of 200-300.

**Recommended wording for the Iteration 2 report:** "A calibrated XGBoost baseline reaches 0.72 macro-F1 in grouped
cross-validation on a mostly synthetic training pool, and 0.24 on a small, partly weak dev-gold set. Real-student
accuracy has not been measured; it will be measured on signed gold in January-March." Follow blueprint §19.2: if the
model does not beat the rule engine reliably on gold, report that and keep the rules as the default.

---

## 4. The model -> backend -> frontend gap (what actually has to be built)

### 4.1 Findings

1. **No inference code exists.** The model is seven JSON files in `data/misconception_dataset/models/`
   (`xgb_v1`, `xgb_masked_v1`, `xgb_common_v1`, `xgb_best_v1`, `calibrator`, `label_encoder`, `metrics_v1`).
2. **Taxonomy mismatch.** Dataset has 11 labels. Backend `CPP_MISCONCEPTIONS` has 10 and **no `CPP_OTHER_ERROR`**; it also
   scores Python codes `M01-M03` and the bank codes `CPP-M02/M03` (value-vs-index, print-vs-return) which the model has
   **no class for**. `cpp_mapping.py` is the one translation point and needs a model-label table.
3. **Two different execution harnesses.** The backend runs C++ in a bubblewrap sandbox (`execution/sandbox.py`).
   The model's runtime/tests features were produced by `sandbox_runner` (Docker, ASan/UBSan, Valgrind). A student
   submission at inference time will not have sanitizer or Valgrind output unless we run `sandbox_runner` too.
4. **Feature availability at inference.** Computable from source + `g++ -Wall -Wextra` + the backend test results:
   `static`, `warnings`, `semantics`, `tests`, partly `context`. Not available without `sandbox_runner`: `runtime` (sanitizers).
   XGBoost accepts NaN, but a model trained with runtime features present on some rows and a server that always sends NaN
   is a **train/serve skew risk** that must be measured, not assumed away.
5. **Diagnosis API shape is fixed to two modes.** `Diagnosis.mode` is `current_only | history_aware`
   (`frontend/src/api/types.ts`). The model needs either a third mode or a field on the existing ones.
6. **Unused doc statement to honour:** blueprint §9.1 says XGBoost owns *current-submission* classification only; the
   temporal learner model consumes its probability. So the model plugs into the **current-only** engine, and
   history-aware stays the temporal fusion on top.

### 4.2 Target design

```
submit -> run_submission_tests (existing)
       -> compile branch / all-pass branch / timeout branch   (deterministic, no model; blueprint §12)
       -> else InferenceFeatureBuilder(source, compile warnings, test results, problem context)
              -> ModelClassifier(variant, calibrator, label_encoder, threshold)
              -> top-k probabilities, abstain if max < global threshold
       -> fuse_diagnosis(rule evidence + model evidence item "MODEL_PREDICTION")   # model becomes an EvidenceItem
       -> current_only Diagnosis (+ model block in explanation_json)
       -> history_aware Diagnosis (existing temporal update, unchanged)
       -> hint policy (label -> hint family)
```

Key design decision: **write the model output as one more `EvidenceItem`** (source_type `MODEL`, weight from
`config/evidence_weights.yaml`) instead of replacing the rule engine. That keeps provenance, lets the rules remain the
fallback, keeps the history engine untouched, and makes "rules vs model vs both" an ablation by config flag.

### 4.3 Backend work items

| ID | Item | Files |
|---|---|---|
| B1 | `InferenceFeatureBuilder`: build the 90-feature vector in `FEATURE_SCHEMA` order from a live submission using `tracelearn_features.extract_features` | new `backend/app/analysis/model_features.py` |
| B2 | `ModelClassifier`: load booster JSON + `calibrator.json` + `label_encoder.json`; temperature scaling; global threshold; return top-k; expose model sha256 and variant | new `backend/app/diagnosis/xgb_classifier.py` |
| B3 | Label mapping: dataset label <-> backend code (add `CPP_OTHER_ERROR`, decide treatment of `M02/M03` bank codes) | `diagnosis/taxonomy.py`, `cpp_mapping.py` |
| B4 | Evidence source `MODEL` + weight config; `fuse_diagnosis` accepts it; UNCERTAIN when below threshold | `db/models.py`, `analysis/pipeline.py`, `diagnosis/confidence.py`, `config/evidence_weights.yaml` |
| B5 | Router per blueprint §12 (compile fail / all pass / timeout bypass the model) | `services/submission_service.py` |
| B6 | Feature flag `MODEL_DIAGNOSIS={off,shadow,on}` and `MODEL_VARIANT={full,common,best}` in `config.py`. `shadow` = compute and store, do not affect the shown diagnosis | `config.py` |
| B7 | Persist model version, variant, sha256, probabilities, abstain flag per submission (migration) | `db/models.py` + schema |
| B8 | Hints for all 11 labels (OTHER_ERROR gets generic guidance, not a misconception hint) | `hints/templates.py`, `hint_policy.py` |
| B9 | API: add `model_prediction` to the diagnose / run-and-analyze responses; new `GET /api/model/info` | `schemas/diagnosis.py`, `schemas/submissions.py`, `api/submissions.py` |
| B10 | `requirements.txt`: pin `xgboost`, `numpy`, `pandas` to the versions the trainer used **(verify they are present)** | `requirements.txt`, `Dockerfile` |

### 4.4 Frontend work items

| ID | Item | Files |
|---|---|---|
| F1 | Types: `ModelPrediction {variant, version, top_k[{label, p}], abstained, threshold, top_features[]}`; add to `RunResult` and `Diagnosis` | `frontend/src/api/types.ts` |
| F2 | Labels/colors/descriptions for the 11 labels incl. OTHER_ERROR | `frontend/src/lib/labels.ts` |
| F3 | Student Result page: show the label, a plain-language reason, and the hint. Show confidence as a band (low/medium/high), not raw probability; show "not sure, here is general guidance" on abstain | `pages/student/Result.tsx`, `SubmissionDetail.tsx` |
| F4 | Teacher SubmissionDetail: side-by-side **rules / model / history-aware**, top-3 probabilities, top features, model version; teacher correction button writes an audit event | `pages/teacher/SubmissionDetail.tsx` |
| F5 | Teacher Research page: rules-vs-model-vs-history table from `/api/evaluation` | `pages/teacher/Research.tsx`, `api/evaluation.py` |
| F6 | Misconception charts accept the 11 labels | `components/MisconceptionCharts.tsx` |
| F7 | `npm run lint` + `npm run build` green; add a component test for abstain and OTHER_ERROR rendering (no test runner is set up in `package.json` **(verify)**; add Vitest) | `frontend/` |

---

## 5. Gates and tests for the integration

| Gate | Pass criteria |
|---|---|
| **I1 Parity** | For >= 50 dataset rows with source available, features from `InferenceFeatureBuilder` equal `features.csv` within tolerance for `static`, `warnings`, `semantics`; mismatches listed. Test: `backend/tests/test_model_feature_parity.py` |
| **I2 Prediction golden** | Fixed 10-row fixture -> exact label + probabilities (rounded) from `ModelClassifier`; same result across two processes. `test_xgb_classifier.py` |
| **I3 Contract** | Vector order = `FEATURE_SCHEMA`; unknown model/schema version refuses to load; NaN passes through; label_encoder covers all 11 labels |
| **I4 Router** | One test per branch: compile fail, all pass, timeout, normal -> model called exactly once only in the last case. `test_diagnosis.py` |
| **I5 Flag-off identity** | With `MODEL_DIAGNOSIS=off`, API output on the existing C++ and Python end-to-end tests is **byte-identical** to today |
| **I6 Shadow mode** | `shadow` stores predictions and does not change `primary_misconception` on any existing test |
| **I7 Abstain** | Below-threshold prediction -> UNCERTAIN + rule fallback, never a confident wrong label; OTHER_ERROR shown as generic guidance |
| **I8 Skew check** | Run the bank's own reference solutions and variant files through the live path; report model accuracy on the **40-problem bank variants** (`data/cpp_diagnostics/variants`) vs the rule engine. Report, do not tune on it |
| **I9 No leakage** | `ground_truth_*` and `mutation_op`/`seed_ref` never reach the feature builder (test with a poisoned fixture); existing temporal no-future-leakage tests still pass |
| **I10 Performance** | Inference adds < 200 ms p95 per submission on the dev machine |
| **I11 Frontend** | `lint` + `build` + component tests green; screenshot of Result and teacher SubmissionDetail with a model prediction and with an abstain |
| **I12 E2E** | Playwright or API-level script: student submits a buggy bank variant -> diagnosis shows model block -> hint -> teacher sees comparison. Runs in CI on Linux |
| **I13 CI** | `backend` + `frontend` jobs in `ci.yml` green on Linux, with the 44 currently failing backend tests either fixed or explicitly marked Linux-only with a reason |

Decision rule from blueprint §19.2: after I8, if the model does not beat the rule engine on the bank variants, ship it in
`shadow` mode for Iteration 2 and say so; do not claim an ML win.

---

## 5b. Detailed passing gates and possible failures

Thresholds marked *(proposed)* are new numbers I am suggesting for the integration work; agree or change them in the
week-1 meeting **before** looking at results, and record them in this file. Thresholds marked *(master plan)* already
exist in `docs/master_plan_dataset.md`. A gate is green only when its **evidence artifact** exists and is committed.
"Fallback" is the pre-agreed action when the fix fails, so nobody has to negotiate under deadline pressure.

### 5b.1 Integration gates I1-I13

#### I1 Feature parity (owner: Eman)
- **Command / test:** `pytest backend/tests/test_model_feature_parity.py`
- **Pass:** on >= 50 dataset rows with source available (stratified: >= 3 per class, all three sources):
  `static.*` and `semantics.*` match `features.csv` **exactly**; `warnings.*` match exactly when the same g++ version is used;
  `tests.*` match within 1 test count. Zero unexplained mismatches (every difference has a written cause).
- **Evidence:** `reports/inference_parity.md` with a per-block mismatch table.
- **Possible failures**
  | Symptom | Likely cause | Fix | Fallback |
  |---|---|---|---|
  | `static.*` differs on many rows | Dataset features were computed on clang-format-normalised source; live path uses raw student code | apply the same normaliser in the builder, or compute from the raw source in both | document and exclude normalised-only features |
  | `warnings.*` all zero live | live compile uses different flags (`-O2 -Wall -Wextra` is the dataset contract) | copy flags from `sandbox_runner`, not `cpp_runner` | serve `best`/`common` without warnings |
  | `warnings.*` differ by count | g++ 13.3 (WSL) vs another version on the server | pin g++ in `Dockerfile`; record version in the manifest | accept +-1 and widen the tolerance in writing |
  | `tests.*` shape differs | backend test results lack `first_fail_index` / per-test timing | compute from backend results; leave NaN where truly absent | drop `tests` block, retrain `common` |
  | Column order wrong | built from a dict, not `FEATURE_SCHEMA` order | iterate `FEATURE_SCHEMA` explicitly (I3) | none, must fix |

#### I2 Prediction golden (owner: Rayaan)
- **Test:** `backend/tests/test_xgb_classifier.py`
- **Pass:** a committed 10-row fixture produces the same top label and probabilities (rounded to 4 dp) in two separate
  processes and on Windows and Linux; probabilities sum to 1 +- 1e-6; model sha256 equals `metrics_v1.json`.
- **Possible failures:** probabilities differ across OS (XGBoost thread nondeterminism: set `n_jobs=1` at inference);
  `get_booster().save_model` JSON loads with a different `XGBClassifier` API (load via `Booster`, not the sklearn wrapper,
  as the trainer saves boosters); calibrator applied twice or not at all (assert `T` read from `calibrator.json`).
  Fallback: freeze the xgboost version in `requirements.txt` and fail loudly on mismatch.

#### I3 Contract (owner: Rayaan)
- **Pass:** vector length == 90 and order == `FEATURE_SCHEMA`; a model with a different `schema_version` or feature
  list refuses to load with a clear error; every one of the 11 labels in `label_encoder.json` maps to a backend code or
  to an explicit "model-only" entry; NaN passes through unchanged.
- **Possible failures:** schema bumps to 1.2 later and silently reorders (the hash check catches this: store the
  schema hash in `metrics_v1.json`); label added to the dataset but not the backend (test iterates `label_encoder.json`).

#### I4 Router branches (owner: Rayaan)
- **Test:** `backend/tests/test_diagnosis.py` (one test per branch, with a spy on `ModelClassifier.predict`).
- **Pass:** compile error -> deterministic feedback, 0 model calls; all tests pass -> `NO_MISCONCEPTION`, 0 calls;
  timeout without crash -> infinite-loop hint, 0 calls; failing + runnable -> exactly 1 call.
- **Possible failures:** model called on a compile error and returns a confident wrong class (the most damaging bug:
  students see a misconception label for a missing semicolon); wrong-answer detected as runtime error (the existing
  `test_wrong_answer_is_not_a_runtime_error` failure on Windows hints this boundary is fragile: fix before wiring).

#### I5 Flag-off identity (owner: Rayaan)
- **Pass:** with `MODEL_DIAGNOSIS=off`, the JSON from `/submissions/{id}/run-and-analyze` and `/diagnose` for all
  existing end-to-end fixtures is byte-identical to a snapshot taken **before** the change (commit the snapshots first).
- **Possible failures:** new response fields appear even when off (make `model_prediction` `null`, not absent, in both
  states and update the snapshots once, deliberately); an extra DB row changes ids (write model evidence only when on/shadow).

#### I6 Shadow mode (owner: Rayaan)
- **Pass:** in `shadow`, `primary_misconception`, `primary_confidence`, hints and learner state are identical to `off`
  on every existing test; the model block is stored and retrievable.
- **Possible failures:** model evidence leaks into `fuse_diagnosis` through the shared evidence table (filter by
  `source_type != MODEL` when shadow); learner-state updater reads the new row (test it explicitly).

#### I7 Abstain and OTHER_ERROR (owner: Eman + Rayaan)
- **Pass:** `max_prob < threshold` -> `UNCERTAIN`, rule engine decides, UI shows "not sure" text; a confident
  `CPP_OTHER_ERROR` shows generic debugging guidance and **no** misconception name; on the dev-gold set the
  confident-misclassification rate stays <= the open-set target of 30% (master plan §8 Layer 5).
- **Possible failures:** threshold is tuned on 45 mostly-weak dev-gold rows and abstains on everything or nothing.
  Check the abstain rate on the bank variants: acceptable band 10-60% *(proposed)*; outside it, set the threshold from
  the OOF probabilities instead and say so. OTHER_ERROR precision is 0.15 today, so expect false alarms; fallback is to
  treat OTHER_ERROR as `UNCERTAIN` in the UI until precision >= 0.5 on gold.

#### I8 Bank-variant evaluation (owner: Rayaan)
- **Command:** new `scripts/eval_bank_variants.py` over `data/cpp_diagnostics/variants` and `solutions` through the live path.
- **Pass (report-only, no tuning on it):** per-class precision/recall with Wilson 95% intervals; clean reference
  solutions produce `NO_MISCONCEPTION` or abstain in >= 95% of cases *(proposed)* (a false-alarm gate);
  model-vs-rules difference reported with a paired bootstrap resampled by **problem**.
  Ship decision: model is shown to students only if macro-F1 (model+rules) >= macro-F1 (rules) with the CI lower bound
  >= -0.02; otherwise `shadow` only (blueprint §19.2).
- **Possible failures**
  | Symptom | Likely cause | Response |
  |---|---|---|
  | Model far below rules on bank variants | bank bugs are hand-written and look unlike mutants/PROGPedia (distribution shift) | report honestly; keep rules as default; add bank variants to training **only** from a disjoint set, never the evaluation set |
  | Clean solutions flagged | train data has no clean negatives; `NO_MISCONCEPTION` is not a model class | the router already bypasses the model when all tests pass; verify the bypass is what catches them |
  | High variance (few problems per class) | bank is 40 problems / 8 beliefs | report intervals; make no per-class claims under 15 items (master plan §13.7) |

#### I9 No leakage (owner: Umaima)
- **Pass:** a poisoned fixture (`ground_truth_label`, `mutation_op`, `seed_ref`, `source` set to distinctive values)
  never changes the feature vector; grep test asserts those names are not importable from the feature builder;
  existing temporal tests (`test_history_model`, `test_state_transitions`) pass on Linux.
- **Possible failures:** `Submission.ground_truth_label` is a column on the same object the builder receives; pass
  only `source_code` + test results, never the ORM object.

#### I10 Performance (owner: Rayaan)
- **Pass:** model inference alone p95 < 50 ms; whole added path (features + g++ warnings compile + predict) p95 < 2 s
  *(proposed)* on the dev machine and in the Railway/Docker image; no more than 1 g++ invocation added per submission.
- **Possible failures:** warnings compile doubles latency (reuse the compile that runs the tests, capture its stderr
  with `-Wall -Wextra`); model loaded per request (load once at startup, assert in a test); cold start in the container.
  Fallback: run the model asynchronously and return the rule diagnosis first; the UI polls for the model block.

#### I11 Frontend (owner: Eman)
- **Pass:** `npm run lint` and `npm run build` exit 0; component tests (Vitest) cover: abstain state, OTHER_ERROR state,
  model absent (`null`), all 11 labels have a name, color and description (test iterates the label list); screenshots
  of student Result and teacher SubmissionDetail committed under `docs/ui/`.
- **Possible failures:** TypeScript build breaks because `types.ts` and the API diverge (generate types from the
  OpenAPI schema or add a contract test against a recorded response); a label missing from `labels.ts` renders
  "undefined" (the label-iteration test catches it); raw probabilities shown to students are misread as certainty
  (use bands: low < 0.5, medium 0.5-0.75, high > 0.75 *(proposed)*).

#### I12 End-to-end (owner: Umaima)
- **Pass:** scripted run on Linux: student logs in -> submits a bank variant -> gets execution result, diagnosis with
  model block, hint -> teacher opens the submission, sees rules/model/history, corrects the label -> correction stored
  as an audit event and original prediction preserved. Runs in CI, < 5 min, no flaky retry used to pass.
- **Possible failures:** bubblewrap blocked on the CI runner (`kernel.apparmor_restrict_unprivileged_userns=0`, already
  in `docs/CI_CD.md`); database state leaks between tests (use a fresh SQLite per run; note the repo contains two
  stray `.db` files, `tracelearn.db` and `tracelearn_test_*.db`, which should be git-ignored); timing flake on
  timeouts (use the existing 2 s limit with a deterministic infinite-loop fixture).

#### I13 CI (owner: Umaima)
- **Pass:** `ci.yml` `backend` job green on Python 3.11 and 3.12, `frontend` job green on Node 22, `dataset.yml` green;
  the 44 backend failures from this Windows machine are each either fixed or carry a `skipif` with a written reason;
  **no new skip added to make a gate pass** without a line in this file.
- **Possible failures:** tests pass locally on Windows but fail on Linux and vice versa (always trust the Linux run);
  Python 3.14 wheels for xgboost missing (the repo has both 3.12 and 3.14 `__pycache__`; pin 3.12, as the master plan G0b says).

### 5b.2 Data and model gates that block the integration (carried from the master plan)

| Gate | Pass criteria *(master plan unless noted)* | Evidence artifact | Current | Possible failures and response |
|---|---|---|---|---|
| **G1** resolvers | 0 labels<->normalized orphans, enums clean | `verify_dataset.py` exit 0 | pass | New lane rows lack proofs -> proof-join (`095878c`) only excuses SYNTHETIC with a committed proof; never blanket-excuse |
| **G4** Tier-0 floors | every class >= floor (200-300), rejection < 50%, >= 15 clusters/class, <= 3 mutants/seed | `verify_dataset.py --per-class-report` | **fail** (e.g. UNINIT 35, OTHER 13) | Seed starvation: use the pre-committed relaxations (per-seed cap 5, hand-written templates, or lower the floor with disclosure). Never pad with rejected mutants. Cut-line: ship at >= 150/class if unmet after week 3 |
| **G5** weak labels | every LF >= 50 audited fires at >= 90% precision; selection report | `lf_audits.csv`, `selection_report.md` | **not started** (pre-review says `lf_loop_boundary`, `output_pm1` misfire; CodeStream precision ~45%) | LF below 90% -> tighten or retire it; rows it labelled drop to review pool, not to training. Expect CodeStream weak rows to shrink |
| **G6** gold | 150 floor / 220 target + 60 dev-gold certain; Fleiss kappa >= 0.6 (4 raters); duplicates >= 8/10 | `gold_forms_report.md`, kappa report | **not started** | kappa < 0.6: revise guideline, re-annotate; per-class kappa < 0.4: merge candidate or "human-ambiguous" finding. The 150 floor is non-negotiable |
| **G7** splits | cluster / seed groups / twins across splits = 0, gold not in train, train-val PSI < 0.2 | `merge_report.json` | pass (PSI drift is reported, non-gating at merge) | New dev-gold clusters moved from train: re-run the merge, never hand-edit splits; PSI >= 0.2 on train/val at training -> investigate source shortcut |
| **G8** training | CV beats majority by >= 0.25; synthetic mass <= 50%; weight clip <= 10; class mass <= 15%; gold not in train | `metrics_v1.json` `g8` | **3 of 4** (synthetic mass 0.91) | Do **not** lower the cap or reweight. Needs real natural rows in synthetic-only classes (UNINIT, STALE_EXIT, WRONG_LOOP_DIR, RANGE_CHECK, ASSIGN, BASE_CASE). If still failing at H3, waive it in `DATASET_CARD.md` with the projected mass (0.75-0.81) |
| **G3** pilot go/no-go | macro-F1 >= 0.40 with bootstrap CI; S-only >= 0.30 on real rows; adversarial AUC < 0.75; full beats runtime+tests-only by >= 0.02 and beats static+warnings-only | `reports/g3_pilot.md` (**not written**) | **not run** | S-only < 0.30 means synthetic rows do not transfer to real code (dev-gold 0.24 suggests this is likely): then pre-registered merges via `label_mapping.csv`, family-level reporting, and the model is `shadow`-only. AUC > 0.85 means style leakage: ship `common` features only |
| **G9** final evaluation | per-class P/R/F1 with Wilson intervals, paired bootstrap vs rules, open-set false alarm <= 30%, scope statement "gold is CodeStream-only" | `final_evaluation.md` | **not started** | Difference vs rules under ~9 points with CI spanning zero: report as "inconclusive-directional", never as a win |
| **G10** independent re-run | someone other than Rayaan reproduces numbers from a clean checkout | re-run log | **not started** | Differences usually come from unpinned versions or untracked data (G: drive raw files); pin and document the raw-data requirement |

### 5b.3 Failure modes across the whole effort (what is most likely to go wrong)

| # | Failure | Early warning | Prevention / response | Owner |
|---|---|---|---|---|
| 1 | Model works offline, wrong in the app (train/serve skew) | I1 mismatches, I8 far below CV | Parity test first; ship `common`/`best`; `shadow` mode; report both numbers | Eman, Rayaan |
| 2 | Students shown a confident wrong label | I4/I7 abstain rate near 0%, high-confidence errors on bank variants | Router bypass, global threshold, "not sure" copy, teacher review flag | Rayaan |
| 3 | Real accuracy is poor and we only find out in January | dev-gold 0.24 today | Start G6 now; report CV and gold separately; never quote CV as accuracy | Umaima |
| 4 | Gold annotation slips | calibration round not done by end of week 2 | Cut to the 150 floor; external annotator takes more overlap items | Umaima |
| 5 | Synthetic-only classes never get natural rows | G8 mass still > 0.75 after sign-off | Disclose; family-level reporting; waiver at H3 | Rayaan |
| 6 | Backend suite red on CI, hides regressions | I13 | Week-1 triage; no merge on red | Umaima |
| 7 | Two taxonomies drift (dataset vs backend vs frontend) | I3 test failing, `undefined` labels in UI | One mapping table, tests iterate `label_encoder.json` | Rayaan, Eman |
| 8 | Model version changes under the demo | different sha in `/api/model/info` | Store sha256 on every submission; freeze model for the demo build | Rayaan |
| 9 | Windows-only work hides Linux bugs (sandbox, `fcntl`, bubblewrap) | works on Rayaan's machine, fails in CI | Run gates in WSL or CI, treat CI as the source of truth | all |
| 10 | Review churn: co-author/history rewrite breaks local branches | diverged branches after force-push | Agree once on history policy; fetch before each work session | all |
| 11 | One-shot test split opened too early | someone passes `--confirm-one-shot` | Only after gold is signed; the evaluator logs every run in `reports/holdout_evaluations.jsonl` | Rayaan |
| 12 | Hint text reveals the answer or contradicts the label | teacher review of 11-label hint table | Review every hint row against the belief definition before enabling the model for students | Eman |

### 5b.4 Gate calendar

| By end of | Must be green | May be red (with a written reason) |
|---|---|---|
| Week 1 (13 Nov) | I2, I3, I13 triage list, variant decision | I1 (in progress) |
| Week 2 (20 Nov) | I1, I4, I5, I6, backend API contract frozen | I8 |
| Week 3 (27 Nov) | I7, I8 result recorded, I11, dev-gold signed | G8 synthetic mass |
| Week 4 (4 Dec) | I9, I10, I12, I13, G7, G1; model mode decided (`on` or `shadow`) | G3/G5b/G6/G9/G10 (move to January-March plan) |

---

## 6. Plan by person

Roles follow the dataset master plan (Eman = Lane A / synthetic + features, Umaima = Lane B / sandbox harness +
labels, Rayaan = Lane C / contracts, merge, training) and the commit history (Rayaan 57, eman06 46, Umaima 47, non-merge commits).
**This is a proposal; swap items freely.**

### Rayaan (training, contracts, model serving)

| Week | Task | Done when |
|---|---|---|
| 1 | B2 `ModelClassifier` + B10 deps + I2/I3 tests | golden prediction test passes |
| 1 | B3 label mapping + B4 `MODEL` evidence source + weight config | rule+model fusion unit tests pass |
| 2 | B5 router + B6 flags + B7 persistence/migration + I4/I5/I6 | flag-off identity test green |
| 2 | B9 API fields and `/api/model/info`; freeze the response contract and send to Eman | contract merged, `types.ts` updated |
| 3 | I8 bank-variant evaluation (model vs rules) and write the result into `docs/` | numbers + interval published |
| 3-4 | Retrain after Umaima's sign-offs and Eman's new rows; re-run G8 and report (do not tune caps); update `DATASET_CARD.md` | metrics_v1 regenerated, honest G8 |
| 4 | Release checklist for the December build; tag `v0.2.0` | CD smoke job passes |

### Eman (features, data volume, frontend display)

| Week | Task | Done when |
|---|---|---|
| 1 | B1 `InferenceFeatureBuilder` (reuse `extractor.py`, `semantics.py`, `cpg_source.py`) + I1 parity test | parity gate passes for static/warnings/semantics |
| 1-2 | Fix any parity mismatch at the source (extractor), not by patching the model | zero unexplained mismatches |
| 2 | F1, F2, F6 types/labels/charts for 11 labels | `npm run build` green |
| 2-3 | F3 student Result + F4 teacher comparison view, abstain and OTHER_ERROR states | I11 screenshots |
| 3 | B8 hints for 11 labels; check the 40-problem bank maps to them | every label has hint levels 1-5 or a documented exception |
| 3-4 | Raise real/OTHER_ERROR volume: decoy generation (>= 100 pool) and more `expand_mutants` clusters for classes still under floor | G4 per-class report improves; synthetic mass projection published |
| 4 | F5 Research page + F7 frontend tests | I11 green |

### Umaima (execution harness, labels, Linux CI, human gates)

| Week | Task | Done when |
|---|---|---|
| 1 | Triage the 44 backend failures under WSL/Linux: real bug vs Windows-only; fix or mark; get `backend` CI job green | I13 |
| 1 | Decide how inference gets runtime features: (a) run `sandbox_runner` for model submissions, or (b) ship the static+warnings+semantics variant only. Write a one-page decision with latency numbers | decision recorded; Rayaan picks `MODEL_VARIANT` from it |
| 1-2 | Sign the spot-check rows in the five review sheets and run `apply_prereview_signoff.py` | `lf_audits.csv` non-empty; H2 mislabel rate measured |
| 2-3 | Calibration round (15 items) then dev-gold sign-off (>= 60 certain rows) | dev-gold >= 60 certain |
| 2-4 | Start gold annotation (220 target, 150 floor), blind forms, external annotator for the 45 overlap items | kappa computed; gold locked before January |
| 3 | I12 end-to-end test in CI (bank variant -> diagnosis -> hint -> teacher) | green on Linux |
| 4 | Security/abuse tests running for real in CI (not skipped) | `test_security.py` green on Linux |

### Shared (all three)

- Weekly 30-minute gate review using `scripts/run_gates.py` (to be written, see `docs/superpowers/plans/2026-10-29-remaining-work-plan.md` task 0.4).
- Problem bank: confirm 30-40 problems are assigned in the demo classroom and each has visible/hidden/diagnostic tests.
- Rehearse the full demo (blueprint §22.1 last bullet) in week 4 on a clean Linux checkout.

---

## 7. Schedule (weeks from 6 Nov)

| Week | Focus | Exit check |
|---|---|---|
| 1 (6-13 Nov) | Classifier + feature builder + Linux triage + variant decision | I1, I2, I3 |
| 2 (13-20 Nov) | Router, flags, API contract, frontend types, sign-offs start | I4, I5, I6 |
| 3 (20-27 Nov) | Frontend views, bank-variant evaluation, hints, dev-gold | I7, I8, I11 |
| 4 (27 Nov-4 Dec) | Retrain, G8 report, E2E in CI, demo rehearsal, tag | I9, I10, I12, I13 |
| Buffer | Fixes, report, demo video | Iteration 2 report |

Cut-lines: if week 3 slips, ship `shadow` mode with the teacher comparison view only (F4) and drop the student-facing
model text (F3); the rules stay the student-facing diagnosis.

---

## 8. Risks and open decisions

| Risk / decision | Mitigation / who decides |
|---|---|
| Train/serve skew (runtime features missing at inference) | I1 + I8; Umaima's variant decision; fall back to `common`/`best` |
| Model looks good in CV, poor on real code (dev-gold 0.24) | Ship in shadow first; judge on bank variants and gold; do not claim accuracy |
| OTHER_ERROR is weak (F1 0.20) and not a backend code today | B3 + I7: abstain and give generic guidance instead of a confident label |
| 8 of 11 classes have no natural train rows | Disclose; family-level reporting if G3b triggers |
| Backend failures hidden by running only on Windows | Umaima's week-1 Linux triage |
| Gold annotation is the long pole for any real accuracy claim | Start the calibration round in week 1-2 |
| 6 commits (eman06) still carry a Claude co-author trailer | Eman rewrites + force-pushes if wanted (team decision) |
| Open: do `CPP-M02` / `CPP-M03` stay rule-only (no model class)? | Rayaan + Eman, week 1 |
| Open: exact December date and which problems are in the demo set | Team |

## 9. Testing the model on real-world data (Rayaan's deliverable for the panel)

### 9.1 What "real-world data" we actually have

| Source | What it is | Usable for testing? |
|---|---|---|
| **CodeStream** (Mendeley, CC BY 4.0) | 5,482 real student submissions, 202 participants, 46 problems; 3,396 C/C++ rows already executed against the dataset's own tests (`reports/u1_executor_report.md`) | **Yes, the main one.** Test-side clusters: 12 clusters, **1,558 C/C++ submissions (789 failing, 452 accepted), 161 users**. No row from these clusters, and no mutant seeded from them, reached training (`reports/codestream_cluster_split.md`) |
| CodeStream dev-gold clusters | 4 clusters, 450 submissions (281 failing), 88 users | Yes, for **developing and debugging** the evaluation scripts and for calibration. Not for claims |
| **PROGPedia** (Zenodo) | ~9,100 real submissions, 12 problems with oracle tests (128 tests) | Partly. Already used in training (285 rows), so only leave-problem-out / dev-gold slices count as held-out. Verdicts exist, tests were rebuilt by us from ACCEPTED consensus |
| Project CodeNet | 237,512 files, **no verdicts, no tests** | **No.** Cannot know whether code is wrong or why. Using it for "accuracy" would be inventing labels (master plan §2.1) |
| TraceLearn pilot (planned Jan-Mar) | our own students, human-labelled | The only source that is real **and** ours; not available before the December panel |

### 9.2 What we may truthfully claim, and when

The docs are explicit (`Docs_Agents/...Normalization...Plan.md` §14, brief rule 7): **synthetic accuracy does not predict
real-world performance; a wrong submission does not prove a belief; weak-label agreement is not accuracy.** So "tested on
real-world data" is only defensible in the forms below. The label source decides which sentence is allowed.

| Evidence tier | Real code? | Labels | Allowed sentence | Available |
|---|---|---|---|---|
| **T1 Gold test** | yes, CodeStream test-side | blind human gold (target 220, floor 150), kappa >= 0.6 | "On N real student submissions from M users and K problem clusters never seen in training or tuning, labelled blind by four raters, the model scores macro-F1 X [CI] versus Y [CI] for the rule baseline." | after G6 (January) |
| **T2 Repair-confirmed** | yes, all 789 failing test-side rows | none needed: execution-verified repair | "On N real failing submissions, X% of the model's top predictions were confirmed by an automatic repair of that class making every test pass, versus Y% for a prior-matched random label and Z% for the rule engine." | December, once scripts exist |
| **T3 Behaviour on real code** | yes, 789 failing + 452 accepted | none | "On real code the model abstains on A% of failing submissions, flags B% of accepted submissions (should be ~0), and gives the same label on consecutive failed attempts of the same student C% of the time." | December |
| **T4 Sensitivity** | yes | gold + T2 | "Results are reported separately for students seen versus unseen in training, and for PROGPedia versus CodeStream." | with T1/T2 |
| **T5 Pilot** | yes, our classrooms | human labels | "In a pilot with P students ..." | Jan-Mar |

Until T1 exists, the only honest headline is T2 + T3, **plus** the cross-validation number described as "on a mostly
synthetic training pool". The dev-gold macro-F1 of 0.24 should be shown, not hidden: it is the current real-data
estimate on a small, partly weak set.

### 9.3 Protocol (pre-register this before running anything on the test side)

1. **Freeze.** Model sha256, variant, threshold, temperature, feature schema and the evaluation scripts are fixed and
   recorded in `reports/real_data_protocol.md` with a commit hash **at least 3 days before** the test-side run.
   Proposed freeze: end of week 3 (27 Nov), after the retrain.
2. **Develop on dev-gold clusters only.** Write and debug every script below on the 4 dev-gold clusters (281 failing
   rows). The 12 test clusters are touched once.
3. **Score all failing rows, not a sample.** Features for every failing test-side C/C++ row come from the same
   normalize + extract path used in training, from the cached executions (`cache/codestream_exec.jsonl`, gitignored,
   on Umaima's machine; or re-run `execute_codestream.py` in WSL with `G:` mounted).
4. **T2 repair confirmation** (new `scripts/eval_repair_confirmation.py`, built on `scripts/repair_verify.py`):
   for each row, take the model's top-1 class `c` (skip abstentions and `OTHER_ERROR`); call
   `verify(code, lang, tests, c)`; confirmed = some edit of class `c` makes every test pass. Controls on the same rows:
   (a) rule-engine top-1, (b) a random class drawn from the training prior, (c) **coverage ceiling** = share of rows
   where *any* class repairs. Report confirmation rate, coverage, and CIs by bootstrap resampled **by problem**.
5. **T3 behaviour** (new `scripts/eval_real_behaviour.py`): abstain rate; predicted-class histogram versus the gold
   random slice's prevalence; flag rate on the 452 accepted rows (via the full router); label stability on consecutive
   failed attempts by the same user on the same problem; "label disappears after the fix" rate (the next attempt passes,
   the previous attempt's label was non-abstaining).
6. **T4 sensitivity**: split every metric by (user seen in train?) and by source; report both.
7. **T1 gold** (`scripts/evaluate_holdout.py --split test --confirm-one-shot`, extended): per-class P/R/F1 with Wilson
   intervals, paired bootstrap versus rules by problem, McNemar exact, open-set false-alarm <= 30%, `firing_count`
   slices. One run, logged in `reports/holdout_evaluations.jsonl`.
8. **Baselines on identical rows:** majority, rule engine mapped to `tl-cpp-v2` (its UNCERTAIN counted as
   `OTHER_ERROR`), **logistic regression** (does not exist yet, blueprint §9.5 requires it), and the evidence ablations
   from blueprint §15.2 (static-only, warnings-only, tests-only, runtime-only, full).
9. **Everything generated by script into `reports/`; no number typed by hand** (POC rule: "no hard-coded accuracy").

### 9.4 Passing gates for the real-data evaluation *(proposed, agree before looking at results)*

| Gate | Pass criteria | Evidence |
|---|---|---|
| **RW0 Freeze** | protocol file committed >= 3 days before the test-side run; sha256 in it matches `/api/model/info` | `reports/real_data_protocol.md` |
| **RW1 Coverage** | features computed for >= 95% of the 789 failing test-side rows; the rest listed with reasons (compile fail, timeout, missing source) | `reports/real_scoring_coverage.md` |
| **RW2 Repair confirmation** | model confirmation rate >= prior-matched random + 0.15 (absolute), bootstrap CI lower bound > 0; not worse than the rule engine by more than 0.02 | `reports/real_repair_confirmation.md` |
| **RW3 Real-code behaviour** | abstain rate 10-60%; flag rate on accepted rows <= 2% (after router); label stability >= random-pair baseline | `reports/real_behaviour.md` |
| **RW4 Sensitivity** | seen-vs-unseen-student gap reported; if the gap in macro-F1 > 0.10, the unseen-student number is the headline | same reports |
| **RW5 Gold (T1)** | G6 passed; one-shot run; difference versus rules reported with the pre-registered reading ("inconclusive-directional" if CI spans zero) | `final_evaluation.md` |
| **RW6 Reproducible** | a teammate regenerates RW1-RW4 numbers from a clean checkout within tolerance | re-run log |

### 9.5 What can go wrong in the real-data evaluation

| Failure | Why it happens | What to do |
|---|---|---|
| T2 looks great but means little | **Circularity:** repair operators are the inverse of the mutation operators that created most training rows, so the model may simply recognise operator fingerprints. Real-code confirmation is independent evidence, but it is not independent *method* | State this in the report. Present T2 as supporting evidence only, never as accuracy; T1 gold is the claim |
| Low coverage ceiling (few rows are repairable by any single-edit operator) | Real bugs are often multi-edit or logic errors | Report coverage next to the rate; do not extrapolate to uncovered rows |
| Confirmation by coincidence (an edit passes tests that are weak) | CodeStream tests are few per problem | Require the repair to be minimal and re-run on the sanitizer pass; list problems with < 3 tests and report separately |
| `OTHER_ERROR` cannot be repair-checked | no operator exists for it | Exclude from RW2, report how many rows that is; evaluate it only on gold |
| Test-side peeking | scripts tuned after seeing test results | Develop on dev-gold clusters; freeze; one run; every run logged |
| Distribution shift hurts: model strong on mutants, weak on real code | G3(b) S-only < 0.30 is plausible given dev-gold 0.24 | Report honestly; ship `shadow`; use rules as default; the finding itself is publishable ("synthetic-trained classifiers do not transfer without real-row supervision") |
| Same course, same style | CodeStream is one course; 161 test users also appear in train | RW4 sensitivity; state external validity limit; the pilot is the answer |
| Accepted rows flagged | 39 "Accepted" rows fail the local tests (`u1_executor_report.md`), plus 344 Presentation Error rows pass | exclude rows whose local verdict disagrees with the source verdict from RW3, list them |
| Missing raw data on the demo machine | `G:` drive not mounted on this Windows host | commit only derived artifacts; document `TRACELEARN_RAW`; keep a cached results file for the panel |
| Licence / redistribution | CodeStream CC BY 4.0; PROGPedia terms "research only" (`DATASET_CARD.md`) | cite properly; never commit raw student code from restricted sources; check before showing code on slides |

### 9.6 What to say to the panel (and what not to)

**Say**
- "The classifier was trained on a mix of synthetic mutants and real student code, and evaluated on real student code
  from problems it never saw."
- "Without human labels we checked its predictions by execution: X% were confirmed by an automatic repair, against Y% for chance."
- "Human-labelled evaluation (blind, four raters, kappa reported) is scheduled; interim dev-gold macro-F1 is 0.24 on 45 rows."
- "It is a hypothesis generator with evidence and an abstain option, not proof of what a student believes."

**Do not say**
- "72% accuracy on real-world data." (That is cross-validation on a mostly synthetic pool.)
- "Tested on our students." (Pilot not run.)
- "The labels are ground truth." (Weak labels are 45-76% precise by our own pre-review; zero human-signed.)
- "XGBoost beats the rules." (Not measured on gold yet; blueprint §19.2 says to report the truth.)

**Likely questions**
| Question | Honest answer |
|---|---|
| How do you know it works on real students? | T2/T3 on 789 real failing submissions today; T1 gold in January; pilot after that |
| Isn't it just learning your synthetic bugs? | That is the main risk; that is why S-only, source-shortcut and adversarial-validation gates exist, and why dev-gold is only 0.24 |
| Why not use CodeNet's 237k files? | It has no verdicts or tests; labelling it would be guessing |
| Why should we trust the labels? | Three tiers: execution-verified synthetic, repair-verified real, human gold; weak labels are down-weighted and never used for evaluation |
| Same course in train and test? | Yes; sensitivity analysis reported; pilot with new students addresses it |

### 9.7 Rayaan's real-data tasks (added to your table in section 6)

| Week | Task | Done when |
|---|---|---|
| 1 | Write `scripts/score_real_rows.py` (features + predictions for all failing rows of a chosen split, from the exec cache) and run on dev-gold clusters | RW1 on dev-gold |
| 2 | `scripts/eval_repair_confirmation.py` with the three controls; run on dev-gold clusters | RW2 numbers on dev-gold, circularity paragraph written |
| 2 | Add logistic-regression + evidence-ablation baselines to the trainer; tests `test_baselines.py` | baselines reported on the same CV folds |
| 3 | `scripts/eval_real_behaviour.py`; write and commit `reports/real_data_protocol.md`; freeze model | RW0 |
| 4 | One run of RW1-RW4 on the 12 test-side clusters; panel slide with T2/T3/T4 and the honest caveats | RW1-RW4 green or explained |
| Jan | T1 gold run after G6 | RW5 |

---

## 10. Alignment check against the end-product docs

I read the blueprint (`Docs_Agents`), the dataset brief, the normalization plan, the master plan, and `docs/*`.
The plan above matches the end product on the main path (current-submission classifier -> temporal model -> hints ->
teacher), but these points do not line up yet.

| # | End-product requirement (source) | Current state | Action | Owner |
|---|---|---|---|---|
| A1 | Language: blueprint says Python primary ("can be shifted to C++"); dataset brief and master plan say C++; normalization plan §15 lists "Resolve the Python-versus-C++ discrepancy" as an open item | Backend runs both; model is **C++-only**; 6 Python problems remain | Write a one-page decision: product language = C++ for Iteration 2; Python stays on rules; update blueprint wording and slides | Rayaan + team |
| A2 | 8-12 **belief-style** classes (blueprint §1, TAXONOMY) | Three vocabularies: bank `CPP-M01..M08` (8), model 11 labels, backend 13 codes. Model has OFF_BY_ONE, INT_OVERFLOW, UNINIT, WRONG_LOOP_DIR that the bank does not test; bank M02/M03 have no model class; some model classes (ARRAY_BOUNDS, INT_OVERFLOW) are symptoms, not beliefs | One table `docs/TAXONOMY.md` mapping all three, flagging symptom-vs-belief classes and which are modeled, rule-only, or both | Eman |
| A3 | Temporal formula uses the classifier probability `P_t` (blueprint §10.4) | Plan feeds the model in as an evidence item only | Pass the calibrated model probability into `learner_model/updater.py` as `P_t`; test: one model-labelled failure never makes PERSISTENT | Rayaan |
| A4 | Baselines: majority, rule-only, **logistic regression**, XGBoost, evidence ablations (blueprint §9.5, §15.2) | No logistic regression exists anywhere in the repo | Add in trainer + report (task in 9.7) | Rayaan |
| A5 | Student-aware and problem-aware splits (blueprint §12.6) | Splits are problem-cluster-grouped; users overlap train and test by design | Student-overlap sensitivity (RW4) | Rayaan |
| A6 | Inference failure falls back to rule/test feedback and marks diagnosis uncertain; all model/config versions logged (blueprint §16.3) | B7 logs versions; no failure-path test | Add test: model file missing/corrupt/NaN vector -> rules answer, diagnosis flagged `UNCERTAIN`, no 500 | Rayaan |
| A7 | Metrics generated from DB/exports, never hard-coded (blueprint §18.2) | Research page exists; model numbers would be pasted | F5 reads `/api/evaluation`; model metrics come from `metrics_v1.json` via API | Eman |
| A8 | Evidence provenance for every output (blueprint §18.5) | Model block must list top features and model version | B7/B9 + F4 (already planned); add test that a diagnosis with a model block always has `model_sha256` | Rayaan |
| A9 | Teacher corrections preserve the original prediction and feed future datasets (blueprint §14.2) | Exists for rules; model prediction must be preserved too | Include model block in the audit record; test it | Eman |
| A10 | Remedial and transfer problems per misconception (blueprint §13.2); transfer success as strong counter-evidence | No remedial/transfer graph in the plan | Not required for December; add to January plan. Minimum for December: one remedial pointer per supported label in hint templates | Eman |
| A11 | Hint effectiveness (RQ5) and teacher usefulness (RQ6) need instruments before the pilot (blueprint §15, §19) | None | Draft pilot instruments, consent text and retention policy in January (blueprint §16.2: before the pilot) | Umaima |
| A12 | Local student data: 5-10 students on 10-15 problems in FYP-I (blueprint §12.4) | None planned | Schedule an informal 5-student session in weeks 3-4 on the demo build; collect submissions with consent; not for headline numbers | Umaima + Eman |
| A13 | Licences and redistribution (brief rule 14) | Model files are committed; raw data is not; PROGPedia "research only" | Confirm in writing that derived model + features may be shared; cite CodeStream CC BY 4.0 | Rayaan |
| A14 | Server-side **Python** execution listed in blueprint §22.1 | Backend supports C++; Python runs in a subprocess marked non-secure | Update deliverable wording to "C++ (and Python for the POC problems)" or harden Python sandbox; panel will notice | Team |
| A15 | Model confidence drives hint level and escalation (blueprint §13.1) | `hint_policy` uses learner state and rule confidence | Define the mapping model band -> hint level 1-5 in a table; test on fixtures | Eman |

None of these changes the critical path in section 4, but A1, A2 and A3 should be settled in week 1 because the label
mapping (B3), fusion (B4) and the frontend labels (F2) all depend on them.

---

## 11. Commands to reproduce the numbers in this file

```bash
python -m pytest -q --ignore=tests/test_progpedia_oracle.py          # root suite (Windows)
python scripts/verify_dataset.py --per-class-report                  # class floors
python scripts/train_xgb_misconception.py --cv-repeats 3             # regenerates metrics_v1.json
python scripts/evaluate_holdout.py --split test_iid                  # IID check (8 certain rows)
# python scripts/evaluate_holdout.py --split test --confirm-one-shot # ONE-SHOT: do not run before gold is signed
```
