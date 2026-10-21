# Annotation guideline — `tl-cpp-v2` (DRAFT)

> **Status: draft for the calibration round.** All four raters annotate
> `annotations/forms/calibration/` together. Afterwards, write the agreed
> decision tree into section 4 and remove this notice. Gold annotation
> starts only after that (Master Plan §13.4).

## 1. What you are labeling

Each item is one **failing** C/C++ submission. It compiled, and it fails at least one
of its problem's tests. You see the problem statement, the code, up to three failing
tests (input / expected / actual), and raw compiler, sanitizer and Valgrind messages.
You do **not** see any rule output or model prediction, and you should not look them up.

## 2. The one rule that decides the primary label

**Label the misconception that explains the first failing test.** It must be the
*cause*, not just a symptom. If you fixed only that one thing, the first failing test
should pass.

- Several misconceptions present → primary = the one behind the first failing test.
  Tick the others as `also_…`.
- None of the classes explains it → `CPP_OTHER_ERROR`.
- You cannot decide → `UNCERTAIN`. Do not force a label.

## 3. Classes (cause, not symptom)

| Label | Pick it when… | Not when… |
|---|---|---|
| `CPP_LOOP_BOUNDARY` | the **loop-test comparison operator** is wrong (`<=` vs `<`, `< n+1`, `!= n+1`); changing only the operator fixes it | the operator is right and an index or start value is off → `OFF_BY_ONE` |
| `CPP_OFF_BY_ONE` | index / count / initial-value arithmetic is off by one (`a[i+1]`, start at 1, `n` vs `n-1`) and the loop operator is right | the array is far too small → `ARRAY_BOUNDS` |
| `CPP_ARRAY_BOUNDS` | the access is more than one past the end, or a fixed array is smaller than the input needs | the access is exactly one past the end because of `<=` → `LOOP_BOUNDARY` |
| `CPP_UNINITIALIZED_VAR` | a declared variable is read before it is set (often flagged by Valgrind "uninitialised") | it is set on every path before use |
| `CPP_INT_OVERFLOW` | the value outgrows `int`. Small tests pass and large ones fail, or there is a signed-overflow report | the formula itself is wrong |
| `CPP_MISSING_BASE_CASE` | a recursion has no reachable stopping case (stack overflow, crash or timeout that grows with input) | the base case exists but returns the wrong value → usually `OTHER` |
| `CPP_ASSIGN_VS_COMPARE` | `=` is written inside a condition where `==` was meant | the assignment inside the condition is deliberate and correct |
| `CPP_WRONG_LOOP_DIR` | the loop runs backwards (or reversed) and the task needs ascending order. The output is often reversed | order does not matter for the task |
| `CPP_RANGE_CHECK` | a validation condition is wrong at a range edge (rejects a valid edge value or accepts an invalid one) | a loop bound is wrong → `LOOP_BOUNDARY` |
| `CPP_STALE_EXIT` | a loop's exit condition reads a variable that the loop body never updates (premature or never-ending exit) | the update exists but is wrong arithmetic |
| `CPP_OTHER_ERROR` | it is a real bug but not one of the above (wrong formula, wrong output format, printing prompts, solving a different problem, …) | — |

## 4. Decision tree (fill in after calibration)

1. Does the program print extra prompts / text or use the wrong output format? → usually `OTHER_ERROR`.
2. …
3. …

## 5. Practical notes

- "Presentation" means the right tokens with the wrong whitespace. Trailing spaces and
  blank lines are already ignored. A real presentation difference is `OTHER_ERROR`
  unless a class explains it.
- Sanitizer lines report *where* memory went wrong, not *why*. Use them as evidence, not as the answer.
- Write a short note whenever you choose `UNCERTAIN` or `OTHER_ERROR`. The notes feed the decision tree.
