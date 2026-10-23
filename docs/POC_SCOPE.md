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

> **Status (October 2026):** all three items above are now implemented. The
> diagnosis pipeline lives in `backend/app/diagnosis/`, the hint policy in
> `backend/app/hints/`, the teacher UI in `frontend/src/pages/teacher/`, the
> sandbox in `backend/app/execution/sandbox.py`, and `HistoryProvider` takes an
> `as_of` timestamp in `backend/app/learner_model/history.py`. This document
> keeps the Milestone 1 record unchanged.

## HistoryProvider and strict temporal causality

Learner history used for diagnosis must never leak information from the future.
When implemented, `HistoryProvider` will:

1. Accept an explicit `as_of` timestamp (typically the submission under diagnosis).
2. Return only `learner_state_history` rows with `effective_at <= as_of`, ordered by time.
3. Exclude submissions, test results, or state transitions that occur after `as_of`.

This strict temporal causality prevents evaluation leakage and mirrors how a tutor
could reason using only past interactions.
