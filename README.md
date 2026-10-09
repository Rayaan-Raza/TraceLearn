# TraceLearn POC

**Misconception-aware programming practice platform — proposal-stage proof of concept.**

TraceLearn investigates whether programming evidence accumulated across attempts and related problems can distinguish isolated coding mistakes from recurring conceptual misconceptions (and track improvement, resolution, and recurrence), rather than treating every submission independently.

This repository is a **research POC**, not a production product. The diagnostic core is **rule-based and explainable** — not machine learning and not an LLM.

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
14. [Code execution and security (important)](#14-code-execution-and-security-important)
15. [Frontend](#15-frontend)
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
| Frontend | React + Vite + TypeScript + react-router, plain CSS, Monaco Editor (bundled) |
| Code analysis | Python built-in `ast` |
| Code execution | g++ / python3 inside a bubblewrap sandbox with resource limits |
| Metrics | pandas, scikit-learn (F1 / confusion matrix only — **no ML in the diagnostic core**) |

**Not used in this POC:** Pyodide, browser-side execution, payments, mobile apps, plagiarism detection, LSTM/XGBoost, unrestricted LLM debugging.

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
│   │   ├── api/                       ← auth, problems, submissions, students, classrooms, teachers, evaluation, demo
│   │   ├── auth/                      ← JWT, dependencies, object-level access rules
│   │   ├── security/                  ← rate limiting, headers, body size limit
│   │   ├── schemas/
│   │   ├── execution/                 ← sandbox (bubblewrap), C++/Python runners, test runner
│   │   ├── analysis/                  ← static, test, runtime, diff, history, pipeline
│   │   ├── diagnosis/                 ← taxonomy, rules, confidence, current_only, history_aware
│   │   ├── learner_model/             ← states, history (temporal cutoff), updater
│   │   ├── hints/                     ← policy + templates (3 levels)
│   │   ├── evaluation/                ← labels (isolated), metrics, comparison, evaluator
│   │   └── services/                  ← submission orchestration
│   └── tests/                         ← unit + contract tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx                    ← role-based routes
│   │   ├── pages/student, pages/teacher
│   │   ├── api/client.ts              ← cookie + CSRF client
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
│   ├── create_teacher.py
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

## 14. Code execution and security (important)

Submissions execute **server-side**, and every submission is treated as untrusted code.

| Layer | What it does |
|-------|--------------|
| **bubblewrap sandbox** | Compile and run happen in new mount/PID/network/IPC namespaces. The program sees a read-only `/usr`, an empty `/tmp` and its own scratch dir — **no network, no project files, no database, no `.env`, empty environment**. |
| **Resource limits** | CPU seconds, address space (256 MB, 2 GB for the compiler), output size, open files, no core dumps; wall-clock timeout kills the whole process group. |
| **Concurrency cap** | At most `MAX_CONCURRENT_EXECUTIONS` submissions run at once; per-user execution rate limit. |
| **Source screening** | C++ may only `#include <standard headers>` (blocks `#include "/proc/self/environ"`-style file reads through compiler errors). |
| **Analysis isolation** | The C++ regex detectors run in a separate process with a 3 s budget (some patterns backtrack catastrophically on crafted input). |

Python submissions run in a fresh `python3 -I` process inside the sandbox — never inside the API server process. C++ output is compared token-by-token (spaces vs. newlines do not matter).

**Install bubblewrap on the server:** `sudo apt install bubblewrap`. In production (`APP_ENV=production`) execution is **refused** if bubblewrap is unavailable. On Windows/macOS development machines it falls back to resource limits only and logs a warning — that mode is not safe for untrusted users. If you run in Docker, the container needs to allow unprivileged namespaces (e.g. `--security-opt seccomp=unconfined` or a tailored profile); also set `--pids-limit` to bound process counts.

### Security model (API)

* **Every endpoint requires sign-in** (except `/health`, register and login).
* **Students** see only their own submissions, diagnoses, evidence, hints and learner state. They submit as themselves — the student id comes from the session, never the request.
* **Teachers** see only students in classrooms they own (plus synthetic `SYN*` research students). Teacher self-registration needs `TEACHER_SIGNUP_CODE`; otherwise create teachers with `python scripts/create_teacher.py`.
* Data the caller may not see returns **404**, so ids cannot be probed.
* Students never receive inputs or expected outputs of **hidden/diagnostic tests**. Ground-truth labels are never returned by any endpoint.
* Browser sessions use an **httpOnly** cookie plus a **double-submit CSRF token**; API clients can use `Authorization: Bearer`. Logout revokes every token issued to that user. JWTs pin HS256 and check issuer/audience/expiry.
* Rate limits on login, registration, class joining and code execution; 256 KB request body cap; 64 KB source cap.
* Security headers on every response (CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, HSTS when secure). Swagger is off in production.
* `/api/demo/*` is disabled unless `ENABLE_DEMO_ENDPOINTS=true`, teacher-only, and only touches synthetic data (it no longer drops tables).
* The server **refuses to start** in production with a default/short `SECRET_KEY`, wildcard CORS, or demo endpoints enabled.

`backend/tests/test_security.py` covers all of the above (auth on every route, token forgery, CSRF, IDOR between students/teachers/classrooms, hidden-test leakage, input limits, sandbox file/network/env isolation).

---

## 15. Frontend

React + Vite + TypeScript, react-router, Monaco (bundled locally — no CDN). Fonts are self-hosted.

**Student**

| Screen | Purpose |
|--------|---------|
| Dashboard | Focus area (worst learner state), progress counts, concept-state and mistake-timeline charts, assignments, recommended problems |
| Practice | All problems visible to the student + class assignments, with status |
| Problem | Monaco editor (C++ or Python per problem), visible test cases, **Run / Submit** |
| Result | Tests passed, expected vs. your output (visible tests only), diagnosis summary, progressive hints |
| Classroom | Join a class with a code; current and previous assignments with your attempts |
| Submissions / Progress | Attempt history; per-concept learning story from real learner-state transitions |

**Teacher**

| Screen | Purpose |
|--------|---------|
| Class Overview | Class stats and misconception chart; create classrooms |
| Classroom | Join code (copy/rotate), roster, assignments, recent submissions |
| Assign Problem | Pick from the problem bank or author a C++ problem with visible/hidden tests |
| Assigned Problems | Per-assignment results and misconception chart; close/reopen |
| Misconceptions / Students | Who has which concept tracked and in what state |
| Submission | Code, all tests incl. hidden, **current-only vs history-aware** comparison, grouped evidence, teacher review (CONFIRM/REJECT/CORRECT/MARK_UNCERTAIN) |
| Research | Live experiment metrics (current-only vs history-aware), synthetic demo replay, sandbox status |

The UI routes by the role the server reports; every API call is still authorized server-side.

---

## 16. API reference

Base URL: `http://127.0.0.1:8000`. All `/api` routes require authentication unless noted. Interactive docs at `/docs` in development.

| Method | Path | Who |
|--------|------|-----|
| GET | `/health` | public |
| POST | `/api/auth/register` · `/api/auth/login` | public (rate limited) |
| POST | `/api/auth/logout` · GET `/api/auth/me` | signed in |
| GET | `/api/problems` · `/api/problems/{id}` | signed in (custom problems: owner / assigned students) |
| POST | `/api/problems` | teacher (C++ stdin/stdout problem) |
| POST | `/api/submissions` | student (as themselves) |
| POST | `/api/submissions/{id}/run-and-analyze` (also `/execute`, `/analyze`, `/diagnose`, `/next-hint`) | owning student |
| GET | `/api/submissions/{id}` and `/evidence`, `/diagnoses`, `/test-results`, `/hints`, `/reviews` | owning student or their teacher |
| GET | `/api/students` | teacher (own class members + synthetic) |
| GET | `/api/students/{id}/submissions` · `/timeline` · `/learner-profile` | that student or their teacher |
| POST | `/api/diagnoses/{id}/teacher-review` | that student's teacher |
| GET/POST | `/api/classrooms` | teacher creates; both list their own |
| POST | `/api/classrooms/join` | student (join code) |
| GET | `/api/classrooms/{id}` | owner or member |
| GET | `/api/classrooms/{id}/overview` · `/members` · POST `/rotate-code` · DELETE `/members/{sid}` | owner |
| GET/POST | `/api/classrooms/{id}/assignments` | owner creates; members see their own |
| GET | `/api/assignments/mine` · `/api/assignments/{id}` · PATCH `/api/assignments/{id}` | owner / assigned student (PATCH: owner) |
| GET | `/api/evaluation/comparison` | teacher |
| GET | `/api/demo/status` · POST `/api/demo/reset` · `/api/demo/run-sequence/{SYNnnn}` | teacher, only if `ENABLE_DEMO_ENDPOINTS=true` |

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

- **Python** 3.11+ (verified on 3.13)
- **Node.js** 18+ (Vite frontend)
- **g++** with C++17 support
- **bubblewrap** (`apt install bubblewrap`) — required in production for sandboxed execution
- **OS** Linux for production; Windows/macOS work for development (without the OS sandbox)

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

Copy `.env.example` to `.env`. Every option is documented there. The important ones:

| Variable | Default | Meaning |
|----------|---------|---------|
| `APP_ENV` | `development` | `production` enforces secure settings at startup |
| `SECRET_KEY` | — | **Required in production**; random, ≥ 32 chars |
| `TEACHER_SIGNUP_CODE` | empty | Invite code for teacher self-signup (empty = disabled) |
| `SERVE_FRONTEND` | `false` | Serve `frontend/dist` from the backend (same origin) |
| `ENABLE_DEMO_ENDPOINTS` | `false` | Research demo API (never in production) |
| `SANDBOX_MODE` / `REQUIRE_SANDBOX` | `auto` / prod: on | Code execution isolation policy |
| `DATABASE_URL` | `sqlite:///./tracelearn.db` | SQLAlchemy DB URL |
| `EVIDENCE_WEIGHTS_PATH` | `./config/evidence_weights.yaml` | Fusion weights file |

Weights / thresholds / learner-state triggers: edit **`config/evidence_weights.yaml`** only (and freeze before holdout evaluation).

Create a teacher account (prompts for a password):

```bash
python scripts/create_teacher.py teacher@school.edu "Dr. Sarah Ahmed"
```

Students register themselves and join a class with the join code shown on the teacher's Classroom page.

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
- OpenAPI UI (development only): `http://127.0.0.1:8000/docs`

**Production (single origin, recommended):**

```bash
cd frontend && npm ci && npm run build && cd ..
APP_ENV=production SECRET_KEY=... SERVE_FRONTEND=true \
  uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1
```

Put it behind an HTTPS reverse proxy (nginx/Caddy). Serving the UI and API from one origin keeps the session cookie first-party. If you host the frontend separately (e.g. Vercel), set `VITE_API_BASE_URL`, add that origin to `CORS_ORIGINS`, and use sibling subdomains with `COOKIE_DOMAIN` so the CSRF cookie is readable.

---

## 24. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to port 8000, so the browser sees one origin. Production build: `npm run build`.

---

## 25. Run tests

```bash
python -m pytest backend/tests/ -v
```

Coverage includes (among others):

- Execution success / failure / timeout, sandbox isolation (files, network, environment)
- Static patterns for M01 / M02 / M03
- Current-only cannot access history; history-aware uses related history with **no future leakage**
- Same-problem repetition ≠ automatic PERSISTENT; cross-problem recurrence can create PERSISTENT
- Ground truth not accessible to diagnosis or any endpoint
- Teacher review preserves original prediction
- **Security suite** (`test_security.py`): auth on every endpoint, IDOR, CSRF, token forgery/revocation, hidden-test leakage, rate limits, input limits

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

- **Execution isolation depends on bubblewrap.** Without it (Windows/macOS dev) code runs with resource limits only — never expose such a server to untrusted users. Production refuses to execute without it.
- Rate limits are in-memory and per process; with several workers/replicas add limiting at the reverse proxy too.
- C++ diagnosis is early-stage: the CPP_* evidence codes have no weights in `config/evidence_weights.yaml` and the learner-state updater only tracks M01–M03, so C++ attempts mostly show as "uncertain / no pattern yet" until those are added.
- Rule-based diagnosis only (no ML / LLM in the diagnostic core).
- Synthetic dataset only; metrics reflect POC feasibility, not clinical validity on real students.
- Three Python misconception classes and six dataset problems — not the full planned scale.
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
| Server refuses to start in production | Read the listed problems: usually `SECRET_KEY` missing/short or demo endpoints enabled |
| "Code execution requires bubblewrap" | `sudo apt install bubblewrap`; in Docker allow unprivileged user namespaces |
| Frontend shows the sign-in page after every reload | Cookies blocked: use the Vite proxy in dev, or same-origin `SERVE_FRONTEND` in production; `COOKIE_SECURE=true` needs HTTPS |
| "CSRF token missing or invalid" | Request was sent with the session cookie but without `X-CSRF-Token`; use the frontend client or a Bearer token |
| 429 Too many requests | Rate limit hit; wait a minute |
| Empty problem list | Run `python scripts/seed_database.py` |
| Stale DB state | Delete `tracelearn.db`, re-seed, or `python scripts/reset_demo.py` (synthetic data only) |
| Experiment metrics look “too good” | Do not retune YAML after holdout; report what the frozen config actually produces |

---

## License / academic use

For Final Year Project proposal demonstration and supervised research use. Not intended for deployment as a production learning platform without a secure execution environment, real-student evaluation, and broader product hardening.
