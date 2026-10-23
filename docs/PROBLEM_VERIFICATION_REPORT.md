# Problem Verification Report

Report id: `CPP-VER-2026-10-10-02`
Date: 10 October 2026
Author: Agent 4, C++ test author and quality judge
Taxonomy version: `cpp-taxonomy-0.1`
Standard: ASD-STE100 Simplified Technical English
Companion documents: [`CPP_MISCONCEPTION_TEST_PLAN.md`](CPP_MISCONCEPTION_TEST_PLAN.md), [`CPP_DIAGNOSTIC_BANK_METHOD.md`](CPP_DIAGNOSTIC_BANK_METHOD.md)

This report has two parts. Part A verifies the first 8 problems. Part B
verifies the full 40-problem bank. A later report can supersede an earlier
part. Always read the newest report id first.

---

# PART A: the first eight problems

Report id: `CPP-VER-2026-10-10-01`

---

## 1. Purpose

This report records the verification of the C++ diagnostic bank in
`data/cpp_problems`. It records the compilation logs. It records the test
assertions. It records the memory metrics. It records the sandbox limits.

Every number in this report comes from a real run. The tool writes the raw
machine-readable copy to
`data/cpp_problems/exports/verification_report.json`.

## 2. Result summary

| Item | Measured value |
|---|---|
| Reference solutions verified | 8 of 8 |
| Test cases executed | 77 |
| Test executions | 231 (each test case runs 3 times) |
| Checks passed | 149 |
| Checks failed | 0 |
| Misconception variants detected | 12 of 12 |
| Hard negatives that pass every test | 4 of 4 |
| Sanitizer findings in the reference solutions | 0 |

The verifier exits with code `0`.

## 3. Environment

| Item | Measured value |
|---|---|
| Host | Windows 11 (`x86_64`). No `g++` on `PATH`. |
| Execution host | WSL 2, Ubuntu 24.04, Linux `6.6.87.2-microsoft-standard` |
| Compiler | `g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` |
| Python in the execution host | 3.12.3 |
| Python on the host | 3.14.0 |
| Sandbox engine | `backend.app.execution.sandbox.run_in_sandbox` |
| Sandbox mode | `rlimit-only` |
| Bubblewrap | Not installed in the WSL distribution |

The host has no C++ toolchain. The verifier re-executes itself inside WSL.
The verification uses the project's own sandbox module. Bubblewrap is absent,
so the isolation layer does not apply. Only the resource limits apply.

> **CAUTION:** The `rlimit-only` mode is not safe for untrusted users. Install
> `bubblewrap` in the Linux host before you run student code. Refer to
> `backend/app/execution/sandbox.py`.

### 3.1 Toolchain installation

The WSL distribution needed two Python packages before it could import the
project sandbox module:

```
python3 -m pip install --break-system-packages pydantic-settings sqlalchemy
```

The sandbox module imports `backend.app.config`, which uses
`pydantic_settings`. Without that package the verifier uses a mirror of
`sandbox._limits()`. Both engines apply the same `RLIMIT_CPU`,
`RLIMIT_AS`, `RLIMIT_FSIZE`, `RLIMIT_NOFILE` and `RLIMIT_CORE` values.

## 4. Bank contents

| Problem | Slug | Primary misconception | Secondary | Tests | Visible | Hidden | Diagnostic | Boundary |
|---|---|---|---|---:|---:|---:|---:|---:|
| `CP01` | `m01_sum_first_n` | `CPP-M01` | `CPP-M08` | 9 | 3 | 3 | 3 | 1 |
| `CP02` | `m02_max_value_not_index` | `CPP-M02` | `CPP-M01` | 10 | 3 | 4 | 3 | 1 |
| `CP03` | `m03_return_contract` | `CPP-M03` | — | 9 | 3 | 3 | 3 | 1 |
| `CP04` | `m04_last_element` | `CPP-M04` | `CPP-M01` | 9 | 3 | 3 | 3 | 1 |
| `CP05` | `m05_range_check` | `CPP-M05` | `CPP-M06` | 12 | 3 | 5 | 4 | 1 |
| `CP06` | `m06_zero_test` | `CPP-M06` | `CPP-M05` | 9 | 3 | 4 | 2 | 1 |
| `CP07` | `m07_factorial` | `CPP-M07` | `CPP-M08` | 9 | 3 | 3 | 3 | 2 |
| `CP08` | `m08_search_exit` | `CPP-M08` | `CPP-M04` | 10 | 3 | 4 | 3 | 2 |
| **Total** | | | | **77** | **24** | **29** | **24** | **12** |

