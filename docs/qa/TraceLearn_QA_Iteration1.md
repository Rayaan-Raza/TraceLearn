# TraceLearn — QA Report, Iteration 1

**Repo:** github.com/Rayaan-Raza/TraceLearn (`main` @ `60f6ffe`, 61 commits)
**Date:** 2026-10-10
**Environments tested:**
- Windows 11, Python 3.11.9, g++ 13.2 (MinGW), Node 22: native dev setup as the README describes.
- Linux (Kali WSL2), Python 3.13, g++ 15.2, bubblewrap: same setup as CI, with `SANDBOX_MODE=bwrap`.
- Live app: backend on Linux with the sandbox on, frontend (Vite) on Windows, driven through the browser and an 77-check API script.

---

## 1. Verdict per Iteration 1 item

| Item | Verdict | Summary |
|---|---|---|
| RBAC | ✅ **Pass** | Every access rule I tested held (≈50 checks). |
| Monaco integration | ✅ **Pass** | The editor loads with C++ highlighting and the starter code. Typed code is submitted correctly. |
| Server-side C++ execution pipeline | ⚠️ **Pass on Linux, broken on Windows** | Compile, run, timeout, crash and sandbox isolation all work on Linux. On Windows every C++ run fails (F1). A wrong answer is stored as `runtime_error` (F4). |
| Schema normalisation | ⚠️ **Partial** | The core tables and foreign keys are sound. Misconception IDs have no table or foreign key, and there are no uniqueness constraints where the design needs them (F8, F9). |
| Draft misconception taxonomy | ⚠️ **Present, not unified** | Three separate ID vocabularies exist. The diagnosis only scores the 3 Python IDs (F5, F8). |
| Early-stage evidence extraction | ⚠️ **Works, scoring has bugs** | Evidence is extracted and stored with source, direction and weight. C++ static evidence is dropped, conflict evidence raises confidence, and correct code is never classed as "no misconception" (F2, F3, F5). |
| Submission logging + basic evidence capture | ⚠️ **Works, with defects** | Source, timestamp, status, test results, evidence, hints and teacher reviews are all stored. Attempt numbers can duplicate under concurrency (F6). Hint escalation never goes past level 1 (F7). |

**Automated tests:**

| Environment | Backend (pytest) | Frontend |
|---|---|---|
| Linux + bwrap | 166 / 168 pass (both failures are F10) | `npm run lint`: 0 errors, 5 warnings. `npm run build`: OK |
| Windows | 159 / 168 pass (failures: F1, F11, verifier needs WSL) | same |

---

## 2. Findings (most severe first)

### F1 — HIGH — C++ never runs on Windows ("Execution failed to start")
`backend/app/execution/cpp_runner.py:35`, together with `sandbox.py` `run_in_sandbox`.
The binary is launched as `./solution.exe` with `cwd=workdir`. On Windows, `subprocess.Popen` looks up a relative executable from the *parent's* working directory, not from `cwd`, so it raises `FileNotFoundError`. Compilation succeeds, but every test returns `system_error`. The README says Windows works for development, but on Windows no C++ problem can be solved.
**Repro:** on Windows, `pytest backend/tests/test_security.py::test_cpp_correct_solution_passes`.
**Fix:** pass the absolute path (`str(workdir / BINARY_NAME)`) when bwrap is not in use. I verified that this works.

### F2 — HIGH — A correct submission is never diagnosed `NO_MISCONCEPTION`
`backend/app/diagnosis/confidence.py:78-85`.
With no evidence, the code sets `primary = NO_MISCONCEPTION, pconf = 0.2`. Then `0.2 < review_confidence (0.35)` changes it to `UNCERTAIN` and sets `requires_teacher_review = True`.
**Result:** every correct submission, Python (P01) or C++ (CP01), is shown as *UNCERTAIN · needs review*. It also fills the teacher review queue and the "Needs review" chart with correct work.

