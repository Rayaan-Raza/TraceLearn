# TraceLearn POC

**Misconception-aware programming practice platform — proposal-stage proof of concept.**

TraceLearn investigates whether programming evidence accumulated across attempts and related problems can distinguish isolated coding mistakes from recurring conceptual misconceptions (and track improvement, resolution, and recurrence), rather than treating every submission independently.

This repository is a **research POC**, not a production product. The UI is intentionally spartan. The diagnostic core is **rule-based and explainable** — not machine learning and not an LLM.

---

## Table of contents

1. [What this POC tests](#1-what-this-poc-tests)
2. [What this POC does NOT prove](#2-what-this-poc-does-not-prove)
3. [Who it is for](#3-who-it-is-for)
4. [Core contribution being demonstrated](#4-core-contribution-being-demonstrated)
5. [Architecture overview](#5-architecture-overview)
6. [Technology stack](#6-technology-stack)
7. [Repository layout](#7-repository-layout)
8. [Misconception taxonomy (POC)](#8-misconception-taxonomy-poc)
9. [Problem bank](#9-problem-bank)
10. [Database design](#10-database-design)
11. [Evidence types](#11-evidence-types)
12. [Current-only vs history-aware diagnosis](#12-current-only-vs-history-aware-diagnosis)
13. [Learner-state machine](#13-learner-state-machine)
14. [Code execution (important)](#14-code-execution-important)
15. [Frontend (5 screens)](#15-frontend-5-screens)
16. [API reference](#16-api-reference)
17. [Synthetic datasets](#17-synthetic-datasets)
18. [Experiment & metrics](#18-experiment--metrics)
19. [Requirements](#19-requirements)
20. [Install](#20-install)
21. [Configure](#21-configure)
22. [Seed the database](#22-seed-the-database)
23. [Run the backend](#23-run-the-backend)
24. [Run the frontend](#24-run-the-frontend)
25. [Run tests](#25-run-tests)
26. [Run the synthetic experiment](#26-run-the-synthetic-experiment)
27. [5-minute proposal demonstration](#27-5-minute-proposal-demonstration)
28. [Teacher review](#28-teacher-review)
29. [Documentation index](#29-documentation-index)
30. [Known limitations](#30-known-limitations)
31. [Engineering rules followed](#31-engineering-rules-followed)
32. [Troubleshooting](#32-troubleshooting)

---

## 1. What this POC tests

The highest-risk assumption of the project is:

> **Does longitudinal evidence from previous attempts and related problems add useful diagnostic information beyond analyzing only the current submission?**

The POC therefore **explicitly compares**:

| Mode | Allowed inputs |
|------|----------------|
| **A. Current-submission-only** | Current execution, test results, AST patterns, current problem context |
| **B. History-aware** | Everything in A, plus prior attempts, cross-problem recurrence, related success, prior learner state, hint response |

This comparison is not hidden. The UI has a dedicated **Compare** screen, and the experiment script reports metrics for both modes against seed ground truth.

---

## 2. What this POC does NOT prove

- It does **not** prove that history-aware diagnosis is better for real students.
- It does **not** claim inventing AST parsing, databases, FastAPI, React, ML, or LLMs.
- It does **not** validate empirically tuned evidence weights (weights are provisional engineering parameters).
- The included synthetic dataset demonstrates **pipeline feasibility**. It does **not** establish that the approach improves diagnosis for real students. That requires real student attempt sequences and independent human annotation.

---

## 3. Who it is for

| Audience | Role in the POC |
|----------|-----------------|
| Beginner Python students (synthetic in POC) | Submit code, receive tests, diagnosis, and hints |
| Instructors / TAs / lab demonstrators | Review diagnoses, confirm/reject/correct, inspect experiment metrics |
| Project evaluators / supervisors | Walk the 5-minute demo and inspect evidence / comparison screens |

---

## 4. Core contribution being demonstrated

Planned pipeline implemented in the POC:

```
Student code
    ↓
Execution (trusted subprocess runner)
    ↓
Test results (visible / hidden / diagnostic)
    ↓
Static code analysis (Python `ast`)
    ↓
Attempt-sequence evidence (same problem, prior attempts)
    ↓
Historical learner evidence (related problems, prior state)
    ↓
Evidence fusion (deterministic weights from YAML)
    ↓
Misconception hypotheses + confidence (current_only AND history_aware)
    ↓
Persistent learner-state update (with transition reasons)
    ↓
Hint / remediation decision (3 template levels)
    ↓
Teacher evidence review (audit trail)
```

The interesting part is the **structured diagnostic logic** and the **longitudinal comparison**, not the surrounding frameworks.

---

## 5. Architecture overview

```
┌─────────────┐     POST /api/submissions/.../run-and-analyze      ┌──────────────────┐
│  React UI   │ ─────────────────────────────────────────────────► │  FastAPI backend │
│  (Monaco)   │ ◄───────────────────────────────────────────────── │                  │
└─────────────┘     tests, evidence, dual diagnoses, hint, state   │  SQLite DB       │
                                                                   └────────┬─────────┘
                                                                            │
                    ┌───────────────────────────────────────────────────────┘
                    ▼
         execution → analysis → diagnosis (current_only | history_aware)
              → learner_model → hints → evaluation exports
```

**Domain logic lives outside API routes.** Evidence extraction is separate from interpretation. Current-only and history-aware diagnosis are separate modules.

---

## 6. Technology stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.11+ (verified on 3.14 if that is what is installed), FastAPI, SQLAlchemy, Pydantic, pytest |
| Database | SQLite for POC simplicity (models designed so PostgreSQL can replace later) |
| Frontend | React + Vite + TypeScript, plain CSS (spartan), Monaco Editor |
| Code analysis | Python built-in `ast` |
| Code execution | **Subprocess runner for trusted synthetic/demo code only** |
| Metrics | pandas, scikit-learn (F1 / confusion matrix only — **no ML in the diagnostic core**) |

**Not used in this POC:** Docker, Pyodide, browser-side Python execution, authentication polish, payments, mobile apps, plagiarism detection, LSTM/XGBoost, unrestricted LLM debugging.

---

## 7. Repository layout

```
POC/
├── README.md                          ← this file
├── requirements.txt
├── .env.example
├── config/
│   └── evidence_weights.yaml          ← frozen weights + thresholds (do not tune after holdout)
├── backend/
│   ├── app/
│   │   ├── main.py                    ← FastAPI app, CORS, routers
│   │   ├── config.py
│   │   ├── db/                        ← models, database, seed
│   │   ├── api/                       ← problems, submissions, students, teachers, evaluation, demo
│   │   ├── schemas/
│   │   ├── execution/                 ← abstract runner + subprocess implementation + test runner
│   │   ├── analysis/                  ← static, test, runtime, diff, history, pipeline
│   │   ├── diagnosis/                 ← taxonomy, rules, confidence, current_only, history_aware
│   │   ├── learner_model/             ← states, history (temporal cutoff), updater
│   │   ├── hints/                     ← policy + templates (3 levels)
│   │   ├── evaluation/                ← labels (isolated), metrics, comparison, evaluator
│   │   └── services/                  ← submission orchestration
│   └── tests/                         ← unit + contract tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx                    ← 5-tab shell
│   │   ├── screens/                   ← Submission, Evidence, Compare, Timeline, Teacher
│   │   ├── api/client.ts
│   │   └── ...
│   └── package.json                   ← monaco-editor, @monaco-editor/react
├── data/
│   ├── problems/                      ← problems.json + reference solutions
│   ├── demo_sequences/                ← SYN* demonstration trajectories
│   ├── evaluation_sequences/          ← holdout EVAL* (not used for weight tuning)
│   ├── annotations/                   ← ground truth for evaluation only
│   └── exports/                       ← experiment CSV/JSON outputs
├── scripts/
│   ├── seed_database.py
│   ├── run_synthetic_experiment.py
│   ├── reset_demo.py
│   └── export_results.py
└── docs/
    ├── POC_SCOPE.md
    ├── TAXONOMY.md
    ├── LEARNER_STATE_RULES.md
    └── EXPERIMENT.md
```

---

## 8. Misconception taxonomy (POC)

Exactly **three** misconception categories (plus non-misconception outcomes):

| ID | Meaning | Typical evidence |
|----|---------|------------------|
| **M01_LOOP_BOUNDARY** | Off-by-one / incorrect loop boundary reasoning | `range(n+1)`, `<=` vs `<`, wrong iteration count |
| **M02_INDEX_VALUE** | Confusion between index and stored value | `for x in nums: nums[x]` |
| **M03_MISSING_RETURN** | Failure to return a computed result | no `return`, `print` instead of return, missing branch return |
| **NO_MISCONCEPTION** | No strong misconception evidence | — |
| **UNCERTAIN** | Evidence too weak or conflicting | — |

**Important:** A detected code pattern is **evidence** for a misconception. It must **not** automatically become a permanent misconception label.

---

## 9. Problem bank

Exactly **six** problems (two per misconception family) so cross-problem recurrence can be demonstrated:

| ID | Task idea | Family |
|----|-----------|--------|
| P01 | Sum / loop boundary style task | M01 |
| P02 | Related loop/count boundary task | M01 |
| P03 | First negative **value** (not index) | M02 |
| P04 | Find max **value** (not position) | M02 |
| P05 | Square / return a value | M03 |
| P06 | Absolute difference / return paths | M03 |

Each problem includes visible, hidden, and **diagnostic** tests (diagnostic tests are marked separately from ordinary correctness tests).

---

## 10. Database design

Core tables (SQLAlchemy; SQLite file typically `tracelearn.db`):

| Table | Role |
|-------|------|
| `students` | Anonymous aliases (e.g. SYN001), `is_synthetic` |
| `problems` | Slug, title, description, function name, concept/prerequisite tags |
| `test_cases` | `visible` / `hidden` / `diagnostic`, inputs/expected, optional diagnostic tag |
| `submissions` | Source code, attempt number, execution status, stdout/stderr, runtime; optional ground-truth fields for **evaluation only** |
| `test_results` | Per-test pass/fail and outputs |
| `evidence_items` | Source type, evidence code, direction, weight, details |
| `diagnoses` | Mode `current_only` or `history_aware`, hypotheses, confidence, uncertainty, explanation JSON |
| `learner_states` | Per student × misconception state + confidence + support counts |
| `learner_state_history` | Append-only transitions with `reason_json` |
| `teacher_reviews` | CONFIRM / REJECT / CORRECT / MARK_UNCERTAIN; original diagnosis preserved |
| `hint_events` | Hint level + text |

Ground-truth labels are **not** readable by diagnosis modules; evaluation code loads them separately.

---

## 11. Evidence types

| Source | Examples |
|--------|----------|
| **Execution** | SyntaxError, IndexError, timeout, unexpected None |
| **Test** | Visible/hidden/diagnostic pass/fail codes (e.g. upper-boundary fail) |
| **Static (AST)** | `range(n+1)`, value used as index, missing return / print-as-return |
| **Sequence** | Same-problem prior attempt: pattern persisted/removed, tests improved |
| **History** | Cross-problem recurrence, related success after earlier evidence, prior state |

Weights live in **one** file: [`config/evidence_weights.yaml`](config/evidence_weights.yaml). Confidence is clamped to \[0, 1\] and every score must be explainable (supporting / conflicting evidence lists).

**Freeze policy:** Do not tune weights after observing holdout (`data/evaluation_sequences/`) results.

---

## 12. Current-only vs history-aware diagnosis

| Constraint | Current-only | History-aware |
|------------|--------------|---------------|
| Prior submissions | Forbidden | Allowed only if **strictly before** submission *t* |
| Prior learner state | Forbidden | Allowed with temporal cutoff |
| Cross-problem evidence | Forbidden | Allowed |
| Future corrected attempts | Forbidden | Forbidden (`test_no_future_history_leakage`) |

Enforced by separate modules and tests — history-aware is **not** an alias of current-only.

---

## 13. Learner-state machine

States: **NEW**, **PERSISTENT**, **IMPROVING**, **RESOLVED**, **RECURRED**, **REQUIRES_TEACHER_REVIEW**.

Tightened POC rules:

1. **One submission can never yield PERSISTENT.**
2. Same-problem repetition may raise confidence but normally stays **NEW**.
3. **Cross-problem recurrence** on a related concept is the main **PERSISTENT** trigger.
4. Every transition stores a reason JSON (audit trail).
5. Successful related performance can reduce confidence / move toward IMPROVING / RESOLVED.

This is an **explicit state machine**, not an ML model. See [`docs/LEARNER_STATE_RULES.md`](docs/LEARNER_STATE_RULES.md).

---

## 14. Code execution (important)

For this POC, Python submissions execute **server-side** using a **subprocess runner**.

| Fact | Detail |
|------|--------|
| What runs | Student function loaded from submitted source; called with test-case arguments |
| Timeout | Configurable (`EXECUTION_TIMEOUT_SECONDS`, default 5) |
| Security | **Not a secure sandbox.** Does **not** claim network or filesystem isolation |
| Allowed use | Trusted synthetic / demo code only |
| Not used | Browser execution, Pyodide, Docker |

The runner is abstracted behind an `ExecutionRunner` interface so a future isolated runner could replace subprocess without rewriting diagnosis or the API. **This repository does not include Docker or container orchestration.**

Monaco Editor is **editor-only**: it does not execute Python in the browser. Flow:

1. Student edits code in Monaco.
2. **Run & Analyze** reads editor contents.
3. Frontend POSTs source to FastAPI.
4. Backend executes tests, extracts evidence, runs both diagnoses, updates learner state, returns hint.
5. UI shows results beside/below Monaco.

---

## 15. Frontend (5 screens)

Intentionally **spartan** (plain CSS, serif text, black borders, no product polish) so reviewers see a research prototype.

| Screen | Purpose |
|--------|---------|
| **Submission** | Student + problem selectors, Monaco (`language=python`, line numbers, auto-indent, bracket matching, minimap off, ~14px, ~450px height), Run & Analyze, tests + dual diagnosis + hint |
| **Evidence** | Grouped evidence (execution / test / static / sequence / history) with support/conflict and weights |
| **Compare** | Side-by-side current-only vs history-aware; highlights when history changed the result |
| **Timeline** | Learner state transitions over attempts |
| **Teacher / Experiment** | Review actions + live metrics from evaluation API |

Vite proxies `/api` to `http://127.0.0.1:8000` in development.

---

## 16. API reference

Base URL: `http://127.0.0.1:8000`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/api/problems` | List problems |
| GET | `/api/problems/{problem_id}` | Problem detail + tests |
| GET | `/api/students` | List students |
| POST | `/api/submissions` | Create submission |
| GET | `/api/submissions/{id}` | Get submission |
| POST | `/api/submissions/{id}/execute` | Run tests |
| POST | `/api/submissions/{id}/analyze` | Extract evidence |
| POST | `/api/submissions/{id}/diagnose` | Dual diagnosis + state update |
| POST | `/api/submissions/{id}/run-and-analyze` | Combined pipeline (UI primary) |
| GET | `/api/submissions/{id}/evidence` | Evidence items |
| GET | `/api/submissions/{id}/diagnoses` | Diagnoses for both modes |
| GET | `/api/submissions/{id}/test-results` | Test outcomes |
| GET | `/api/students/{id}/timeline` | Attempt timeline |
| GET | `/api/students/{id}/learner-profile` | Current learner states |
| POST | `/api/diagnoses/{id}/teacher-review` | Teacher CONFIRM/REJECT/CORRECT/MARK_UNCERTAIN |
| GET | `/api/evaluation/comparison` | Calculated current-only vs history-aware metrics |
| POST | `/api/demo/reset` | Reset demo DB state |
| POST | `/api/demo/run-sequence/{student_id}` | Replay a synthetic sequence |

Interactive docs (when server is running): `http://127.0.0.1:8000/docs`

---

## 17. Synthetic datasets

### Demo sequences (`data/demo_sequences/`)

Used for the proposal walkthrough (e.g. SYN001–SYN005 style trajectories):

- Persistent loop-boundary across related problems → NEW → PERSISTENT → IMPROVING
- Isolated single failure → must **not** become PERSISTENT
- Index/value persistence and recovery
- Missing-return resolve path
- Ambiguous / conflicting evidence → lower confidence / teacher review

### Evaluation sequences (`data/evaluation_sequences/`)

**Holdout** trajectories. Not used when designing or tuning rules/weights. Evaluate only after freezing `config/evidence_weights.yaml`.

Sequences reference **actual Python source files**. The app must execute code and extract evidence — seed data is not precomputed diagnoses.

---

## 18. Experiment & metrics

```bash
python scripts/run_synthetic_experiment.py
```

Typical pipeline:

1. Reset / seed DB  
2. Load problems and synthetic attempts  
3. Execute → evidence → current-only + history-aware diagnoses → learner states  
4. Compare predictions to seed labels  
5. Write exports under `data/exports/`

Example exports:

- `submission_predictions.csv`
- `evidence_items.csv`
- `state_transitions.csv`
- `experiment_summary.json`
- confusion matrices for each mode

Important reported quantities include:

- Misconception accuracy, macro precision / recall / F1  
- Confusion matrices  
- `history_changed_predictions` / `history_changed_correctly`  
- False persistent counts (current-only vs history-aware)  
- Persistent cases detected (both modes)  
- Learner-state accuracy where labels exist  

**Never hardcode metrics in the UI.** Do not claim history is better unless calculated results show it. Do not retune weights after seeing holdout numbers just to make history “win.”

---

## 19. Requirements

- **Python** 3.11+ preferred (3.12 ideal). If only 3.14 is installed, verify `pip install -r requirements.txt` and tests pass.
- **Node.js** 18+ (Vite frontend)
- **OS** Windows / macOS / Linux

No container runtime is required for this POC.

---

## 20. Install

From the repository root:

```bash
# Backend dependencies
python -m pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

Optional: copy environment template:

```bash
copy .env.example .env
# or: cp .env.example .env
```

---

## 21. Configure

Key settings (`.env` or defaults in `backend/app/config.py`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///./tracelearn.db` | SQLAlchemy DB URL |
| `EXECUTION_MODE` | `subprocess` | Trusted POC runner only |
| `EXECUTION_TIMEOUT_SECONDS` | `5` | Per-call timeout |
| `EVIDENCE_WEIGHTS_PATH` | `./config/evidence_weights.yaml` | Fusion weights file |

Weights / thresholds / learner-state triggers: edit **`config/evidence_weights.yaml`** only (and freeze before holdout evaluation).

---

## 22. Seed the database

```bash
python scripts/seed_database.py
```

Seeds problems, test cases, and synthetic students. Re-run after `reset_demo` or deleting the SQLite file if you need a clean start.

---

## 23. Run the backend

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

- Health: `http://127.0.0.1:8000/health`  
- OpenAPI UI: `http://127.0.0.1:8000/docs`

---

## 24. Run the frontend

```bash
cd frontend
npm run dev
```

Open the URL Vite prints (typically `http://127.0.0.1:5173`). API calls go through the Vite proxy to port 8000.

Production build check:

```bash
cd frontend
npm run build
```

---

## 25. Run tests

```bash
python -m pytest backend/tests/ -v
```

Coverage includes (among others):

- Execution success / failure / timeout  
- Static patterns for M01 / M02 / M03  
- Current-only cannot access history  
- History-aware uses related history with **no future leakage**  
- Same-problem repetition ≠ automatic PERSISTENT  
- Cross-problem recurrence can create PERSISTENT  
- Ground truth not accessible to diagnosis  
- Conflicting evidence / teacher review preserves original prediction  
- Experiment metrics generated from database  

---

## 26. Run the synthetic experiment

```bash
python scripts/run_synthetic_experiment.py
```

Also useful:

```bash
python scripts/reset_demo.py
python scripts/export_results.py
```

Inspect `data/exports/` after the experiment.

---

## 27. 5-minute proposal demonstration

1. **Reset** — `python scripts/reset_demo.py` (and seed if needed).  
2. **SYN002 (isolated mistake)** — One off-by-one, then related success. Current-only may show M01 *evidence*; history-aware should **not** confidently mark PERSISTENT. Message: *one failure is evidence, not a permanent label.*  
3. **SYN001 (persistent)** — Faulty P01 → another attempt → related P02 fault. Show cross-problem recurrence and move toward PERSISTENT.  
4. **Compare screen** — Show exactly which historical evidence changed confidence/state.  
5. **Corrected attempt** — Evidence weakens; state moves toward IMPROVING.  
6. **Teacher view** — Diagnosis, confidence, evidence, correction controls.  
7. **Experiment view** — Live calculated current-only vs history-aware metrics (not hardcoded).

---

## 28. Teacher review

Actions: **CONFIRM**, **REJECT**, **CORRECT**, **MARK_UNCERTAIN**.

- System prediction is **preserved**.  
- Teacher action, corrected label (if any), and timestamp are stored.  
- Do not silently overwrite the original diagnosis row.

---

## 29. Documentation index

| File | Contents |
|------|----------|
| [`docs/MASTER_POC.md`](docs/MASTER_POC.md) | **Master POC document** — every feature, logic vs hardcoded, panel demo plan |
| [`docs/POC_SCOPE.md`](docs/POC_SCOPE.md) | Scope, temporal causality design |
| [`docs/TAXONOMY.md`](docs/TAXONOMY.md) | Misconception definitions |
| [`docs/LEARNER_STATE_RULES.md`](docs/LEARNER_STATE_RULES.md) | NEW vs PERSISTENT and transitions |
| [`docs/EXPERIMENT.md`](docs/EXPERIMENT.md) | Frozen weights, holdout policy |

---

## 30. Known limitations

- **Subprocess execution is not suitable for untrusted student code.** It is for trusted synthetic/demo code only and is not a secure sandbox.
- Rule-based diagnosis only (no ML / LLM in the diagnostic core).
- Synthetic dataset only; metrics reflect POC feasibility, not clinical validity on real students.
- Three misconception classes and six problems — not the full planned 8–12 / 30–40 scale.
- UI is deliberately minimal (spartan), not a polished product experience.
- Evidence weights are provisional engineering parameters, not empirically validated.

---

## 31. Engineering rules followed

1. Never silently invent experimental results.  
2. Never label the learner-state machine as ML.  
3. Keep domain logic outside API routes.  
4. Separate evidence extraction from interpretation.  
5. Keep current-only and history-aware separate and testable.  
6. Every diagnosis must show why it was produced.  
7. Every learner-state transition must store a reason.  
8. A single submission must never automatically create PERSISTENT.  
9. Related success must be able to reduce misconception confidence.  
10. Weak/conflicting evidence can yield UNCERTAIN / teacher review.  
11. Preserve raw execution/test evidence.  
12. Do not overwrite system diagnoses after teacher correction.  
13. No LLM calls in the diagnostic core.  
14. Ground truth only via evaluation code.  
15. Strict temporal causality for history (no future leakage).

---

## 32. Troubleshooting

| Problem | What to try |
|---------|-------------|
| `ModuleNotFoundError: backend` | Run commands from repo root; ensure `PYTHONPATH` includes project root if needed |
| Frontend cannot reach API | Backend on `127.0.0.1:8000`; Vite proxy; CORS includes `5173` |
| Empty problem list | Run `python scripts/seed_database.py` |
| Tests hang on execution | Timeout should fire; check `EXECUTION_TIMEOUT_SECONDS`; avoid infinite loops in fixtures |
| Stale DB state | Delete `tracelearn.db` (or your SQLite path), re-seed, or `python scripts/reset_demo.py` |
| Monaco blank | Ensure `monaco-editor` and `@monaco-editor/react` installed; rebuild frontend |
| Experiment metrics look “too good” | Do not retune YAML after holdout; report what the frozen config actually produces |

---

## License / academic use

For Final Year Project proposal demonstration and supervised research use. Not intended for deployment as a production learning platform without a secure execution environment, real-student evaluation, and broader product hardening.