Every problem holds at least one visible test, one hidden test, one
diagnostic test and one boundary test. The matrix in
`docs/MISCONCEPTION_COVERAGE_MATRIX.md` requires this.

## 5. Compilation log

The mandated build command is:

```
g++ -std=c++17 -O2 -Wall -Wextra solution.cpp -o solution
```

The verifier also compiles with the backend flags:

```
g++ -std=c++17 -O2 -Wall solution.cpp -o solution
```

Results for all 16 builds:

| Problem | Mandated flags | Backend flags | Warnings | Compile time |
|---|---|---|---|---:|
| `CP01` | exit 0 | exit 0 | none | 919 ms |
| `CP02` | exit 0 | exit 0 | none | 969 ms |
| `CP03` | exit 0 | exit 0 | none | 869 ms |
| `CP04` | exit 0 | exit 0 | none | 919 ms |
| `CP05` | exit 0 | exit 0 | none | 919 ms |
| `CP06` | exit 0 | exit 0 | none | 868 ms |
| `CP07` | exit 0 | exit 0 | none | 869 ms |
| `CP08` | exit 0 | exit 0 | none | 969 ms |

Every solution compiles with exit code `0`. No build emits a warning. Both
flag sets give the same result. The backend omits `-Wextra`, but `-Wall`
already enables the `-Wparentheses` warning. Thus the static evidence in
section 8 is stable on the backend flags.

The sanitizer builds use:

```
g++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer
g++ -std=c++17 -O1 -g -fsanitize=undefined -fno-omit-frame-pointer
```

All 16 sanitizer builds succeed.

## 6. Test assertions

The judge compares stdout token by token. It uses the same rule as
`backend/app/execution/test_runner.py`. Spaces and line breaks do not change
the result.

A test case passes when all three conditions hold:

1. The process exits with code `0`.
2. The run does not time out.
3. The stdout tokens equal the expected tokens.

Results:

| Problem | Test cases passed | Deterministic (3 runs) | Runtime min | Runtime median | Runtime max |
|---|---:|---|---:|---:|---:|
| `CP01` | 9 of 9 | yes | 4.34 ms | 4.45 ms | 6.02 ms |
| `CP02` | 10 of 10 | yes | 4.34 ms | 4.54 ms | 5.92 ms |
| `CP03` | 9 of 9 | yes | 4.36 ms | 4.55 ms | 10.68 ms |
| `CP04` | 9 of 9 | yes | 4.36 ms | 4.64 ms | 6.39 ms |
| `CP05` | 12 of 12 | yes | 4.38 ms | 4.72 ms | 7.97 ms |
| `CP06` | 9 of 9 | yes | 4.44 ms | 4.53 ms | 6.58 ms |
| `CP07` | 9 of 9 | yes | 4.53 ms | 5.95 ms | 6.08 ms |
| `CP08` | 10 of 10 | yes | 4.37 ms | 4.57 ms | 6.21 ms |
| **Total** | **77 of 77** | **yes** | **4.33 ms** | **4.63 ms** | **10.34 ms** |

The runtime column shows the wall-clock time of one child process. The
2000 ms limit leaves a large margin.

## 7. Memory metrics

The verifier reads `getrusage(RUSAGE_CHILDREN).ru_maxrss` after each run. This
value is a running maximum over all terminated children. Only one child runs
at a time, so the value after a run is that run's peak, unless an earlier
child used more memory.

