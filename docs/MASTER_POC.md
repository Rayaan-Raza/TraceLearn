# TraceLearn — Master POC Document

This document describes **everything in the TraceLearn proof of concept**: what each feature does, how it works in the backend, what is real logic versus configuration or seed data, and how to demonstrate the POC to a panel.

**Audience:** project supervisors, examiners, and the student presenting the proposal.

**Last updated:** aligns with the repository as built (Python backend, React/Monaco frontend, SQLite, synthetic datasets).

---

## Part 1 — Research purpose

### Central question

> Does longitudinal evidence from previous attempts and related problems add useful diagnostic information beyond analyzing only the current submission?

### What the POC demonstrates

- A **full diagnostic pipeline** from student code → execution → evidence → dual-mode diagnosis → learner state → hints → teacher review.
- **Explicit comparison** between:
  - **Mode A:** current-submission-only diagnosis
  - **Mode B:** history-aware diagnosis
- **Explainable evidence** — every diagnosis can be traced to weighted evidence items stored in the database.
- **Learner-state rules** that distinguish isolated mistakes from recurring misconceptions.

### What the POC does NOT claim

- That history-aware diagnosis is **proven better** for real students.
- That weights are empirically validated.
- That execution is secure for untrusted code.
- That this is a production-ready learning platform.

---

## Part 2 — Feature inventory (detailed)

Each subsection lists: **what it is**, **how it works**, **hardcoded vs real logic**, and **where in the codebase**.

Legend:

| Tag | Meaning |
|-----|---------|
| **REAL** | Computed at runtime from code, tests, or DB history |
| **CONFIG** | Values from `config/evidence_weights.yaml` (editable, frozen for holdout eval) |
| **SEED** | Pre-authored in JSON/Python files; ground truth for evaluation only |
| **TEMPLATE** | Fixed text strings (hints, UI labels) |
| **STORED** | Read from SQLite after prior pipeline steps |

---

### 2.1 Problem bank (6 exercises)

| Item | Detail |
|------|--------|
| **What** | Six function-based Python problems (P01–P06), two per misconception family |
| **How** | Loaded from `data/problems/problems.json` into SQLite on seed; API serves list + detail |
| **Logic** | **SEED** for problem text, starter code, test inputs/outputs; **REAL** when student submits new code |
| **Code** | `backend/app/db/seed.py`, `backend/app/api/problems.py`, `data/problems/problems.json` |

| ID | Title | Function | Target misconception |
|----|-------|----------|----------------------|
| P01 | Sum First N | `sum_first_n(n)` | M01 loop boundary |
| P02 | Count Positive | `count_positive(nums)` | M01 loop boundary |
| P03 | First Negative | `first_negative(nums)` | M02 index vs value |
| P04 | Find Max Value | `find_max_value(nums)` | M02 index vs value |
| P05 | Square Number | `square_number(x)` | M03 missing return |
| P06 | Absolute Difference | `absolute_difference(a, b)` | M03 return paths |

Each problem has **6 test cases**: 2 visible, 2 hidden, 2 diagnostic (with optional `diagnostic_tag`).

Reference solutions exist in `data/problems/solutions/P01.py` … `P06.py` for validation — not shown to students in the UI by default.

---

### 2.2 Student profiles (5 synthetic learners)

| Item | Detail |
|------|--------|
| **What** | Anonymous synthetic students SYN001–SYN005 |
| **How** | Seeded in DB with `is_synthetic=True`; demo trajectories in `data/demo_sequences/` |
| **Logic** | **SEED** for trajectory definitions; **REAL** for diagnoses/states after pipeline runs |
| **Code** | `backend/app/db/seed.py`, `data/demo_sequences/SYN*.json` |

| Student | Narrative | Attempts | Intended story |
|---------|-----------|----------|----------------|
| SYN001 | Persistent loop-boundary | 4 | NEW → PERSISTENT (cross-problem) → IMPROVING |
| SYN002 | Isolated loop error | 3 | One mistake, then correct — should NOT stay PERSISTENT |
| SYN003 | Index/value confusion | 3 | NEW → PERSISTENT → IMPROVING |
| SYN004 | Missing return | 4 | NEW → PERSISTENT → IMPROVING → RESOLVED |
| SYN005 | Ambiguous evidence | 1 | UNCERTAIN / REQUIRES_TEACHER_REVIEW |

