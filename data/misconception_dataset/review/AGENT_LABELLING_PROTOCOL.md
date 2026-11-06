# Independent labelling protocol (agent annotators)

You label real, failing C/C++ student submissions with the single misconception that
explains the **first failing test**. Work alone: never open another annotator's output, the
dataset's `labels.jsonl`, any `.csv`/`.jsonl` under `annotations/`, any model, report or rule
output. Read only the shard file and `statements.md` you were given, and this protocol.

## What you see per item
Problem id, verdict, oracle test counts, the first failing test (input / expected / observed), and the code.
The oracle tests come from consensus of accepted programs, so "expected" is the correct output.

## Output
Write ONE JSON file (path given in your task) shaped exactly like

    {"PG-0001": ["CPP_OTHER_ERROR", 2, "short reason"], "PG-0002": ["CPP_ARRAY_BOUNDS", 3, "a[100] but n up to 1e5"]}

`[label, confidence 1-3, note]`. Confidence 3 = certain, 2 = likely, 1 = a guess. Every item in the shard must
have an entry. Use `UNCERTAIN` (confidence 1) when you truly cannot decide; do not force a label.

## The rule
Label the misconception that **causes the first failing test**: if you fixed only that, the first failing
test should pass. Several bugs present → the one behind the first failing test. None of the classes → `CPP_OTHER_ERROR`.

## Classes
| Label | Pick it when | Not when |
|---|---|---|
| CPP_LOOP_BOUNDARY | a loop-test comparison operator is wrong (`<=` vs `<`, `< n+1`); changing only the operator fixes it | the operator is right and an index/start is off → OFF_BY_ONE |
| CPP_OFF_BY_ONE | an index, count or start value is off by one (`a[i+1]`, start at 1, `n` vs `n-1`) with the loop operator right | the array is far too small → ARRAY_BOUNDS |
| CPP_ARRAY_BOUNDS | an access is more than one past either end, an index comes from an unbounded input value, or a fixed array is smaller than the input needs | exactly one past the end from `<=` → LOOP_BOUNDARY |
| CPP_UNINITIALIZED_VAR | a declared variable is read before it is set on some path (including a failed `scanf` leaving it unset) | it is set on every path first |
| CPP_INT_OVERFLOW | a value outgrows `int`/`long`: small tests pass, large fail; products or sums of big inputs | the formula itself is wrong |
| CPP_MISSING_BASE_CASE | a recursion has no reachable stopping case (stack overflow, crash, timeout growing with input) | the base case exists but returns the wrong value → OTHER |
| CPP_ASSIGN_VS_COMPARE | `=` written in a condition where `==` was meant | the assignment is deliberate |
| CPP_WRONG_LOOP_DIR | a loop runs backwards/forwards the wrong way for the task; output reversed | order is irrelevant |
| CPP_RANGE_CHECK | a validation/threshold condition is wrong at a range edge (`<` vs `<=` in an `if`, wrong constant, `\|\|` for `&&`, a range written as a chained comparison `a<=x<b`) and that explains the failure | a loop bound is wrong → LOOP_BOUNDARY |
| CPP_STALE_EXIT | a loop condition reads a variable the body never updates, so it exits early or never | the update exists but is wrong arithmetic |
| CPP_OTHER_ERROR | a real bug that is not one of the above: wrong formula or algorithm, wrong output text/format/spacing, printing prompts, solving a different problem, `scanf` without `&`, missing return value, wrong data structure logic, reading the wrong input format | — |

## Decision tree (apply in order)
1. Does the first failing difference come from output text, spacing, prompts, case or a different problem? → OTHER_ERROR.
2. Is a variable read before assignment (also after a failed `scanf`)? → UNINITIALIZED_VAR.
3. A crash / garbage from an index outside the array (negative, input-sized, or far past the end, or a table smaller than the input)? → ARRAY_BOUNDS.
4. A loop operator one too many/few (`<=` vs `<`) → LOOP_BOUNDARY; a start/offset/`n-1` slip with the operator right → OFF_BY_ONE.
5. Values overflow `int` on large inputs while small tests pass → INT_OVERFLOW.
6. `=` in a condition, `if (x = 1)` → ASSIGN_VS_COMPARE.
7. A loop that cannot end or ends at once because its condition variable never changes → STALE_EXIT.
8. A threshold/validation edge wrong (`<` vs `<=`, wrong cut-off, chained comparison) → RANGE_CHECK.
9. Recursion with no stopping case → MISSING_BASE_CASE; loop in the wrong direction → WRONG_LOOP_DIR.
10. Otherwise OTHER_ERROR (or UNCERTAIN if you cannot tell).

Give the most specific class that really explains the first failing test. Do not choose a misconception just because
the pattern appears somewhere in the code: it must be the cause.
