# C++ Misconception Diagnostic Test Plan

Taxonomy version: `cpp-taxonomy-0.1`
Date: 10 October 2026
Author: Agent 4, C++ test author and quality judge
Standard: ASD-STE100 Simplified Technical English
Companion document: [`PROBLEM_VERIFICATION_REPORT.md`](PROBLEM_VERIFICATION_REPORT.md)

---

## 1. Purpose

This plan states how the team authors the diagnostic tests for the C++
misconceptions `CPP-M01` to `CPP-M08`. It defines the bank layout. It defines
the rules for each test type. It defines the pass and fail rules.

The plan targets the gap that `docs/MISCONCEPTION_COVERAGE_MATRIX.md` records:
the taxonomy has no diagnostic test set.

## 2. Scope

The plan covers eight problems in `data/cpp_problems`. Each problem targets one
primary misconception. The plan also covers the negative controls and the
hard-negative controls.

The plan does not cover real student submissions. It does not cover the
taxonomy definitions. Refer to `docs/TAXONOMY.md` for the definitions.

## 3. Bank layout

```
data/cpp_problems/
├── problems.json              ← problems and their test cases
├── tests/
│   ├── manifest.json          ← test index, checksums, limits
│   ├── public/<CPnn>/NN.in    ← visible input. The student can see it.
│   ├── public/<CPnn>/NN.out   ← visible expected output.
│   ├── hidden/<CPnn>/NN.in    ← hidden and diagnostic input.
│   └── hidden/<CPnn>/NN.out   ← hidden and diagnostic expected output.
├── solutions/CPnn.cpp         ← verified reference solution
├── variants/                  ← misconception variants and hard negatives
│   ├── CPnn__CPP-Mnn_a.cpp    ← a variant that holds the misconception
│   ├── CPnn__HARDNEG_*.cpp    ← correct code that looks suspicious
│   └── manifest.json          ← the expected result for each variant
└── exports/verification_report.json  ← machine-readable run output
```

Rules for the file names:

1. The folder is `public` for a visible test.
2. The folder is `hidden` for a hidden test.
3. The folder is `hidden` for a diagnostic test.
4. The file number `NN` is the global order of the test inside its problem.
5. The test id holds the kind letter. `V` is visible, `H` is hidden, `D` is
   diagnostic. For example `CP05-D2`.

## 4. Test type rules

| Type | The student can see it | Purpose |
|---|---|---|
| `visible` | Yes | Shows the contract with a typical case and a boundary case. |
| `hidden` | No | Checks the contract further. It stops a guessed solution. |
| `diagnostic` | No | Targets one misconception. A failure is evidence. |

Rules for every problem:

1. Use at least two test cases.
2. Use at least one boundary test.
3. Use at least one typical test.
4. Use at least one diagnostic test.
5. Record the sandbox limits on every test case.
6. Record a `diagnostic_tag` on every diagnostic test.

## 5. Rules for each misconception

### 5.1 `CPP-M01`: exclusive upper bound

1. The problem is `CP01`. The student sums the integers `0` to `n-1`.
2. The boundary tests use `n = 0` and `n = 1`.
3. The typical test uses `n = 5`. The expected output is `10`.
4. The exposing test uses `n = 1`. A loop with `i <= n` adds one extra term.
5. The negative control is `CP01__HARDNEG_inclusive_other_range.cpp`. It uses
   `<=` on a different range. It must pass every test.

### 5.2 `CPP-M02`: value and position

1. The problem is `CP02`. The student prints the largest value.
2. The exposing input is `{7, 3, 9}`. The value is `9`. The position is `2`.
3. One input holds duplicate values at different positions.
4. One input holds no value that equals its position.
5. The negative control is a correct search that returns the value.

### 5.3 `CPP-M03`: print and return

1. The problem is `CP03`. The function `twice` must return `x * 2`.
2. The contract uses the return value in an expression: `twice(x) + 1`.
3. The diagnostic tests use inputs where the printed text and the returned
   value differ. The variant prints `8` and returns `0`. The stdout holds `81`.
4. The verifier links the function into a separate driver. The driver reports
   the return value. Thus the judge observes both channels separately.
5. The expected value from the driver is `returned=8`.

### 5.4 `CPP-M04`: index equal to `size()`

1. The problem is `CP04`. The student prints the last element.
2. The boundary tests use an empty vector and a single-element vector.
3. The variant `CP04__CPP-M04_a.cpp` reads index `size()`. The `at()` call
   throws `std::out_of_range`. The run ends with signal 6.
4. The variant `CP04__CPP-M04_b.sanitize-only.cpp` loops with `i <= size()`.
   The plain `-O2` run is not reliable. AddressSanitizer reports the
   heap-buffer-overflow.
5. The negative control is a full traversal that stops before `size()`.

### 5.5 `CPP-M05`: chained comparison

1. The problem is `CP05`. The student prints `IN` when `1 <= x <= 10`.
2. The boundary tests use `x = 1` and `x = 10`.
3. The out-of-range tests use `x = 11`, `x = -5`, `x = 100` and `x = -1`.
4. The variant uses `1 <= x <= 10`. That expression is always true in C++.
5. The compiler emits the warning `comparisons like 'X<=Y<=Z' do not have
   their mathematical meaning [-Wparentheses]`.
6. The negative control uses `!(x < 1 || 10 < x)`. It must pass every test.

### 5.6 `CPP-M06`: assignment and equality