Holdout evaluation sequences (not for rule design): **EVAL001**, **EVAL002** in `data/evaluation_sequences/`.

---

### 2.3 Code submission & Monaco editor

| Item | Detail |
|------|--------|
| **What** | Student selects learner + problem, edits Python in Monaco, clicks Run & Analyze |
| **How** | Frontend POSTs source → backend creates submission → full pipeline |
| **Logic** | **REAL** — editor content is sent to server; Monaco does not execute Python |
| **Code** | `frontend/src/screens/StudentSubmission.tsx`, `frontend/src/api/client.ts`, `backend/app/api/submissions.py` |

Flow:

1. `POST /api/submissions` — `{ student_id, problem_id, source_code }`
2. `POST /api/submissions/{id}/run-and-analyze` — execute + analyze + diagnose

---

### 2.4 Code execution (subprocess test runner)

| Item | Detail |
|------|--------|
| **What** | Runs submitted Python against all test cases for the problem |
| **How** | `exec()` in isolated worker process with timeout; calls `function_name(*args)` from test JSON |
| **Logic** | **REAL** — actual Python execution on submitted code |
| **Security** | **Not a sandbox.** Trusted synthetic/demo code only. No network/filesystem isolation claims |
| **Code** | `backend/app/execution/subprocess_runner.py`, `backend/app/execution/test_runner.py` |

Captures: `execution_status` (success, syntax_error, runtime_error, timeout, system_error), stderr, runtime_ms, per-test pass/fail and actual vs expected output.

**Not hardcoded:** pass/fail comes from comparing live function output to expected JSON.

---

### 2.5 Static analysis (AST)

| Item | Detail |
|------|--------|
| **What** | Rule-based detectors on submitted source using Python `ast` |
| **How** | Walks AST for known patterns; emits evidence records |
| **Logic** | **REAL** on submitted code; **CONFIG** for weight mapping in fusion |
| **Code** | `backend/app/analysis/static_analyzer.py` |

| Pattern | Evidence code | Misconception |
|---------|---------------|---------------|
| `range(..., n + 1)` | `STATIC_RANGE_N_PLUS_ONE` | M01 |
| Loop var used as subscript index | `STATIC_ITER_VALUE_USED_AS_INDEX` | M02 |
| No return / print instead of return | `STATIC_NO_RETURN`, `STATIC_PRINT_INSTEAD_OF_RETURN` | M03 |

**Limitation:** Only detects **explainable, simple** patterns — not full semantic understanding.

---

### 2.6 Test & runtime evidence

| Item | Detail |
|------|--------|
| **What** | Evidence from test pass/fail and execution errors |
| **How** | After test run, analyzers map failures to evidence codes (e.g. diagnostic upper-boundary fail) |
| **Logic** | **REAL** from live test results |
| **Code** | `backend/app/analysis/test_analyzer.py`, `backend/app/analysis/runtime_analyzer.py` |

Examples: `DIAGNOSTIC_UPPER_BOUNDARY_FAIL`, `RUNTIME_INDEX_ERROR`, `TEST_VISIBLE_FAIL`.

---

### 2.7 Sequence evidence (same problem, prior attempt)

| Item | Detail |
|------|--------|
| **What** | Compares current submission to previous attempt on **same problem** |
| **How** | `difflib` diff + checks if prior evidence persisted or disappeared |
| **Logic** | **REAL** from DB prior submissions (`id < current.id`) |
| **Code** | `backend/app/analysis/diff_analyzer.py` |

Used only in **history-aware** path (and stored for inspection). Current-only diagnosis **cannot** access this.

---

### 2.8 Historical evidence (cross-problem)

| Item | Detail |
|------|--------|
| **What** | Evidence from prior submissions on **related problems** (shared concept tags) |
| **How** | `HistoryProvider` queries submissions strictly **before** current submission |
| **Logic** | **REAL** from DB; **CONFIG** decay: `effective_weight = base * decay_factor^age` |
| **Code** | `backend/app/learner_model/history.py`, `backend/app/analysis/history_analyzer.py` |

