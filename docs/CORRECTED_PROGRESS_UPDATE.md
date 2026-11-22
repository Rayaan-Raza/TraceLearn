# TraceLearn: corrected progress update

Corrects the progress report of 1 to 15 November 2026. Written 22 November 2026 by Eman Ihsan; each member approves their own section in the pull request.

The first report was drafted from commit messages. In several places it described what a commit was meant to do instead of what the repository shows, and the supervisor's audit found those places. This update goes through the claims again. Every claim gets one of five words, and no other:

- **Delivered**: the code is on main.
- **Run**: a generated result is committed, with its date and model hash.
- **Tool only**: the script exists; its output is not committed.
- **Held back**: attempted, then reverted or not merged, with the reason.
- **Planned**: not started.

## Dataset and model facts, in one place

- Pool on main (commit eec9639): 3,352 rows. PROGPedia 1,206, synthetic 1,064 (31.7%), CodeNet 707, CodeStream 375. Splits: train 2,444, test 674, dev-gold 209, test_iid 25.
- Served model: the execution variant of the plain profile, sha256 0af477c2. It trained on 1,349 rows (n_train in metrics_v1.json). The work plan splits these into 800 real-source and 549 synthetic rows; the committed files cannot confirm that split, and the ids of the 1,349 rows were never recorded (see docs/MODEL_LOG.md, 22 November entry).
- Labels: 2,265 rows carry label_source "human". Of those, 1,733 are agent consensus, 327 blind review and 13 human review. The flag does not mean a person labelled the row. A provenance sidecar (annotations/label_provenance.csv, PR #25) separates code origin, label origin and reviewer; the filters and the dataset-card table are still being moved onto it.
- Held-out results, classifier only, committed report of 9 November: on 525 programs from 20 problems, agreement with the recorded labels is 0.785, precision 0.807 (71/88) and recall 0.406 (71/175) when it names a class, false alarm 0.026. Always answering OTHER_ERROR scores 0.667 there. On 664 rows from 22 problems: 0.788, precision 0.721 (75/104), recall 0.368 (75/204); always-OTHER scores 0.693. This set has been scored many times and is a development set, not a blind one.

## How we describe the data

> TraceLearn uses real-source student code alongside synthetic training examples. Labels include agent-generated, weak-rule and human-reviewed annotations with differing levels of validation. Our held-out results measure agreement with those recorded labels.

## Claims, by member

### Rayaan Raza

| Claim in the first report | State | What stands |
|---|---|---|
| "real-only" XGBoost profile | Delivered | The plain profile trains on real-source rows plus three agent-written synthetic families: 800 real-source and 549 synthetic rows. |
| Multi-annotator labels for 1,123 real PROGPedia failures | Delivered | Two annotator agents of the same model family labelled 1,123 failures; a third adjudicated disagreements. [Rayaan to add what a person checked.] |
| Second and third opinions on 322 CodeStream failures | Delivered | 322 items: 178 agreed three of three, 138 two of two, 6 two of three, all by agents. |
| Froze an 84-item blind set for final evaluation | Run | The 84-item set was scored on 6 November (three logged runs of the final set in holdout_evaluations.jsonl) and is now historical. A new set is being built. |
| The execution model decides by default | Delivered | The default path is rules, then repairs, then the classifier, with the rule engine as fallback. |
| Decides "without slowing the request path" | Planned | Not measured. To be replaced by the two measured latencies from task R6. |
| Reviewed most of the team's pull requests | Delivered | Reviewed pull request #16 (review commit 8a72c08). |

### Umaima Zeeshan

| Claim in the first report | State | What stands |
|---|---|---|
| First sign-off round: 135 rows signed | Delivered | 135 sign-off entries by one rater. 45 labels changed after the model's answer was revealed, so these are partly anchored reviews, not independent gold labels. |
| Four-rater calibration round, kappa 0.76 | Run | Four raters on 15 items, kappa 0.76, 12 unanimous. A readiness exercise before a gold round. It does not measure agreement on LOOP_BOUNDARY against OFF_BY_ONE. [Umaima to name the external rater's role.] |
| Decision note to serve the best variant | Held back | The 8 November note recommended the best variant. On 9 November the backend moved to the execution variant with background run records. |
| Fixed learner-state recovery | Delivered | Recovery and recurrence are fixed and tested on Python problems P05 and P06. The C++ path with the model on is being tested now (task U3). |
| Poster review | Planned | The poster was not supplied to the audit. It will be committed with its source (task E6). |

### Eman Ihsan

| Claim in the first report | State | What stands |
|---|---|---|
| Extended four repair generators | Held back | Attempted for stale-exit, range-check, uninitialised-variable and int-overflow. Reverted in review commit 8a72c08, because the live run record uses those files and the change would have altered the served model's input. Held for a separate PR after the PR #17 decision. |
| Manifest pins the training snapshot | Tool only | Added the manifest generator and a trainer hook. No manifest was committed for the model served on 15 November. PR #23 fixes the Windows check, adds the model hashes and the trained row ids, commits a manifest and runs the check in CI. |
| Problem-weighted macro-F1 in the report | Tool only | Added the code. The committed report is still the 9 November run; PR #21 regenerates it. |
| Confidence band mapped to hint level | Delivered | The policy and its fixture tests are on main. That the submission service passes a prediction to it is Planned: PR #20 does it and PR #24 tests it end to end. |
| Research page shows live metrics | Delivered | Mode and variant are live. The performance figures are the committed training metrics, and will be captioned with their population, date and model hash. |
| Conflict-finding tool | Delivered | The tool and a 19-row queue. No row has been relabelled (task U4). |
| Sparse-class and coverage audits | Tool only | Both scripts select on the human flag, which includes agent-labelled rows. No output is committed. |
| Stabilised the calibration threshold | Delivered | Added a warning when a retrain moves a threshold by 0.10 or more, and a bootstrap median for the dev-gold threshold. The per-variant bootstrap already existed; its 5th to 95th percentile range was 0.38 to 0.69. |
| --force guard on the served model | Delivered | Joint with Rayaan's review fix, which corrected which file is guarded. |
| Hint templates, teacher panel, charts, Vitest tests | Delivered | On main. The frontend CI job does not yet run npm test, and one component test copies the component's logic instead of mounting it (task E3). |
| Poster | Planned | Not supplied to the audit. The editable source and a PDF will be committed under docs/poster/ (task E6). |

## Wording fixed in the repository

- DATASET_CRITIQUE_PLAN.md: rows 1, 3, 10 and 11 said done for what are scripts; they now say tool only. The conflict queue is 19 rows, not about 40.
- DATASET_CARD.md and README.md: current counts at the top, the v0.6 tables kept under a history heading.
- The generated heldout_eval.md still says labels are "treated as human on the owner's instruction". It is left alone and changes when the report is regenerated (PR #21).
- Searching the Markdown files for "real-only" finds it only in two reports that name a real-only experiment with its own model and result.

## Module inventory against the blueprint

The requirement list is section 22.1 of docs/TraceLearn_FYP_Master_Design_and_Implementation_Blueprint.md ("Required by December"). The blueprint was written for Python; the product now teaches C++ and the 40-problem C++ bank is in data/cpp_diagnostics/. "Partial" means part of the module is running and part is not.

| Module | State | Test or source |
|---|---|---|
| Student and teacher platform with browser editor | Implemented | frontend/src/pages; backend/tests/test_milestone1.py |
| Server-side execution, visible, hidden and diagnostic tests | Implemented | backend/tests/test_execution.py, test_cpp_end_to_end.py |
| 30 to 40 integrated problems, 8 to 12 misconceptions | Implemented | 40 C++ problems on 8 bank misconceptions (the model has 11 classes): test_cpp_problem_bank.py |
| Multi-source evidence extraction with provenance | Implemented | test_run_record.py, test_model_run_record.py |
| Rule baseline and XGBoost pipeline | Partial | test_xgb_classifier.py, test_model_runner.py. The runtime scored by the evaluation is not yet the one reported (R5, PR #21) |
| Temporal learner model with no-future-leakage tests | Partial | test_history_contract.py, test_state_transitions.py. Recovery is tested on Python only; C++ with the model on is task U3 |
| Five-level adaptive hint policy | Partial | test_hint_model_band.py. The real submission path does not yet pass a prediction (R4, PR #20; E2, PR #24) |
| Teacher evidence and correction workflow | Partial | A teacher review endpoint (backend/app/api/teachers.py) and the evidence view exist; the panel does not yet say which stage decided (E3). Effects of a correction on learner state are iteration 3 work |
| Public-data ingestion and local data collection | Implemented | tests/ dataset suite; provenance sidecar (PR #25) |
| Initial labelled evaluation, reproducible metrics | Partial | Held-out report exists; reproduction by a second person is task U2 |
| Full classroom to teacher demonstration | Partial | test_cpp_end_to_end.py covers diagnosis, state and hints; the shipped-defaults lifecycle is tasks E2 and U3 |

## Still open

- Approvals: each member approves their own section in the pull request. The two bracketed sentences are for Rayaan and Umaima to finish.
- Counts marked as computed from the work plan (800 real-source, 549 synthetic) cannot be checked from committed files.
