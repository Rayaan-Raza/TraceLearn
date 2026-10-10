# TraceLearn — Iteration 1 re-QA after fixes

**Base:** `main` @ `12c3c26` (includes the partner's "score the C++ diagnostic bank end to end" commit)
**Fixes:** local branch `qa/iteration1-fixes`. The changes are **uncommitted and not pushed**.
**Date:** 2026-10-10

## Verdict: Iteration 1 is done end to end ✅

Every item on the Iteration 1 list works end to end, on Windows (native) and on Linux (bubblewrap sandbox). One design question about review flagging remains open for the team (section 4). It does not block any Iteration 1 item.

| Iteration 1 item | Status | Evidence |
|---|---|---|
| RBAC | ✅ | 77/77 API checks: roles, 404 between users and classes, CSRF, logout revocation, rate limits. The frontend sends users to their own role's pages. |
| Monaco integration | ✅ | The editor loads with C++ highlighting and starter code. Code typed and submitted runs (typing tested in the first QA round; this round used the Submit button). |
| Server-side C++ execution pipeline | ✅ | **Windows now works.** All 40 reference solutions pass. Wrong answer, crash, timeout and compile error each get their own status. The sandbox probe on Linux reads no files, secrets or network. |
| Schema normalisation | ✅ (for Iteration 1) | Attempt numbers are unique (DB constraint plus retry). One vocabulary mapping now exists (`cpp_mapping.py`). |
| Draft misconception taxonomy | ✅ | 3 Python and 10 C++ codes are scored. All 8 bank misconceptions (`CPP-M01`…`M08`) map and reach a diagnosis. |
| Early-stage evidence extraction | ✅ | 43 bank variants run through the live API: 40 get the right label. 40/40 correct solutions and 4/4 hard negatives give `NO_MISCONCEPTION`. |
| Submission logging + basic evidence capture | ✅ | Source, timestamp, status, test results, evidence, hints and teacher reviews are stored. The concurrent-submit race is fixed. |

## 1. Test results (final code)

| Run | Before | After |
|---|---|---|
| pytest, Linux + bwrap | 166/168 | **191/191** |
| pytest, Windows | 159/168 | **189 passed, 2 skipped** (both need bubblewrap) |
| C++ verifier (581/501 checks) | Failed (memory probe; WSL distro) | **Passes, also from Windows** |
| Live API QA script | 75/77 | **77/77** |
| C++ bank E2E: correct solutions labelled `NO_MISCONCEPTION` | 18/40 (15 sent to review) | **40/40** (0 sent to review) |
| C++ bank E2E: hard negatives (correct but suspicious-looking code) | 0/4 | **4/4** |
| C++ bank E2E: misconception variants correctly labelled | 38/43 | **40/43** |
| Synthetic experiment, diagnosis accuracy (both modes) | 0.47 (macro F1 0.51) | **0.87** (macro F1 0.71) |
| Concurrent submits, 8 parallel | `[1,2,2,2,2,4,7,7]` | `[1..8]` |
| `npm run lint` / `npm run build` | 0 errors | 0 errors (5 warnings that were already there) |

## 2. What changed

### Your requests
1. **Windows.** C++ ran in the wrong folder on Windows; the program path is now made absolute (`sandbox.py`). The 40-problem bank is pinned to LF (`.gitattributes`). The verifier skips Docker's WSL distro and picks one that has g++ (`TRACELEARN_WSL_DISTRO` overrides it). The PID-namespace test is skipped without bubblewrap.
2. **No Python questions, no Language column.** The new `api.practiceProblems()` filters out Python. It is used by Practice, the Dashboard recommendations and the teacher's Assign picker. The Language column, the Dashboard "C++" badge and the language text in the Assign picker are removed. Python problems can still be opened by ID, so the synthetic students' history and the research page still work.
3. **Filler text removed:**
   - Progress: "No patterns yet…" card, page subtitle, chart subtitles.
   - Dashboard: "Nothing flagged yet…", the tagline, chart subtitles.
   - Result: "Why this matters" card, "Hints get more specific…", "TraceLearn compared your output…", "No clear pattern yet", "TraceLearn looked at this attempt…", "Keep going…".
   - Submissions and Practice: subtitles.
   - Teacher pages: Research subtitle, the first-classroom blurb, the StudentDetails explanation, the Students tagline, and the long empty-state sentences (shortened to "No … yet.").
   - **Kept on purpose**, because they carry information: chart axis labels; "Your teacher will review this attempt."; the stdin/output note on the teacher's create-problem form; the "affects SYN students only" warning on the demo reset; the join-code instructions.

### Bug fixes within Iteration 1
| # | Fix | File(s) |
|---|---|---|
| F2 | A fully passing submission gets a confident `NO_MISCONCEPTION` (0.80, no review). It is no longer `UNCERTAIN` with a review flag. The new `TEST_ALL_PASSED` evidence says "all tests passed". A code pattern or an earlier attempt alone cannot override passing diagnostic tests. | `test_analyzer.py`, `confidence.py`, `evidence_weights.yaml` (`no_misconception_confidence`) |
| F3 | Conflict evidence now *lowers* the score. It used to add +0.1, because a negative weight was subtracted. | `rules.py` |
| F4 | New `wrong_answer` status, separate from `runtime_error`. | `models.py`, `test_runner.py` |
| F6 | Unique `(student, problem, attempt)` constraint with retry. A migration adds the index to existing DBs. Replaying a demo sequence twice returns 409 "reset first". | `models.py`, `database.py`, `submission_service.py`, `demo_service.py`, `demo.py` |
| F7 | One hint source for both paths. The first hint is always level 1, from the problem's own bank hints. It used to jump to a level-3 template. A correct submission gets no hint. | `hint_policy.py`, `api/submissions.py` |
| F10 | The memory-limit probe reads its buffer, so g++ 15 cannot optimise the allocation away. | both `verify_cpp_*.py` |
| F11 | `.gitattributes` covers `data/cpp_diagnostics`. | `.gitattributes` |
| New | The C++ "assignment in condition" detector flagged `<=`, `>=` and `!=` as assignments. That flagged correct code and then spread to every later problem through history. | `cpp_static.py` |

`backend/tests/test_iteration1_regressions.py` has 13 regression tests for these fixes. Four existing tests relied on duplicate attempt numbers, or compared confidences across different labels. I updated them; each one keeps its original intent.

## 3. Things outside Iteration 1 that the team should know about
- **History never changes a prediction.** `history_changed_predictions = 0` both before and after these fixes. The two modes give the same result on all labelled data. This is the core research comparison, so it matters for a later iteration.
- **Learner states never reach IMPROVING or RESOLVED.** Learner-state accuracy is 0.27 before and after; IMPROVING and RESOLVED never occur, although the README demo describes NEW → PERSISTENT → IMPROVING.
- **No sandbox on Windows.** Without bubblewrap, student code runs with no isolation. That is acceptable for local development only; production must be Linux with bwrap. The README already says this.
- **Blank submissions get high confidence.** An empty `main` is diagnosed as "missing return" at 100% confidence, because 3 diagnostic failures × 0.35 is clamped to 1.0.

## 4. Open design decision (not changed)
**Review flagging when diagnostic tests disagree.** When one diagnostic test passes by accident, the attempt is always sent to review. For example, n = 0 sums to 0 with both `<` and `<=`. This happens to CP01 and to the textbook Python off-by-one. Those cases then get only the generic hint, which affects 10 of the 43 variants.

I tried to relax this, but it breaks the team's labelled case SYN005, which is meant to require review. SYN005 behaves *exactly* like the textbook bug on every test. So this is a research call:
- change the D1 inputs in the bank so they tell the two versions apart, or
- relabel SYN005.

## 5. How to reproduce
```
python -m pytest backend/tests -q
python scripts/run_synthetic_experiment.py
```
QA scripts are in `C:\Users\USR\tlqa\qa\`: `api_qa.py`, `bank_e2e.py`, `race.py`, `sandbox_probe.py`. The full fix diff is `iteration1_fixes_backup.patch`.
