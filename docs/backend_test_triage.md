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
| **Windows** (Umaima's laptop, `pytest backend/tests` alone, `TRACELEARN_SKIP_CPP_VERIFY=1`, older branch with 191 tests) | **1 failed**, 186 passed, 4 skipped: the memory-limit check, see #5 |

## Causes and fixes

| # | Failure | Cause | Fix | Status |
|---|---|---|---|---|
| 1 | `test_history_contract::test_contract_partitions_every_source_type` (fails on Linux, so `main` was red in CI) | PR #6 (learner-state contract) requires every `EvidenceSourceType` to be observed or longitudinal; PR #7 added `MODEL` to neither. Each PR passed alone. | `MODEL` placed in a third group `DERIVED_SOURCES`, behaviour unchanged (still read by neither mode until the router B5 places it; never counted as observed support). New test pins it. | fixed, `344d65d`; superseded 9 Nov: `#13` made `MODEL` observed support (with `model_first` its prediction is the diagnosis and must reach the learner state), so `DERIVED_SOURCES` was removed when `#11` merged `main` |
| 2 | 27 backend failures/errors when `pytest` runs from the repo root | `backend/tests/__init__.py` makes `backend/tests` the package `tests`, the same name as the root `tests/` folder. Collected together, the backend conftest runs twice under two names, and the app settings no longer match the throwaway test database, demo-endpoint and invite-code settings it sets up. Tests then hit the real `tracelearn.db` (8 problems instead of 6, demo endpoints off, etc.). This is also where the stray `tracelearn_test_*.db` files come from. | `pytest.ini`: `testpaths = tests`, so a bare `pytest` runs the dataset suite only; the backend runs with `pytest backend/tests` (as CI always did). | fixed |
| 3 | Every test run modified two tracked files (`data/cpp_*/exports/verification_report.json`) | `test_full_verification_passes` ran the verifier scripts, which rewrite the committed report | `--no-export` flag on both verifier scripts; the tests pass it (also forwarded through the WSL hand-off on Windows) | fixed |
| 4 | `tests/` (merge, training, evaluation, review scripts: 366 tests) never ran in CI | `dataset.yml` runs only `tests/misconception_dataset`, and only on some paths | new `dataset-scripts` job in `ci.yml` (Python 3.12, `requirements.txt`) | added |
| 5 | `test_security::test_sandbox_timeout_and_output_limits` on Windows: the 8 GB allocation returns `timeout`, not `runtime_error` | The memory cap is a POSIX rlimit (`RLIMIT_AS` / `prlimit --as`). Windows has none, so the allocation is not refused and runs until the time limit, and it can exhaust the laptop's memory. The sandbox docstring already says the Windows path is not safe for untrusted code; production runs on Linux. | Split into `test_sandbox_timeout` (all platforms) and `test_sandbox_memory_limit` (`skipif(os.name != "posix")` with the reason) | fixed |
| 6 | The rest of the reported 44 | Run alone, `backend/tests` on Windows has no other failure, so the remainder came from the combined root-level run (#2) on that machine | none needed | closed |

## How to run the tests

```
python -m pytest                    # dataset / model scripts (tests/)
python -m pytest backend/tests      # backend; on Linux install g++ and bubblewrap first
```

Do not run both suites in one process (see `pytest.ini`). On Windows use `py -m pytest`. Set
`TRACELEARN_SKIP_CPP_VERIFY=1` to skip the two C++ bank verification runs, which go through WSL
and can take a long time there. Trust the Linux CI result for anything that touches the sandbox.