Examples: `CROSS_PROBLEM_RECURRENCE`, `RELATED_SUCCESS_AFTER_MISCONCEPTION`, `PREVIOUS_RELATED_M01`.

**Temporal causality:** `HistoryProvider.get_prior_submissions` filters `Submission.id < current.id` — no future leakage (tested).

---

### 2.9 Evidence fusion & confidence

| Item | Detail |
|------|--------|
| **What** | Combines evidence into misconception hypotheses with confidence scores |
| **How** | Sum weighted support/conflict per misconception; pick primary + alternative; clamp 0–1 |
| **Logic** | **REAL** fusion; **CONFIG** weights from YAML |
| **Code** | `backend/app/diagnosis/confidence.py`, `backend/app/diagnosis/rules.py`, `config/evidence_weights.yaml` |

Weights (provisional, not empirically tuned):

| Key | Default | Role |
|-----|---------|------|
| static_strong | 0.30 | AST pattern match |
| diagnostic_match | 0.35 | Diagnostic test failure |
| cross_problem_recurrence | 0.20 | History across problems |
| related_success | -0.20 | Reduces confidence |
| conflicting_diagnostic | -0.20 | Conflicting signals |

**Not ML.** Fully inspectable arithmetic. Explanation JSON lists supporting/conflicting items.

---

### 2.10 Current-only diagnosis (Mode A)

| Item | Detail |
|------|--------|
| **What** | Diagnosis using **only** current execution, tests, static analysis |
| **How** | Separate engine; history/sequence providers are not called |
| **Logic** | **REAL**; enforced by module separation + unit tests |
| **Code** | `backend/app/diagnosis/current_only.py` |

Stored in `diagnoses` table with `mode=current_only`.

---

### 2.11 History-aware diagnosis (Mode B)

| Item | Detail |
|------|--------|
| **What** | Same fusion as Mode A **plus** sequence + historical evidence |
| **How** | Separate engine; may produce different confidence, alternative hypothesis, or state interpretation |
| **Logic** | **REAL**; not an alias of current-only |
| **Code** | `backend/app/diagnosis/history_aware.py` |

Stored with `mode=history_aware`. Learner state updates use **history-aware** diagnosis.

**Honest note:** On the current synthetic run, primary labels sometimes match between modes; confidence and learner state can still differ. Experiment reports `history_changed_predictions` — do not claim history always changes the top label.

---

### 2.12 Learner-state machine

| Item | Detail |
|------|--------|
| **What** | Per-student, per-misconception state: NEW, PERSISTENT, IMPROVING, RESOLVED, RECURRED, REQUIRES_TEACHER_REVIEW |
| **How** | Rules applied after history-aware diagnosis; transitions logged with reason JSON |
| **Logic** | **REAL** rule engine; **CONFIG** thresholds (e.g. min cross-problem for PERSISTENT) |
| **Code** | `backend/app/learner_model/updater.py`, `backend/app/learner_model/states.py`, `docs/LEARNER_STATE_RULES.md` |

Hard rules:

1. **One submission never yields PERSISTENT alone.**
2. Same-problem repetition → usually stays **NEW** (may raise confidence).
3. **Cross-problem recurrence** is the main **PERSISTENT** trigger (≥2 related problems by config).
4. Every transition writes to `learner_state_history` with reason.

**Not ML** — explicit state machine.

---

### 2.13 Hint policy

| Item | Detail |
|------|--------|
| **What** | 3-level template hints after diagnosis |
| **How** | Level from confidence + misconception; text from fixed templates |
| **Logic** | **TEMPLATE** text; **REAL** level selection from diagnosis confidence |
| **Code** | `backend/app/hints/hint_policy.py`, `backend/app/hints/templates.py` |

Low confidence / UNCERTAIN → generic hint, not misconception-specific. Does **not** output corrected code.

---

### 2.14 Teacher review

| Item | Detail |
|------|--------|
| **What** | CONFIRM, REJECT, CORRECT, MARK_UNCERTAIN on a diagnosis |
| **How** | POST stores review row; original diagnosis unchanged |
| **Logic** | **REAL** persistence; audit trail |
| **Code** | `backend/app/api/teachers.py`, `teacher_reviews` table |

---

### 2.15 Ground truth & evaluation

