from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

def w(rel, text):
    (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / rel).write_text(text.strip() + "\n", encoding="utf-8", newline="\n")

w("docs/POC_SCOPE.md", """
# TraceLearn POC Scope (Milestone 1)

This proof-of-concept implements the backend foundation for TraceLearn: persisted
problems and test cases, a read-only problems API, evaluation ground-truth isolation,
and documentation of learner-state and history rules used in later milestones.

## In scope (Milestone 1)

- SQLite schema for students, problems, submissions, evidence, diagnoses, learner state, and reviews
- Seed data for six canonical problems (`P01`–`P06`) with visible, hidden, and diagnostic tests
- FastAPI service with health check and `GET /api/problems` endpoints
- Ground truth accessible only through `backend/app/evaluation/labels.py`

## Out of scope (later milestones)

- Full diagnosis pipeline, hint generation, and teacher UI
- Production code execution sandbox (see subprocess warning in root `README.md`)
- Complete `HistoryProvider` implementation (design documented below)

## HistoryProvider and strict temporal causality

Learner history used for diagnosis must never leak information from the future.
When implemented, `HistoryProvider` will:

1. Accept an explicit `as_of` timestamp (typically the submission under diagnosis).
2. Return only `learner_state_history` rows with `effective_at <= as_of`, ordered by time.
3. Exclude submissions, test results, or state transitions that occur after `as_of`.

This strict temporal causality prevents evaluation leakage and mirrors how a tutor
could reason using only past interactions.
""")

w("docs/TAXONOMY.md", """
# Misconception taxonomy (POC stub)

Milestone 1 stores misconception identifiers as strings on diagnoses and learner state.
Diagnostic test cases in `data/problems/problems.json` attach optional `diagnostic_tag`
values (for example `off_by_one`, `factorial_base_case`).

Later milestones map these tags to weighted evidence in `config/evidence_weights.yaml`.
This document will expand with full definitions and teacher-facing descriptions.
""")

w("docs/LEARNER_STATE_RULES.md", """
# Learner state rules

These rules govern how misconception-level learner state transitions are applied in the POC.

## States

- **NEW** — observed on a submission but not yet promoted to persistent cross-problem knowledge.
- **PERSISTENT** — misconception recurs across different problems; primary trigger for lasting state.
- **RESOLVED** — learner demonstrated recovery (future milestone logic).

## Core rules

1. **One submission never makes a misconception PERSISTENT.** A single attempt—pass or fail—may
   create or refresh a **NEW** signal tied to that submission, but cannot alone promote to **PERSISTENT**.

2. **Same-problem repetition stays NEW.** Additional attempts on the **same** problem continue to
   surface as **NEW** unless cross-problem evidence exists. Re-drilling one exercise does not imply
   a global persistent misconception.

3. **Cross-problem recurrence is the main PERSISTENT trigger.** When the same misconception tag
   appears on submissions for **different** problem IDs (threshold configured in
   `config/evidence_weights.yaml` under `learner_state.min_cross_problem_for_persistent`), the
   learner state may transition to **PERSISTENT**.

4. **History is append-only** in `learner_state_history`. Updates must respect strict temporal
   causality (see `docs/POC_SCOPE.md`).

## Configuration reference

See `learner_state` keys in `config/evidence_weights.yaml`.
""")

w("docs/EXPERIMENT.md", """
# Experiment protocol (stub)

## Holdout evaluation

- **Demo sequences** live under `data/demo_sequences/` (development and walkthroughs).
- **Evaluation sequences** live under `data/evaluation_sequences/` (holdout; do not tune on these).

## Frozen weights

`config/evidence_weights.yaml` is **frozen before holdout evaluation**. Do not adjust weights or
thresholds after observing results on `data/evaluation_sequences/`. Document any pre-registerd
changes in version control before running holdout metrics.

## Ground truth

Labeled misconceptions for evaluation are loaded via `GroundTruthRepository` in
`backend/app/evaluation/labels.py`. Diagnosis modules must not import ground-truth files directly.
""")

w("data/demo_sequences/README.md", """
# Demo sequences

Interactive and walkthrough submission sequences for local demos and UI development.

These files are **not** holdout evaluation data. Safe to iterate while building features.
Do not use demo outcomes to tune `config/evidence_weights.yaml`.
""")

w("data/evaluation_sequences/README.md", """
# Evaluation sequences

Holdout submission sequences for offline metrics and ablations.

Treat this folder as **frozen holdout**: do not tune evidence weights or diagnosis thresholds
based on results here until weights are explicitly frozen (see `docs/EXPERIMENT.md`).
""")

w("README.md", """
# TraceLearn POC

Backend proof-of-concept for TraceLearn (Milestone 1).

## Requirements

- Python 3.14 (`C:\\Python314\\python.exe` recommended)

## Install

```bash
pip install -r requirements.txt
```

## Seed database

```bash
python scripts/seed_database.py
```

## Run API

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Health: `GET /health`  
Problems: `GET /api/problems`

## Tests

```bash
python -m pytest backend/tests/test_milestone1.py -v
```

## Code execution warning

`EXECUTION_MODE=subprocess` runs learner code in a **trusted synthetic POC environment only**.
It is **not** a secure sandbox. Never execute untrusted user code with subprocess mode in production.
Use container isolation for real deployments.

## Documentation

- `docs/POC_SCOPE.md` — scope and HistoryProvider causality note
- `docs/LEARNER_STATE_RULES.md` — NEW vs PERSISTENT rules
- `docs/EXPERIMENT.md` — frozen weights and holdout folders
""")

w("docker-compose.yml", """
# Placeholder for future containerized API + isolated code runner (not used in Milestone 1).
services:
  api:
    image: placeholder/tracelearn-api:latest
    profiles: ["future"]
    ports:
      - "8000:8000"
""")

print("docs ok")
