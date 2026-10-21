# Learner state rules

These rules control the misconception-level learner states in the POC. The code is in
`backend/app/learner_model/updater.py` (state rules) and `backend/app/learner_model/history.py`
(the data that the rules read). The thresholds are in `config/evidence_weights.yaml` under
`learner_state`, `weights` and `history`.

## States

| State | Meaning |
|-------|---------|
| `NEW` | Observed on a submission, but not yet on two different problems. |
| `PERSISTENT` | Observed on two or more different problems. |
| `IMPROVING` | Was `PERSISTENT` or `RECURRED`; a related success since the last evidence lowered the confidence. |
| `RESOLVED` | Was `IMPROVING`; sustained related success on different problems lowered the confidence below `resolved_confidence`. |
| `RECURRED` | Was `RESOLVED`; strong new evidence for the same misconception. |
| `REQUIRES_TEACHER_REVIEW` | The evidence for the misconception is weak or conflicts. |

## Definitions

- **Observed support** for misconception M: an evidence row for M with direction `support` and a
  source of `execution`, `test` or `static`. `history` and `sequence` rows restate earlier
  attempts, so they never count as observed support.
- **Problem probes M**: the problem has a diagnostic test whose tag maps to M
  (`cpp_mapping.code_for_diagnostic_tag`). Concept tags alone do not make a problem related.
- **Related success for M**: a submission that passed every test, on a problem that probes M,
  after the most recent observed support for M. A success before the student showed M is not
  evidence of recovery from M.
- **Verified success**: the history-aware diagnosis is `NO_MISCONCEPTION`, it has no review flag,
  and every test passed. A syntax error (also `NO_MISCONCEPTION`, but with a review flag) is not a
  verified success.

## Support path

The history-aware diagnosis names misconception M. The rules apply in this order:

| Condition | New state | Rule name in `reason_json` |
|-----------|-----------|----------------------------|
| The diagnosis has a review flag | `REQUIRES_TEACHER_REVIEW` | `review_flag` |
| M was `RESOLVED` and confidence ≥ `recurred_confidence` (0.45) | `RECURRED` | `strong_evidence_after_resolved` |
| M was `RESOLVED` and confidence < `recurred_confidence` | `REQUIRES_TEACHER_REVIEW` | `weak_evidence_after_resolved` |
| M was `RECURRED` | `RECURRED` | `support_while_recurred` |
| Observed support on ≥ `min_cross_problem_for_persistent` (2) problems, M was `IMPROVING` | `PERSISTENT` | `regression_after_improving` |
| Observed support on ≥ `min_cross_problem_for_persistent` (2) problems | `PERSISTENT` | `cross_problem_recurrence` |
| Otherwise | `NEW` | `isolated_or_same_problem` |

When M is `REQUIRES_TEACHER_REVIEW`, "M was" means the last stored state of M that was not a
review flag. Thus a resolved misconception that went to review can still recur.

The confidence is the confidence of the history-aware diagnosis.

## Success path

A verified success touches only the misconceptions that the current problem probes. For each
of them:

```
S      = related successes for M since its last observed support (the current attempt included)
C_new  = clip(decay_factor * C_old - |weights.related_success| * S, 0, 1)
```

With the default values `decay_factor = 0.80` and `related_success = -0.20`, a confidence of 1.0
falls to 0.60 after one success and to 0.08 after a second.

| Condition | New state | Rule name |
|-----------|-----------|-----------|
| M was `PERSISTENT` or `RECURRED` and `C_new < C_old` | `IMPROVING` | `related_success_after_persistent` |
| M was `IMPROVING`, `S ≥ min_related_successes_for_resolved` (2), the successes are on ≥ `min_distinct_problems_for_resolved` (2) problems, and `C_new < resolved_confidence` (0.25) | `RESOLVED` | `sustained_related_success` |
| M is `REQUIRES_TEACHER_REVIEW` | no change (only the confidence falls) | `success_does_not_clear_review` |
| Otherwise | no change (only the confidence falls) | `related_success_confidence_only` |

The distinct-problem condition mirrors rule 3 below: recovery, like recurrence, must show on more
than one problem. Repeating one solved problem does not resolve a misconception.

## No change

These submissions change no learner state:

- An `UNCERTAIN` diagnosis.
- A syntax error, or any diagnosis with a review flag and no named misconception.
- A failing submission without a named misconception.
- A pass on a problem that does not probe M (an **unrelated success**).

## Core rules

1. **One submission never makes a misconception PERSISTENT.** A single attempt can create or
   refresh `NEW`, but it cannot alone reach `PERSISTENT`.
2. **Same-problem repetition stays NEW.** More attempts on the same problem do not give
   cross-problem recurrence. They are `sequence` evidence.
3. **Cross-problem recurrence is the main PERSISTENT trigger.** Observed support on
   `min_cross_problem_for_persistent` different problems.
4. **Recovery needs related, sustained success.** Unrelated success and uncertainty never move a
   misconception towards `RESOLVED`.
5. **History is append-only** in `learner_state_history`. Each change records the rule, the
   counts and the submission ids in `reason_json`. A `RESOLVED` episode stays in the history when
   the misconception recurs.
6. **Strict temporal causality** (see `docs/POC_SCOPE.md`). The rules read only the current
   submission and earlier submissions. A stored state that a later submission already set is not
   overwritten when an older submission is diagnosed again.

## Evidence contract for the two diagnosis modes

The contract is in `backend/app/diagnosis/evidence_contract.py`.

| Source type | Current-only (Mode A) | History-aware (Mode B) |
|-------------|-----------------------|------------------------|
| `execution`, `test`, `static` | Yes | Yes |
| `sequence` (earlier attempt, same problem) | No | Yes |
| `history` (other problems, earlier states, earlier successes) | No | Yes |
| `context` (reserved) | No | Yes |

Mode A uses an allow-list, so a new source type does not reach it by default.

## History evidence and ageing

`backend/app/analysis/history_analyzer.py` builds the `history` evidence from earlier submissions
only.

| Code | When | Direction |
|------|------|-----------|
| `PREVIOUS_RELATED_<M>` | Observed support for M on a different earlier problem | support |
| `CROSS_PROBLEM_RECURRENCE` | Same condition. An earlier attempt on the same problem does not count. | support |
| `RELATED_SUCCESS_AFTER_MISCONCEPTION` | Related successes for M before the current attempt | conflict, for M only |
| `PREVIOUS_LEARNER_STATE` | Last stored state of M before the current submission, from `learner_state_history` | neutral |

Each record stores `details.age`, the attempt distance from the most recent earlier submission it
uses (0 = the attempt just before the current one). The age counts attempts, not seconds, because
replays submit many attempts in the same second. The weight is
`base * decay_factor ** age`. Both engines read `details_json` back with the evidence
(`records_from_items`), so the decay applies in the diagnosis and not only in the stored weight.

A related success lowers the score of M. It does not by itself put the attempt into review: a
failure after a success is a regression, not a conflict inside the current evidence.

## Configuration reference

```yaml
weights:
  related_success: -0.20                 # step per related success
history:
  decay_factor: 0.80                     # confidence decay and evidence ageing
learner_state:
  min_cross_problem_for_persistent: 2
  resolved_confidence: 0.25
  recurred_confidence: 0.45
  min_related_successes_for_resolved: 2
  min_distinct_problems_for_resolved: 2
```

The tests are in `backend/tests/test_learner_recovery.py` and `backend/tests/test_history_contract.py`.