| Item | Detail |
|------|--------|
| **What** | Compare system predictions to seed labels; export metrics |
| **How** | Labels on submissions / `GroundTruthRepository` — **evaluation module only** |
| **Logic** | **SEED** labels; **REAL** metrics computed from stored diagnoses |
| **Code** | `backend/app/evaluation/labels.py`, `evaluator.py`, `metrics.py`, `scripts/run_synthetic_experiment.py` |

Diagnosis modules **cannot** read ground truth (tested).

Exports: `data/exports/submission_predictions.csv`, confusion matrices, `experiment_summary.json`, etc.

**Metrics are not hardcoded in the UI** — Teacher/Experiment tab reads `/api/evaluation/comparison`.

---

### 2.16 Frontend screens

| Screen | Data source | Hardcoded? |
|--------|-------------|------------|
| **Submission** | Live API run-and-analyze | No — shows real pipeline output |
| **Evidence** | `GET /api/submissions/{id}/evidence` | No — from DB evidence_items |
| **Compare** | Last run's current_only vs history_aware | No — from diagnoses table |
| **Timeline** | `GET /api/students/{id}/timeline` | No — from submissions + state history |
| **Teacher/Experiment** | Evaluation API + learner profile | No — calculated metrics |

UI styling is minimal (spartan CSS) — presentation choice, not a backend feature.

---

### 2.17 Database

SQLite file `tracelearn.db` (default). Eleven tables — see README § Database design.

All pipeline outputs (submissions, test results, evidence, diagnoses, state history) are **persisted** for inspection and experiment replay.

---

### 2.18 Automated tests

26 pytest tests covering execution, static patterns, diagnosis separation, temporal causality, learner-state rules, teacher audit, experiment exports.

**Not a demo feature** — but proves pipeline correctness for examiners who ask about validation.

---

## Part 3 — What is hardcoded vs computed (summary table)

| Component | Hardcoded / seed | Computed at runtime |
|-----------|------------------|---------------------|
| Problem descriptions & tests | JSON seed | — |
| Synthetic student trajectories | JSON + `.py` code files | — |
| Ground-truth labels | Seed (evaluation only) | — |
| Hint template text | Templates | Hint level from confidence |
| Evidence weights | YAML config | — |
| Test pass/fail | — | Subprocess execution |
| AST evidence | — | Static analyzer |
| Diagnosis & confidence | — | Evidence fusion |
| Learner state | Rules in code + YAML | From diagnosis + history counts |
| Experiment metrics | — | From DB diagnoses vs labels |
| UI diagnosis display | — | From API responses |

---

## Part 4 — Panel demonstration plan

### 4.1 Before the panel (15 minutes)

**Terminal 1 — backend**
```powershell
cd c:\Users\rayaan\Desktop\POC
python scripts\reset_demo.py
python scripts\seed_database.py
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — preload trajectories (recommended)**
```powershell
cd c:\Users\rayaan\Desktop\POC
python -c "from fastapi.testclient import TestClient; from backend.app.main import app; c=TestClient(app); print(c.post('/api/demo/run-sequence/SYN002').json()); print(c.post('/api/demo/run-sequence/SYN001').json())"
```

**Terminal 3 — frontend**
```powershell
cd c:\Users\rayaan\Desktop\POC\frontend
npm run dev
```

Open `http://127.0.0.1:5173`. Optionally run `python scripts/run_synthetic_experiment.py` beforehand so Experiment tab has metrics.

---

### 4.2 Opening (30 seconds)

Say:

> “TraceLearn tests whether **history from past attempts and related problems** improves misconception diagnosis beyond the current submission alone. This POC implements a **transparent, rule-based pipeline** with two diagnosis modes compared side by side. It is a research prototype — not a finished product.”

---

### 4.3 Demo script (~8 minutes)

#### Step 1 — Frame the problem (30 sec)

Explain: most systems only say correct/incorrect. You care about **misconception evidence**, **persistence vs isolated bugs**, and **explainability**.

Mention: 6 problems, 3 misconception families, 5 synthetic learner trajectories.

---

#### Step 2 — SYN002: isolated mistake (2 min) ⭐

