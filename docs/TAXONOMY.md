# Misconception taxonomy (POC stub)

Milestone 1 stores misconception identifiers as strings on diagnoses and learner state.
Diagnostic test cases in `data/problems/problems.json` attach optional `diagnostic_tag`
values (for example `off_by_one`, `factorial_base_case`).

Later milestones map these tags to weighted evidence in `config/evidence_weights.yaml`.
This document will expand with full definitions and teacher-facing descriptions.
