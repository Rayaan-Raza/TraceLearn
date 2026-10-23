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