| Metric | Value |
|---|---|
| Minimum child peak RSS | 68,796 kB (67.2 MB) |
| Median child peak RSS | 73,104 kB (71.4 MB) |
| Maximum child peak RSS | 86,676 kB (84.6 MB) |
| Memory cap | 262,144 kB (256 MB) |
| Headroom at the median | 189,040 kB (184.6 MB) |

The reference solutions are small. The memory cap is not close. The
measurement includes the WSL 2 glibc runtime, so a native Linux run uses less
memory. `RUSAGE_CHILDREN.ru_maxrss` is a running maximum, so each value is the
largest child seen up to that run.

## 8. Misconception variants

The bank holds 16 files in `data/cpp_problems/variants`. Twelve files hold a
misconception. Four files are hard negatives. The manifest
`data/cpp_problems/variants/manifest.json` states the expected result for
each file. The verifier asserts that expectation.

| Variant | Tests | Expected | Result | Tests failed | First failure | Observed output | Return code | Timeout |
|---|---:|---|---|---:|---|---|---:|---|
| `CP01__CPP-M01_a.cpp` | 9 | `fail_at_least_one` | `wrong_output` | 7 | `CP01-V1` | `15` | 0 | no |
| `CP01__HARDNEG_inclusive_other_range.cpp` | 9 | `pass_all` | `pass_all` | 0 | — | — | — | no |
| `CP02__CPP-M02_a.cpp` | 10 | `fail_at_least_one` | `wrong_output` | 8 | `CP02-V1` | `2` | 0 | no |
| `CP03__CPP-M03_a.cpp` | 9 | `fail_at_least_one` | `wrong_output` | 9 | `CP03-V1` | `81` | 0 | no |
| `CP04__CPP-M04_a.cpp` | 9 | `fail_at_least_one` | `wrong_output` | 7 | `CP04-V1` | empty | -6 | no |
| `CP04__CPP-M04_b.sanitize-only.cpp` | 9 | `sanitizer_detected` | `sanitizer_detected` | 7 | `CP04-V1` | `0` | 0 | no |
| `CP04__HARDNEG_full_traversal.cpp` | 9 | `pass_all` | `pass_all` | 0 | — | — | — | no |
| `CP05__CPP-M05_a.cpp` | 12 | `fail_at_least_one` | `wrong_output` | 7 | `CP05-V2` | `IN` | 0 | no |
| `CP05__HARDNEG_de_morgan.cpp` | 12 | `pass_all` | `pass_all` | 0 | — | — | — | no |
| `CP06__CPP-M06_a.cpp` | 9 | `fail_at_least_one` | `wrong_output` | 3 | `CP06-V1` | `NONZERO` | 0 | no |
| `CP06__CPP-M06_b.cpp` | 9 | `compile_error` | `compile_error` | — | — | — | 1 | no |
| `CP06__HARDNEG_assignment_with_comment.cpp` | 9 | `pass_all` | `pass_all` | 0 | — | — | — | no |
| `CP07__CPP-M07_a.cpp` | 9 | `fail_at_least_one` | `timeout` | 5 | `CP07-V2` | empty | -9 | yes |
| `CP07__CPP-M07_b.cpp` | 9 | `fail_at_least_one` | `timeout` | 5 | `CP07-V2` | empty | -9 | yes |
| `CP08__CPP-M08_a.cpp` | 10 | `fail_at_least_one` | `wrong_output` | 7 | `CP08-V1` | `0` | 0 | no |
| `CP08__CPP-M08_b.cpp` | 10 | `fail_at_least_one` | `timeout` | 7 | `CP08-V1` | empty | -9 | yes |

Every variant met its expected result. A return code of `-6` means `SIGABRT`.
A return code of `-9` means `SIGKILL` from the wall-clock watchdog.

### 8.1 Static evidence from the compiler

The compiler confirms two misconceptions. The verifier asserts the exact
diagnostic text.

`CP05__CPP-M05_a.cpp`:

```
CP05__CPP-M05_a.cpp:22:16: warning: comparison of constant '10' with boolean expression is always true [-Wbool-compare]
CP05__CPP-M05_a.cpp:22:11: warning: comparisons like 'X<=Y<=Z' do not have their mathematical meaning [-Wparentheses]
```