### F3 — HIGH — Conflict evidence *raises* confidence
`backend/app/diagnosis/rules.py` `aggregate_scores`: `scores[mid] -= rec.weight * 0.5`.
The conflict weights are already negative (`conflicting_diagnostic: -0.20`), so this adds +0.10 instead of subtracting it.
**Observed:** CP01 off-by-one. The evidence is 0.35 + 0.35 with one conflict, but the reported confidence is **0.80**. It should be 0.60.
This affects the core research metric (confidence and the comparison between the two modes).

### F4 — MEDIUM — Wrong answer is stored as `runtime_error`
`backend/app/execution/test_runner.py:137`.
If the program exits 0 but fails tests, the overall status becomes `runtime_error`, because `ExecutionStatus` has no `wrong_answer` value. Submission logs, the CSV exports and any status-based evidence cannot tell a crash from wrong output.

### F5 — MEDIUM — C++ static evidence is extracted, then thrown away
- `aggregate_scores` only creates score slots for `ALL_MISCONCEPTIONS` (the 3 Python IDs). Evidence tagged `CPP_LOOP_BOUNDARY` and the other C++ IDs is dropped without notice.
- `apply_evidence_weights` has no entry for any `CPP_*` code, so they fall back to weight 0.05.

The C++ diagnosis currently works only because the *diagnostic test* evidence is tagged with the Python `M01_LOOP_BOUNDARY` ID. For C++ misconceptions with no Python equivalent (assignment vs comparison, missing base case, overflow, and so on), the static analyser contributes nothing.

### F6 — MEDIUM — Duplicate attempt numbers under concurrency
`backend/app/services/submission_service.py:22` uses `attempt_number = prior_count + 1`, and `submissions` has no unique constraint.
**Repro:** 8 parallel `POST /api/submissions` produced attempts `[1, 2, 2, 2, 2, 4, 7, 7]`. A double-clicked Submit button can do the same. The history-aware mode depends on attempt order.

### F7 — MEDIUM — Hint escalation is stuck at a generic level 1
`backend/app/hints/hint_policy.py`.
- Any diagnosis that is `UNCERTAIN` or `requires_teacher_review` gets the generic hint. Because of F2 and F3, that is almost every submission.
- The 120 C++ bank hints seeded into the `problem_hints` table are never read. The policy only uses the Python `HINTS` templates.

In the UI the result page shows "HINT · LEVEL 1 OF 1 — Re-read the problem…", even though CP01 has 3 written hints.

### F8 — MEDIUM — Three different misconception vocabularies
| Where | IDs |
|---|---|
| `diagnosis/taxonomy.py` (scored) | `M01_LOOP_BOUNDARY`, `M02_INDEX_VALUE`, `M03_MISSING_RETURN` |
| `diagnosis/taxonomy.py` (C++, not scored) | `CPP_LOOP_BOUNDARY` … `CPP_WRONG_LOOP_DIR` |
| `data/cpp_diagnostics/problems.json` (`cpp-taxonomy-0.1`) | `CPP-M01` … `CPP-M08` |

There is no `misconceptions` table. `misconception_id` is free text (`String(64)`) in 5 tables, with no foreign key. A spelling mistake or mixed ID is accepted without any error. This is a schema-normalisation gap and a taxonomy gap at the same time.

### F9 — LOW — Missing uniqueness constraints
- `learner_states`: no unique `(student_id, misconception_id)`, although the README says "one row for each student and misconception".
- `diagnoses`: no unique `(submission_id, mode)`.
- `submissions`: no unique `(student_id, problem_id, attempt_number)`. See F6.
- Tags are stored twice: `problems.concept_tags` (a JSON string) and the `problem_tags` table.

### F10 — LOW — Memory-limit probe fails on newer g++
`scripts/verify_cpp_diagnostics.py:315` and `verify_cpp_reference.py`.
At `-O2`, g++ 15 removes the 512 MB `std::vector`, because the program only prints `size()`. The probe then "succeeds" in 8 ms. **The limit itself works:** a probe that actually reads the memory is killed with `MemoryLimitExceeded`. CI passes today only because Ubuntu 24.04 ships g++ 13.
**Fix:** make the probe read the buffer (for example, sum `b[i]` every 4096 bytes) or mark it `volatile`.