1. The problem is `CP06`. The student prints `ZERO` when `x` equals `0`.
2. The exposing test uses `x = 0`. A condition `if (x = 0)` always fails.
3. The variant `CP06__CPP-M06_a.cpp` emits the warning `suggest parentheses
   around assignment used as truth value [-Wparentheses]`.
4. The variant `CP06__CPP-M06_b.cpp` writes `if (0 = x)`. The compiler
   rejects the source with `lvalue required as left operand of assignment`.
5. The negative control holds an intentional assignment in a condition, with a
   comment. It must pass every test.

### 5.7 `CPP-M07`: no progress

1. The problem is `CP07`. The student computes `n!` by recursion.
2. The base-case test uses `n = 0`. The one-step test uses `n = 1`.
3. The several-steps tests use `n = 3`, `n = 5`, `n = 6` and `n = 10`.
4. The variant `CP07__CPP-M07_a.cpp` passes `n` to the recursive call again.
5. The variant `CP07__CPP-M07_b.cpp` loops without changing the loop variable.
6. Both variants run until the 2000 ms wall-clock limit stops them.

### 5.8 `CPP-M08`: exit condition is not updated

1. The problem is `CP08`. The student finds the first position of a target.
2. The immediate tests use a target at index `0`.
3. The absent tests use a target that is not in the list.
4. The variant `CP08__CPP-M08_a.cpp` is a `while` loop with no update.
5. The variant `CP08__CPP-M08_b.cpp` is a `for` loop with no update
   expression.
6. Both variants pass the immediate test. Both variants fail the absent test.

## 6. Sandbox limits

Apply these limits to every test run:

| Limit | Value | How the judge applies it |
|---|---|---|
| Wall clock | 2000 ms | `subprocess.communicate(timeout=2.0)` then kills the process group. |
| CPU | `int(2) + 1 = 3` s | `RLIMIT_CPU` via `prlimit --cpu=3`. |
| Memory | 256 MB | `RLIMIT_AS` via `prlimit --as=268435456`. |
| Output | 64 KB | `RLIMIT_FSIZE` plus a read cap. |
| Open files | 64 | `RLIMIT_NOFILE`. |
| Core dumps | 0 | `RLIMIT_CORE`. |

The compile step uses a 30 s timeout and a 2048 MB limit.

## 7. Compiler flags

Use these flags for the reference build:

```
g++ -std=c++17 -O2 -Wall -Wextra solution.cpp -o solution
```

Use these flags for the sanitizer build:

```
g++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer solution.cpp -o solution_asan
```

The backend uses `-std=c++17 -O2 -Wall`. It omits `-Wextra`. The verifier
compiles with both flag sets. `-Wall` already enables the `-Wparentheses`
warning. Thus the static evidence is stable on both flag sets.

## 8. Pass and fail rules

1. A reference solution passes a test when the process exits with code `0`,
   the run does not time out, and the stdout tokens match the expected tokens.
2. The judge compares output token by token. Spaces and line breaks do not
   change the result. Refer to `backend/app/execution/test_runner.py`.
3. A reference solution passes the bank when it passes every test case.
4. A misconception variant fails when it fails at least one test case, or when
   it times out, or when the compiler rejects it.
5. A sanitizer-only variant fails when AddressSanitizer reports a defect.
6. A hard negative passes when it passes every test case.
7. The verifier runs each test case three times. All three outputs must be
   identical.

## 9. Normalization rules

1. Use Unix `\n` line endings.
2. Remove all trailing whitespace.
3. End each file with exactly one newline.
4. Write each file as UTF-8.
5. The attribute file `.gitattributes` pins these files to LF.

## 10. Determinism rules

1. The expected output comes from a Python model. The model is separate from
   the C++ reference solution.
2. The test suite in `backend/tests/test_cpp_problem_bank.py` holds a second,
   independent model. It checks every `.out` file.
3. Two runs of `scripts/build_cpp_tests.py` produce byte-identical files.

## 11. Commands

Run the authoring script:

```
python scripts/build_cpp_tests.py
```

Run the verifier:

```
python scripts/verify_cpp_reference.py
```

Run the verifier without the sanitizer build:

```
python scripts/verify_cpp_reference.py --no-sanitize
```

Run the repo test suite:

```
python -m pytest backend/tests/ -q
```

Skip the long verifier test:

```
set TRACELEARN_SKIP_CPP_VERIFY=1
```

## 12. Known limit of the plan

The plan uses a model to produce the expected output. A bug in the model can
pass a wrong expected output to both the C++ solution and the test. The second
independent model reduces this risk. It does not remove the risk.

## 13. The 32-problem extension

The bank grew from 8 problems to 40 problems. The method for the 32 new
problems is in [`CPP_DIAGNOSTIC_BANK_METHOD.md`](CPP_DIAGNOSTIC_BANK_METHOD.md).

The extension obeys the same rules as the first 8 problems. These rules are
new:

1. Put 4 problems on each misconception. Recurrence across problems is the
   main cause of the learner state `PERSISTENT`.
2. Vary the topic inside each misconception.
3. Build the misconception variant from a documented text mutation. Do not
   write a second broken program by hand.
4. Hold 3 hints per problem. Map every hint to the misconception id.
5. Keep the reference solution names stable. The mutation depends on them.

The commands for the extended bank are:

```
python scripts/build_cpp_diagnostics.py
python scripts/verify_cpp_diagnostics.py
python scripts/seed_cpp_diagnostics.py
```

The extended bank reports 40 problems, 305 test cases, 32 variants and 120
hints. The verifier reports 581 checks. All checks pass.