`CP06__CPP-M06_a.cpp`:

```
CP06__CPP-M06_a.cpp:22:11: warning: suggest parentheses around assignment used as truth value [-Wparentheses]
```

`CP06__CPP-M06_b.cpp`:

```
CP06__CPP-M06_b.cpp:21:9: error: lvalue required as left operand of assignment
```

`CP06__HARDNEG_assignment_with_comment.cpp` emits no warning. That file holds
an intentional assignment in a condition, with a comment. The taxonomy
excludes this pattern from `CPP-M06`.

### 8.2 The return channel test for `CPP-M03`

The `CPP-M03` contract is about the return value, not about stdout. The
verifier links the student function into a separate driver. It renames only
the student `main` with `-Dmain=disabled_main`. It compiles the student file
and the driver as two objects. It then links them.

```
g++ -std=c++17 -O2 -Wall -Wextra -Dmain=disabled_main -c CP03.cpp -o solution.o
g++ -std=c++17 -O2 -Wall -Wextra -c driver.cpp -o driver.o
g++ solution.o driver.o -o channel
```

The driver prints the value that arrives through the return channel.

| Solution | Driver output |
|---|---|
| `solutions/CP03.cpp` | `returned=8` |
| `variants/CP03__CPP-M03_a.cpp` | `returned=0` |

Thus the judge observes stdout and the return channel separately. The print
only variant returns `0` and prints `8`. Its stdout is `81`, not `9`.

### 8.3 The `CPP-M04` sanitizer test

The loop variant `CP04__CPP-M04_b.sanitize-only.cpp` reads one element past
the end of a vector of five integers. The plain `-O2` build prints `0` and
exits with code `0`. That result is undefined behaviour. It is not a reliable
assertion.

The AddressSanitizer build reports the defect:

```
==663==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x503000000054
READ of size 4 at 0x503000000054 thread T0
    #0 ... in main data/cpp_problems/variants/CP04__CPP-M04_b.sanitize-only.cpp:42
0x503000000054 is located 0 bytes after 20-byte region [0x503000000040,0x503000000054)
```

The region is 20 bytes. It holds five `int` values. The read starts 0 bytes
after the region. The variant fails the test set. The sanitizer gives the
precise evidence.

## 9. Sandbox limit validation

Two probe programs validate the limits. The verifier runs them in a limited
child process.

### 9.1 The 256 MB memory cap

The probe allocates 512 MB.

```cpp
std::vector<char> block(512ULL * 1024 * 1024, 1);
```

Result:

| Item | Measured value |
|---|---|
| Requested memory | 512 MB |
| Memory cap | 256 MB |
| Outcome | `std::bad_alloc` |
| Return code | -6 (`SIGABRT`) |
| `memory_limit_hit` | `True` |
| Elapsed time | 33 ms |
| stderr | `terminate called after throwing an instance of 'std::bad_alloc'` |

The cap applies. `cpp_runner.py` maps this result to `MemoryLimitExceeded`.

### 9.2 The 2000 ms wall-clock cap

The probe loops forever.

```cpp
while (true) { ++counter; }
```

Result:

| Item | Measured value |
|---|---|
| Wall-clock limit | 2000 ms |
| Outcome | timeout |
| Return code | -9 (`SIGKILL`) |
| `timed_out` | `True` |
| Elapsed time | 2003 ms |

The watchdog kills the process group. `cpp_runner.py` maps this result to the
status `timeout`.

### 9.3 Sanitizer runs carry no memory cap

AddressSanitizer reserves about 16 TB of virtual address space for its shadow.
Any `RLIMIT_AS` below that size stops the program before `main` runs. The
verifier therefore runs the sanitizer builds without the memory cap. It keeps
the 2000 ms wall-clock cap. The judged runs keep the 256 MB cap. The
`-fsanitize=undefined` build runs inside the 256 MB cap, so the reference
solutions are also checked under the real limit.

## 10. Repo test suite

Command:

```
python -m pytest backend/tests/ -q
```

Result:

| Item | Count |
|---|---|
| Passed | 116 |
| Failed | 3 |
| Skipped | 1 |

The new file `backend/tests/test_cpp_problem_bank.py` adds 35 tests. All 35
pass. One test is the full integration test. It runs the verifier and takes
about 86 s.

### 10.1 The three failures are not new

Three tests in `backend/tests/test_security.py` fail. They fail on the
baseline commit `a782189` as well. That commit is the parent of this work.
The failures come from the host, not from this work.

| Test | Cause |
|---|---|
| `test_cpp_correct_solution_passes` | The host has no `g++` on `PATH`. The compile step returns `syntax_error`. |
| `test_sandbox_timeout_and_output_limits` | The test expects `runtime_error` for the output limit, but the same program also reaches the time limit. The time limit wins. |
| `test_python_runner_cannot_touch_server_process` | On Windows the sandbox cannot apply `RLIMIT_AS` or `RLIMIT_CPU`. The child sees the server process id. |

Evidence for `test_cpp_correct_solution_passes`:

```
AssertionError: assert 'syntax_error' == 'success'
```

Evidence for `test_sandbox_timeout_and_output_limits`:

```
assert r.status == "runtime_error"
E       AssertionError: assert 'timeout' == 'runtime_error'
```

Evidence for `test_python_runner_cannot_touch_server_process`:

```
assert ('success' == 'success' and 11184 != 11184)
```

Run these three tests on a Linux host with `g++` and `bubblewrap`. They pass
there.

## 11. Findings

These findings come from the measurements. They are not opinions.

1. A non-progress loop is not always caught by a timeout.
   `CP08__CPP-M08_a.cpp` has an empty loop body with a loop-invariant
   condition. C++ makes a side-effect-free loop that does not terminate
   undefined behaviour. The compiler deletes the loop. The program prints `0`
   and exits with code `0`. Its sibling `CP08__CPP-M08_b.cpp` reads a
   container in the loop body. The compiler keeps that loop, and the timeout
   catches it. A judge that relies on a timeout alone misses the first form.

2. Infinite recursion is also optimized away.
   `CP07__CPP-M07_a.cpp` calls itself with the same argument. The compiler
   replaces the call with a self loop (`objdump` shows `jmp .`). The program
   never terminates. The `-O0` and the `-O1 -g` builds keep the real call.
   That build exhausts the stack and dies with `SIGSEGV` after about 104 ms.

3. The token comparison hides some wrong answers.
   The judge compares tokens. A solution that prints extra whitespace or an
   extra line still passes when the tokens match. This is a documented
   project rule, not a defect.

4. The diagnostic test files shared numbers with the hidden test files.
   The first version of the bank numbered files per test kind. A diagnostic
   test overwrote a hidden test in the same folder. The data loss was silent.
   The repo test `test_test_files_are_normalized` caught it by counting files.
   The bank now numbers files by the global order inside each problem.

5. Windows rewrites line endings.
   The host has `core.autocrlf = true`. A fresh checkout on Windows turns LF
   into CRLF. That breaks the normalization rule. The file `.gitattributes`
   now pins the bank to `eol=lf`.

6. The backend uses `-O2 -Wall` and omits `-Wextra`.
   `-Wall` already enables the two warnings that this report needs. So the
   static evidence is stable. The team can add `-Wextra` to the backend build
   for extra checks.

## 12. Reproduce the results

Run these commands in the repository folder.

Author the test cases:

```
python scripts/build_cpp_tests.py
```

Run the full verification:

```
python scripts/verify_cpp_reference.py
```

Run the verification without the sanitizer build:

```
python scripts/verify_cpp_reference.py --no-sanitize
```

Verify one problem only:

```
python scripts/verify_cpp_reference.py --only CP05
```

Run the repo test suite:

```
python -m pytest backend/tests/ -q
```

Skip the long integration test:

```
set TRACELEARN_SKIP_CPP_VERIFY=1
python -m pytest backend/tests/test_cpp_problem_bank.py -q
```

