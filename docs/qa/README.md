# Iteration 1 QA evidence

QA of Iteration 1 on 10 Oct 2026, run by Eman. GenAI (Claude) was used to run the QA and draft the fixes. The team reviewed every change and tested it before keeping it.

## What was tested

| Area | How | Evidence |
|---|---|---|
| RBAC, CSRF, data access between users | 77 API checks against a live backend | `api_qa.py`, `api_qa_results_v2.json` |
| C++ pipeline on the whole bank | Each of the 40 reference solutions, 43 misconception variants and 4 hard negatives submitted through the API | `bank_e2e.py`, `bank_e2e_results.json` |
| Attempt numbers under concurrent submits | 8 parallel `POST /api/submissions` | `race.py` |
| Sandbox isolation (files, env, network) | C++ probe under bubblewrap | `sandbox_probe.py` |
| Memory and output limits | 512 MB allocation; too much output | `memprobe.py`, `outlimit_linux.py` |
| Evidence per submission | Dumps the evidence of given solutions | `evidence_dump.py` |

The scripts need a running backend on `http://127.0.0.1:8000` with `TEACHER_SIGNUP_CODE=qa-teacher-code-2026`. They create their own test accounts.

## Results: before and after the fixes

| Check | Before (`12c3c26`) | After (`fb94119`) |
|---|---|---|
| pytest, Linux + bubblewrap | 166/168 | 191/191 |
| pytest, Windows | 159/168, C++ could not run | 189 passed, 2 skipped (bubblewrap only) |
| API checks | 75/77 | 77/77 |
| Correct solutions → NO_MISCONCEPTION | 18/40 (15 sent to review) | 40/40 (0 sent to review) |
| Hard negatives → NO_MISCONCEPTION | 0/4 | 4/4 |
| Variants with the correct label | 38/43 | 40/43 |
| Synthetic experiment accuracy (both modes) | 0.47 | 0.87 |
| 8 concurrent submits | `[1,2,2,2,2,4,7,7]` | `[1..8]` |

Fixes: commit `fb94119` "after QA". Regression tests: `backend/tests/test_iteration1_regressions.py`. CI run 38061789808 passed on `fb94119`.

## Reports

- `TraceLearn_QA_Iteration1.md`: the first QA run and its findings (F1–F12).
- `TraceLearn_QA_Iteration1_v2.md`: the re-test after the fixes, and the open items.

## Open items (not changed in Iteration 1)

- The history-aware mode does not change any prediction (`history_changed_predictions = 0`).
- The learner states RESOLVED and RECURRED cannot be reached in `learner_model/updater.py`.
- When diagnostic tests disagree, the attempt always goes to review (labelled case SYN005). This is a design decision for the team.
- On Windows there is no sandbox. Use it for local development only.