1. Select **SYN002** in Submission tab (or show Timeline if preloaded).
2. **Timeline tab:** walk attempts — faulty P01, corrected P01, correct P02.
3. **Say:** “One off-by-one error is **evidence**, not a permanent label. History-aware mode should not mark this as **PERSISTENT**.”
4. **Compare tab:** pick a faulty P01 submission — show current-only vs history-aware; point at confidence and state (NEW, not PERSISTENT).

**Panel takeaway:** History helps avoid over-interpreting single failures.

---

#### Step 3 — SYN001: cross-problem persistence (2 min) ⭐

1. Select **SYN001**.
2. **Timeline tab:** P01 fault → P01 fault again → P02 fault (different problem, same family) → P02 correct.
3. **Say:** “Recurrence on **related problems** is our main trigger toward **PERSISTENT**; one submission alone never is.”
4. **Evidence tab:** open a P02 faulty submission — show static + test + **history** evidence (cross-problem recurrence).

**Panel takeaway:** Evidence is inspectable; history adds cross-problem signals.

---

#### Step 4 — Compare screen (1 min)

**Compare tab** on SYN001 faulty submission:

- Left: current-only diagnosis + confidence  
- Right: history-aware diagnosis + confidence  

Note honestly if labels match but confidence or state interpretation differs. Do **not** claim history always wins unless metrics show it.

---

#### Step 5 — Teacher & experiment (1–2 min)

1. **Teacher/Experiment tab** — show metrics JSON from API (accuracy, F1, `history_changed_predictions`, etc.).
2. Mention exports in `data/exports/` — reproducible, not hardcoded.
3. Optionally click **Confirm** / **Mark uncertain** on a diagnosis to show audit trail concept.

---

#### Step 6 — Close with limitations (30 sec)

> “This validates **pipeline feasibility** on synthetic data. Next steps: secure execution, real student sequences, human annotation, larger taxonomy.”

---

### 4.4 Five-minute compressed version

| Time | Action |
|------|--------|
| 0:00 | State research question |
| 0:30 | SYN002 Timeline — isolated mistake |
| 2:00 | SYN001 Timeline + Evidence |
| 3:30 | Compare tab |
| 4:30 | Experiment metrics |
| 5:00 | Limitations |

---

### 4.5 Likely panel questions & honest answers

| Question | Answer |
|----------|--------|
| Is this machine learning? | No — rule-based fusion; sklearn only for experiment metrics |
| Is execution secure? | No — subprocess for trusted demo code only |
| Does history always improve accuracy? | Not proven; we measure both modes and report honestly |
| Why only 3 misconceptions? | POC scope; full FYP expands later |
| Why plain UI? | Intentional — focus on diagnostic logic for proposal |
| Can you show the code path? | Yes — `submission_service.py` → pipeline → dual engines |

---

### 4.6 Backup if live demo fails

- Show preloaded Timeline for SYN001/SYN002  
- Open `data/exports/experiment_summary.json`  
- Walk through `docs/LEARNER_STATE_RULES.md`  
- Show one row in `data/exports/evidence_items.csv`  

---

### 4.7 Strong closing line

> “This POC shows we can build a pipeline where history is **separate, inspectable, and testable** — and we can **measure** when it changes diagnosis. The open question is whether that helps real learners; this prototype is the instrument to find out.”

---

## Part 5 — Quick reference commands

```powershell
# Install (once)
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Run
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
cd frontend && npm run dev

# Reset + preload demo
python scripts\reset_demo.py
python scripts\seed_database.py
python -c "from fastapi.testclient import TestClient; from backend.app.main import app; c=TestClient(app); c.post('/api/demo/run-sequence/SYN001'); c.post('/api/demo/run-sequence/SYN002')"

# Tests & experiment
python -m pytest backend/tests/ -v
python scripts/run_synthetic_experiment.py
```

---

## Part 6 — Related documents

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Install, run, full technical reference |
| [POC_SCOPE.md](POC_SCOPE.md) | Scope and temporal causality |
| [LEARNER_STATE_RULES.md](LEARNER_STATE_RULES.md) | State transition rules |
| [TAXONOMY.md](TAXONOMY.md) | Misconception definitions |
| [EXPERIMENT.md](EXPERIMENT.md) | Frozen weights and holdout policy |

---

*End of Master POC Document*