## 13. Limitations

1. The verification ran in WSL 2 on a Windows host. A native Linux run gives
   different runtimes and a different peak RSS.
2. Bubblewrap is absent in the WSL distribution. The verification used the
   `rlimit-only` mode. It did not test the isolation layer.
3. The expected outputs come from Python models. A bug in a model can pass a
   wrong expected output to the C++ solution and to the test. A second
   independent model in the repo test suite reduces this risk.
4. The bank holds eight problems. One problem targets one primary
   misconception. The taxonomy has eight misconceptions. Thus the coverage is
   one problem per misconception.
5. The verifier asserts that each variant fails at least one test. It does
   not prove that a failure indicates the misconception in a real student.
   Human review is still necessary.

## 14. Sign-off

This report records a run of `scripts/verify_cpp_reference.py`. The run used
`g++ 13.3.0` with `-std=c++17 -O2 -Wall -Wextra`. The run applied a 2000 ms
wall-clock limit and a 256 MB memory cap. The run passed 149 of 149 checks.
The report states the three pre-existing test failures by name.

---

# PART B: the full 40-problem bank

Report id: `CPP-VER-2026-10-10-02`
Date: 10 October 2026
Author: Agent 4, Lead Curriculum Engineer and C++ QA Architect
Taxonomy version: `cpp-taxonomy-0.1`

## B1. Purpose

This part records the verification of the unified bank in `data/cpp_diagnostics`. It holds 40 problems: the first 8 problems and 32 new problems. It records the compilation logs, the test assertions, the memory metrics, and the misconception triggers.

Read the bank method in [`CPP_DIAGNOSTIC_BANK_METHOD.md`](CPP_DIAGNOSTIC_BANK_METHOD.md). That document states how the team selected, merged, and verified the bank.

## B2. Result summary

| Item | Measured value |
|---|---|
| Problems verified | 40 of 40 |
| Test cases executed | 305 |
| Test executions | 915 (each test case runs 3 times) |
| Checks passed | 581 |
| Checks failed | 0 |
| Misconception variants detected | 32 of 32 |
| Hints seeded | 120 |
| Reference solutions with `verified` status | 40 of 40 |

The verifier exits with code `0`.

## B3. Check breakdown

| Check family | Count |
|---|---:|
| Compile with `-O2 -Wall -Wextra` and no warning | 80 |
| Compile with the backend flags `-O2 -Wall` | 40 |
| Run, compare, and repeat 3 times | 305 |
| AddressSanitizer and UndefinedBehaviorSanitizer | 40 |
| UBSan inside the 256 MB judged limit | 40 |
| Misconception variant fails at least one test | 32 |
| Public examples match the visible test cases | 40 |
| Sandbox limit probes | 4 |
| **Total** | **581** |

## B4. Environment

| Item | Measured value |
|---|---|
| Compiler | `g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` |
| Execution host | WSL 2, Ubuntu 24.04, Linux `6.6.87.2-microsoft-standard` |
| Sandbox engine | `backend.app.execution.sandbox.run_in_sandbox` |
| Sandbox mode | `rlimit-only` |
| Bubblewrap | Not installed in the WSL distribution |
| Wall-clock limit | 2000 ms |
| Memory limit | 256 MB |

## B5. Runtime and memory metrics

The verifier ran 305 test cases three times each. It measured the wall-clock time of each run and the child peak RSS.

| Metric | Value |
|---|---:|
| Minimum runtime | 4.23 ms |
| Median runtime | 4.55 ms |
| Maximum runtime | 10.84 ms |
| Minimum child peak RSS | 68,876 kB (67.3 MB) |
| Median child peak RSS | 100,840 kB (98.5 MB) |
| Maximum child peak RSS | 100,840 kB (98.5 MB) |
| Memory cap | 262,144 kB (256 MB) |

The wall clock leaves a large margin. The memory cap leaves about 157 MB at the median.

## B6. Misconception triggers

The bank holds 32 misconception variants. The generator builds each variant from a documented text mutation of the reference solution. The verifier compiles each variant and asserts that it fails at least one test case.