### F11 — LOW — `.gitattributes` does not cover `data/cpp_diagnostics/`
LF is pinned only for `data/cpp_problems/**`. On Windows (Git default `core.autocrlf=true`), the 40-problem bank is checked out with CRLF line endings. Four bank integrity tests then fail: normalization, independent model, manifest input, checksums.
**Fix:** add the same `eol=lf` rules for `data/cpp_diagnostics/**`.

### F12 — LOW — The CP01-D1 diagnostic test cannot detect the misconception
For n = 0, both `i < n` and `i <= n` print 0, so the off-by-one code passes D1. The system then records "diagnostic tests disagree" (conflict evidence), which always forces teacher review on the textbook case. Pick a D1 input that tells the two versions apart, or do not count a trivially passing case as a conflict.

### Minor or UX
- `test_python_runner_cannot_touch_server_process` is only valid inside a bwrap PID namespace. Without bwrap (any OS), it fails by design. Skip it when bwrap is not available.
- Every test case of a problem has the same name ("visible n", "hidden n"), so the teacher test table is hard to read.
- The CP01 level-1 hint should be a guiding question, but it is a statement that gives the answer away ("Your loop runs one time too many").
- Oxlint gives 5 warnings: setState in an effect (`Problem.tsx:35`, `ClassContext.tsx:45`) and fast-refresh exports. The Monaco chunk is 2.27 MB (582 KB gzip).
- The test client deprecation warning (httpx → httpx2) comes from the dependency and is harmless.

---

## 3. What passed (highlights)

**RBAC and auth (all pass):**
- Teacher signup needs the invite code. A wrong or missing code gets 403, an unknown role gets 422, a duplicate email gets 409, and a short password gets 422.
- Every protected route returns 401 to anonymous users. A forged JWT gets 401. Logout revokes the token.
- Students cannot use teacher routes: student list, classrooms, metrics, demo, review and problem creation all return 403. A teacher cannot submit code.
- Cross-user reads return **404**: student to student, teacher to a non-member student, teacher to another teacher's class. A student cannot submit as another student (403).
- A cookie session without `X-CSRF-Token` gets 403 and works with it. The session cookie is HttpOnly.
- Register and execution rate limits trigger (I hit the 20-per-hour register limit during testing).
- In the frontend, a teacher who opens a `/student/*` URL is redirected to the teacher dashboard.

**C++ pipeline (Linux):**
- Correct code passes all 9 tests. An off-by-one fails 7 of 9.
- A compile error returns `syntax_error`, and the message does not include server paths.
- An infinite loop returns `timeout`. A null dereference returns `runtime_error`.
- `#include "/etc/passwd"` is rejected. Source over 64 KB and invalid or unknown problem IDs are rejected.

**Sandbox probe from inside student code:**
- Cannot read `/home`, `/root`, `/etc/passwd`, `.env` or `tracelearn.db`.
- `SECRET_KEY` is not in the environment. `HOME=/work`.
- The network is blocked (connecting to 8.8.8.8 fails). The process is PID 2, in its own namespace.

**Data exposure:**
- Students never receive hidden or diagnostic test input or output. Teachers do.
- No ground-truth fields appear in any diagnosis response.

**Logging:**
- Source is stored verbatim, with a timestamp.
- Per-test results, evidence rows and hint events are stored.
- A teacher review is saved and the original diagnosis is unchanged.

**UI walkthrough:**
- Student: login → dashboard → practice list (46 problems, assignment flagged) → Monaco editor → Run/Submit → result page with tests, diagnosis and hint.
- Teacher: class overview → submission page with both diagnoses side by side, the evidence list, all tests and the review form.

---

## 4. Suggested priority before the Iteration 1 sign-off
1. **F2 and F3.** These make the diagnosis output wrong on almost every submission. They are small code changes, and the experiment metrics must be re-run afterwards.
2. **F1.** Needed if anyone demos or develops on Windows.
3. **F4, F5, F7.** C++ evidence is not reaching the diagnosis, and the hints do not escalate.
4. **F6, F8, F9.** Schema and taxonomy clean-up (the normalisation item).
5. **F10, F11, F12.** Test and data hygiene.
