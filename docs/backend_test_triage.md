# Backend test triage (I13, week 1)

Owner: Umaima · 8 Nov 2026 · branch `feature/umaima-iter2-triage` from `main` @ `692f0c7`

The 6-Nov status said the backend had **24 failures + 20 errors (44)** on a Windows machine,
"probably Linux-only, not yet confirmed". This file records what was checked on Linux, the
platform CI and the server use.

## Result

| Run (Linux, Python 3.12, g++ 13, bubblewrap) | Result |
|---|---|
| `pytest backend/tests` with bubblewrap (`SANDBOX_MODE=bwrap`, as in CI) | **1 failed**, 246 passed: a real bug, fixed below |
| same, after the fix | **248 passed** |
| same, without bubblewrap (rlimit-only path, as on a dev machine) | 246 passed, 2 skipped (sandbox-isolation tests skip by design) |
| same, with the sandbox's **Windows code path forced** (`IS_POSIX = False`) | 246 passed, 1 failed: `test_sandbox_blocks_files_network_and_env`, which needs Linux isolation by design |
| `pytest` **at the repo root** (old behaviour: collects `backend/tests` and `tests/` together) | **9 failed + 18 errors** in `backend/tests` (test_security 19, test_problem_bank 3, test_milestone1 2, test_diagnosis 2, test_mandatory_contracts 1) |
| `pytest tests` (dataset scripts) | 366 passed, 3 skipped (+ 73 in `tests/misconception_dataset`) |

## Causes and fixes

| # | Failure | Cause | Fix | Status |
|---|---|---|---|---|
| 1 | `test_history_contract::test_contract_partitions_every_source_type` (fails on Linux, so `main` was red in CI) | PR #6 (learner-state contract) requires every `EvidenceSourceType` to be observed or longitudinal; PR #7 added `MODEL` to neither. Each PR passed alone. | `MODEL` placed in a third group `DERIVED_SOURCES`, behaviour unchanged (still read by neither mode until the router B5 places it; never counted as observed support). New test pins it. | fixed, `344d65d` |
| 2 | 27 backend failures/errors when `pytest` runs from the repo root | `backend/tests/__init__.py` makes `backend/tests` the package `tests`, the same name as the root `tests/` folder. Collected together, the backend conftest runs twice under two names, and the app settings no longer match the throwaway test database, demo-endpoint and invite-code settings it sets up. Tests then hit the real `tracelearn.db` (8 problems instead of 6, demo endpoints off, etc.). This is also where the stray `tracelearn_test_*.db` files come from. | `pytest.ini`: `testpaths = tests`, so a bare `pytest` runs the dataset suite only; the backend runs with `pytest backend/tests` (as CI always did). | fixed |
| 3 | Every test run modified two tracked files (`data/cpp_*/exports/verification_report.json`) | `test_full_verification_passes` ran the verifier scripts, which rewrite the committed report | `--no-export` flag on both verifier scripts; the tests pass it (also forwarded through the WSL hand-off on Windows) | fixed |
| 4 | `tests/` (merge, training, evaluation, review scripts: 366 tests) never ran in CI | `dataset.yml` runs only `tests/misconception_dataset`, and only on some paths | new `dataset-scripts` job in `ci.yml` (Python 3.12, `requirements.txt`) | added |
| 5 | Remaining Windows-only failures (44 − 27 ≈ 17, if the 44 came from a root-level run) | Not reproducible on Linux. Likely: no bubblewrap or `resource` limits on Windows, `wsl` hand-off in the C++ bank verification, file locks on SQLite and temp dirs | **Need the list:** run `python -m pytest backend/tests -q -rfE` on the Windows machine and paste the summary. Each one then gets a fix or a `skipif(os.name != "posix", reason=...)` | open |

## How to run the tests

```
python -m pytest                    # dataset / model scripts (tests/)
python -m pytest backend/tests      # backend; on Linux install g++ and bubblewrap first
```

Do not run both suites in one process (see `pytest.ini`). On Windows, trust the Linux CI
result for anything that touches the sandbox.