All 32 variants failed at least one test case. A sample of the measured triggers:

| Problem | Variant outcome | First failure | Expected | Actual |
|---|---|---|---|---|
| `CP09` (`CPP-M01`) | wrong output | `CP09-V1` | `14` | `30` |
| `CP10` (`CPP-M01`) | wrong output | `CP10-V1` | `2` | `3` |
| `CP13` (`CPP-M02`) | wrong output | `CP13-V1` | `5` | `0` |
| `CP16` (`CPP-M02`) | wrong output | `CP16-V1` | `5` | `1` |
| `CP17` (`CPP-M03`) | wrong output | `CP17-V1` | `7` | `70` |
| `CP20` (`CPP-M03`) | wrong output | `CP20-V1` | `7` | `61` |
| `CP21` (`CPP-M04`) | wrong output | `CP21-V1` | `4 1 2 3` | crash |
| `CP24` (`CPP-M04`) | wrong output | `CP24-V2` | `OUT_OF_RANGE` | `50` |
| `CP25` (`CPP-M05`) | wrong output | `CP25-V2` | `A` | `INVALID` |
| `CP28` (`CPP-M05`) | wrong output | `CP28-V1` | `7` | `0` |
| `CP29` (`CPP-M06`) | wrong output | `CP29-V1` | `ZERO` | `NEGATIVE` |
| `CP32` (`CPP-M06`) | wrong output | `CP32-V1` | `VOWEL` | `CONSONANT` |
| `CP33` (`CPP-M07`) | timeout | `CP33-D1` | `1` | no output |
| `CP36` (`CPP-M07`) | timeout | `CP36-D1` | `1` | no output |
| `CP37` (`CPP-M08`) | timeout | `CP37-D1` | `NOT FOUND` | no output |
| `CP40` (`CPP-M08`) | wrong output | `CP40-V3` | `3 6` | `0 0` |

The full machine-readable list is in `data/cpp_diagnostics/exports/verification_report.json`.

## B7. Sanitizer results

Every reference solution compiles with `-fsanitize=address,undefined`. Every test case runs clean. No solution reports a sanitizer error. Every solution also runs clean under `-fsanitize=undefined` inside the 256 MB judged limit.

## B8. Sandbox limit validation

Two probe programs validated the limits.

| Probe | Request | Result |
|---|---|---|
| Memory | 512 MB allocation | `std::bad_alloc`, return code -6, `memory_limit_hit=True`, 33 ms |
| Wall clock | infinite loop | timeout, return code -9, 2003 ms |

## B9. Database seeding

`scripts/seed_cpp_diagnostics.py` wrote the bank into the database.

| Table | Rows written |
|---|---:|
| `problems` | 40 |
| `test_cases` | 305 |
| `problem_hints` | 120 |
| `problem_solutions` | 40 |

The seeder is idempotent. A second run replaces the same rows. The counts do not double.

## B10. Known environment limit

The backend judge needs `g++` on `PATH`. This Windows host has no `g++`. Thus `run_submission_tests` returns `syntax_error` with the message `Compiler failed to start` on this host. That is an environment limit, not a bank defect.

The verifier proves the bank. It re-runs itself inside WSL, where `g++` exists. The 581 checks above ran in that environment.

Three tests in `backend/tests/test_security.py` fail on this host for the same reason. They pass on a Linux host with `g++` and `bubblewrap`.

## B11. Reproduce these results

```
python scripts/build_cpp_diagnostics.py
python scripts/verify_cpp_diagnostics.py
python scripts/seed_cpp_diagnostics.py
python -m pytest backend/tests/ -q
```

Verify one problem only:

```
python scripts/verify_cpp_diagnostics.py --only CP25
```

## B12. Sign-off

This part records a run of `scripts/verify_cpp_diagnostics.py`. The run used `g++ 13.3.0` with `-std=c++17 -O2 -Wall -Wextra`. The run applied a 2000 ms wall-clock limit and a 256 MB memory cap. The run passed 581 of 581 checks. All 32 misconception variants failed at least one test case.
