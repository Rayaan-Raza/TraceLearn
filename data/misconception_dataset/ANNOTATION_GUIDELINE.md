# Annotation guideline — `tl-cpp-v2`

> **Status: agreed, 8 Nov 2026.** All four raters (Eman, Rayaan, Umaima, external) labelled the
> 15 calibration items alone (Fleiss κ 0.76, `reports/calibration_round_report.md`), then settled
> the three disputed items in a meeting (`review/calibration/discussion.csv`). The decision tree
> in section 4 is the result. Gold annotation can start.

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

## 4. Decision tree

**Agreed 8 Nov 2026** by Eman, Rayaan, Umaima and the external rater after the calibration
round. Work through the steps in order and stop at the first "yes". The rules marked
*(calibration)* come from items the raters disagreed on; the item ids are in
`review/calibration/discussion.csv`.

1. **Output, not logic?** Extra prompts or text, wrong format, or debug prints that alone make
   the first failing test fail → `OTHER_ERROR`.
   **Wrong I/O call arguments** *(calibration, C0449)*: a wrong argument to `scanf`/`printf`
   (missing `&`, wrong conversion specifier, a value passed where an address is needed) →
   `OTHER_ERROR`, even when Valgrind or ASan then report uninitialised values or a crash as a
   consequence.
2. **Crash or timeout that grows with input size, from recursion?** No reachable base case →
   `MISSING_BASE_CASE`.
3. **`=` inside a condition where `==` was meant**, and it changes the result → `ASSIGN_VS_COMPARE`.
4. **A variable read before any value is stored in it**, on the failing path → `UNINITIALIZED_VAR`.
   This includes a variable left unset because the program reads input that is never given,
   so the read fails *(calibration, C0451)*. (A missing `&` is still step 1: there the variable
   *is* the bad argument.)
5. **Small tests pass and large ones fail** (or there is a signed-overflow report), and a wider
   type (`long long`) would fix it → `INT_OVERFLOW`.
6. **Memory accessed outside an array?** Count how far:
   - exactly one past the end *because the loop operator is wrong* (`<=` for `<`) → `LOOP_BOUNDARY`;
   - exactly one past or one short because of index or size arithmetic (`a[i+1]`, `n` vs `n-1`,
     array declared one slot short), with the operator right → `OFF_BY_ONE`;
   - more than one past the end, or a fixed array smaller than the stated limits → `ARRAY_BOUNDS`.
7. **Output off by exactly one element or one step, no out-of-bounds access?** Changing only the
   loop operator fixes it → `LOOP_BOUNDARY`; otherwise → `OFF_BY_ONE`.
   **A wrong boundary index in a check or condition** (for example a hard-coded "last index"
   test that misses the final element) → `OFF_BY_ONE`, even when the fix is not a plain ±1
   *(calibration, C0459)*.
8. **A validation condition wrong at a range edge** (rejects a valid edge value or accepts an
   invalid one) → `RANGE_CHECK`.
9. **A loop whose exit condition reads a variable the body never updates** → `STALE_EXIT`.
10. **Loop runs in the reverse direction** where the task needs the other order → `WRONG_LOOP_DIR`.
11. A real bug that none of the above explains → `OTHER_ERROR`. You cannot tell → `UNCERTAIN`.

Still open (not reached in the calibration round; use the proposed answer until the team
decides, and note the item id when one comes up during gold annotation):
- An array exactly one slot short for the maximum input (`int v[999]` for N ≤ 1000): is that
  `OFF_BY_ONE` (proposed) or `ARRAY_BOUNDS`?
- A program whose arrays are big enough but crashes from a huge local array (stack overflow):
  `OTHER_ERROR` (proposed)?
- Debug output plus a real bug: label the output problem (step 1) or the real bug?

## 5. Practical notes

- "Presentation" means the right tokens with the wrong whitespace. Trailing spaces and
  blank lines are already ignored. A real presentation difference is `OTHER_ERROR`
  unless a class explains it.
- Sanitizer lines report *where* memory went wrong, not *why*. Use them as evidence, not as the answer.
- Write a short note whenever you choose `UNCERTAIN` or `OTHER_ERROR`. The notes feed the decision tree.
