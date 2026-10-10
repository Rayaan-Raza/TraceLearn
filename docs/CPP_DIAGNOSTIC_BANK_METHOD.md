# How The C++ Diagnostic Bank Was Built

Report id: `CPP-BANK-2026-10-10-01`
Date: 10 October 2026
Taxonomy version: `cpp-taxonomy-0.1`
Standard: ASD-STE100 Simplified Technical English

---

## 1. Purpose

This document explains the method that produced the C++ diagnostic bank in
`data/cpp_diagnostics`. It states how the team selected the problems. It
states how the team merged the data. It states how the team wrote the hints.
It states how you add a new problem later.

The bank holds 40 problems. Each problem targets one misconception from the
taxonomy `CPP-M01` to `CPP-M08`.

---

## 2. Sources and the merge

The bank has two sources. The team merged them into one folder.

| Source | Count | What it holds |
|---|---:|---|
| `data/cpp_problems` | 8 | The first eight diagnostic problems. They were authored and verified earlier. |
| `scripts/cpp_defs` | 32 | The new problem definitions. Four problems target each misconception. |

### 2.1 The merge rule

`scripts/build_cpp_diagnostics.py` merges the two sources. It applies these
rules:

1. It reads the 8 problems from `data/cpp_problems/problems.json`. It keeps
   the ids `CP01` to `CP08`.
2. It reads the 32 definitions from `scripts/cpp_defs`. The ids are `CP09` to
   `CP40`.
3. It adds three scaffolding hints to each of the first 8 problems. The
   original bank held no hints.
4. It writes one output file per problem. It writes the reference solutions,
   the test files, and the misconception variants.
5. It writes `data/cpp_diagnostics/problems.json`. That file is
   self-contained. The seeder needs only that file.

The merge is lossless. Every test case and every expected output moves to the
new bank unchanged.

### 2.2 Why a second bank folder

The first bank `data/cpp_problems` holds the test files on disk and the
problems in a separate file. The seeder had to read two places. The new bank
holds everything in one JSON file. That makes the seeder simple and makes the
bank portable.

The team keeps the old folder. It is the source of the first 8 problems. Do
not edit it by hand.

---

## 3. How the team selected the 32 problems

### 3.1 The selection rule

The coverage matrix in `docs/MISCONCEPTION_COVERAGE_MATRIX.md` requires at
least two tests per misconception. This plan goes further. It requires four
problems per misconception. Thus the team can measure recurrence across
different problems. Recurrence on different problems is the main cause of the
learner state `PERSISTENT`.

### 3.2 The distribution

| Misconception | Problems | Ids |
|---|---:|---|
| `CPP-M01` | 4 | `CP09`, `CP10`, `CP11`, `CP12` |
| `CPP-M02` | 4 | `CP13`, `CP14`, `CP15`, `CP16` |
| `CPP-M03` | 4 | `CP17`, `CP18`, `CP19`, `CP20` |
| `CPP-M04` | 4 | `CP21`, `CP22`, `CP23`, `CP24` |
| `CPP-M05` | 4 | `CP25`, `CP26`, `CP27`, `CP28` |
| `CPP-M06` | 4 | `CP29`, `CP30`, `CP31`, `CP32` |
| `CPP-M07` | 4 | `CP33`, `CP34`, `CP35`, `CP36` |
| `CPP-M08` | 4 | `CP37`, `CP38`, `CP39`, `CP40` |

### 3.3 The topic rule

The team varied the topic inside each misconception. A student who fixes one
loop-boundary problem may still hold the belief on a different topic. Four
topics per misconception test that.

For example, `CPP-M01` covers a numeric sum, a count with a divisor, a reverse
print, and a product. `CPP-M03` covers an absolute value, a maximum, a bool
test, and a divisor.

### 3.4 The difficulty rule

The team assigned `Beginner` to 28 problems and `Intermediate` to 12. The
intermediate problems are the ones that need sorting, recursion with two base
cases, or a Euclid loop.

---

## 4. How the team designed each problem

Each problem definition holds these parts:

| Field | Purpose |
|---|---|
| `id`, `slug`, `title` | Identity. The id is the primary key. |
| `misconception` | The primary target. |
| `secondary` | Other misconceptions the problem can also show. |
| `difficulty`, `topic` | Catalog metadata. |
| `statement_markdown` | The task, the input section, the output section, the constraints, and the examples. |
| `input_format`, `output_format`, `constraints` | The contract, as separate fields. |
| `examples` | Two public examples with an explanation each. |
| `solution` | The reference C++17 source. |
| `mutation` | The text change that makes the misconception variant. |
| `render`, `model` | The stdin writer and the expected-output model. |
| `cases` | The test cases. |
| `hints` | Three scaffolding hints. |

### 4.1 The reference solution rule

The reference solution obeys these rules:

1. It compiles with `g++ -std=c++17 -O2 -Wall -Wextra` with no warning.
2. It reads from stdin and writes to stdout.
3. It guards every input read. A short input gives a clean exit.
4. It uses the naming conventions in the definition module. The generator and
   the verifier depend on those names.

### 4.2 The expected-output rule

The team does not write the expected output by hand. Each definition holds a
Python `model` function. The generator calls the model. This keeps the
expected output separate from the C++ solution. A bug in the solution cannot
change the expected output.

A second independent model lives in `backend/tests/test_cpp_problem_bank.py`.
It checks every `.out` file. Two models catch a wrong model.

### 4.3 The mutation rule

Each definition holds a `mutation` list. Each entry is a pair of strings. The
first string is text in the reference solution. The second string is the
replacement text.

The generator applies the mutation to the reference source. The result is the
misconception variant. The verifier then compiles the variant and asserts that
it fails at least one test case.

This rule makes the misconception explicit and machine-checked. A human does
not write a second broken program by hand.

---

## 5. How the team wrote the test cases

### 5.1 The test kinds

Each problem holds 7 to 8 test cases:

| Kind | Count | Purpose |
|---|---:|---|
| Visible | 3 | The student sees these. One is a boundary case. |
| Hidden | 2 to 3 | More coverage. The student does not see these. |
| Diagnostic | 2 | The misconception trigger. The student does not see these. |

### 5.2 The trigger rule

A diagnostic test carries `diagnostic_trait` with the misconception id. The
test must fail when the student holds that misconception. It must pass for the
reference solution.

The verifier proves this. It compiles the variant from the mutation. It runs
the full test set. It asserts that the variant fails at least one test case.
The verifier records the first failure with the expected output, the actual
output, and the return code.

### 5.3 The measured trigger result

The verifier ran on `g++ 13.3.0`. It checked 32 variants. Every variant failed
at least one test case. The table shows a sample:

| Problem | Variant result | First failure | Expected | Actual |
|---|---|---|---|---|
| `CP09` | wrong output | `CP09-V1` | `14` | `30` |
| `CP13` | wrong output | `CP13-V1` | `5` | `0` |
| `CP21` | wrong output | `CP21-V1` | `4 1 2 3` | crash |
| `CP25` | wrong output | `CP25-V2` | `A` | `INVALID` |
| `CP29` | wrong output | `CP29-V1` | `ZERO` | `NEGATIVE` |
| `CP33` | timeout | `CP33-D1` | `1` | no output |
| `CP37` | timeout | `CP37-D1` | `NOT FOUND` | no output |
| `CP40` | wrong output | `CP40-V3` | `3 6` | `0 0` |

---

## 6. How the team wrote the hints

### 6.1 The three levels

Each problem holds three hints. The levels follow a scaffolding order. The
student asks for each level in turn.

| Level | Type | What it does |
|---|---|---|
| 1 | Guiding question | Points at the vulnerable code area. It does not name the fix. |
| 2 | Concept reminder | Explains the C++ concept. It does not give the answer. |
| 3 | Partial correction | Names the syntax to check. It shows the correct form. |

### 6.2 The mapping rule

Every hint carries `related_misconception_id`. The value is the primary
misconception of the problem. The seeder writes this value to the
`problem_hints.misconception_id` column. Thus the hint policy can select a
hint by misconception.

### 6.3 The writing rule

The team wrote the hints in ASD-STE100 Simplified Technical English. Each hint
holds one instruction or one question. The team avoided the word "wrong". The
hints describe the code, not the student.

A level 3 hint may show the correct expression. For example, for `CPP-M01`
the level 3 hint says: "Check your comparison operator. An exclusive bound
uses `<`, not `<=`."

### 6.4 The hint count

The bank holds 120 hints. That is 3 hints for each of the 40 problems.

---

## 7. How the team verified the bank

`scripts/verify_cpp_diagnostics.py` is the quality gate. It ran 581 checks.
All 581 checks passed. The checks cover these items:

| Item | Checks |
|---|---:|
| Compile with `-O2 -Wall -Wextra` | 80 |
| Compile with the backend flags | 40 |
| Run, compare, and repeat 3 times | 305 |
| AddressSanitizer and UBSan | 40 |
| UBSan inside the 256 MB judged limit | 40 |
| Misconception variant fails | 32 |
| Public examples match the visible cases | 40 |
| Sandbox limit probes | 4 |
| **Total** | **581** |

The measured runtime median was about 4.6 ms per test case. The measured
child peak memory was about 71 MB. Both are far inside the limits.

---

## 8. How you add a new problem later

Follow these steps. Each step is one command or one file edit.

### 8.1 Write the definition

Open the definition module for the misconception. For example, open
`scripts/cpp_defs/m01_m02.py` for a `CPP-M01` problem.

Copy one existing problem. Then change these fields:

1. `id`: Use the next free id. Do not reuse an id.
2. `slug` and `title`: Use a short unique name.
3. `misconception`: Keep the same value.
4. `statement_markdown`, `input_format`, `output_format`, `constraints`.
5. `examples`: Give two examples with an explanation each. The input must
   match a visible test case exactly.
6. `solution`: Write the C++17 source. Obey the naming conventions.
7. `mutation`: Give one pair of strings. The first string must occur in the
   solution. The generator stops when it does not.
8. `render`: A function that returns the stdin text.
9. `model`: A function that returns the expected output.
10. `cases`: Give the test cases. Use the kinds `visible`, `hidden` and
    `diagnostic`.
11. `hints`: Give three hints.

### 8.2 Build the bank

```
python scripts/build_cpp_diagnostics.py
```

The generator reports the problem count, the test count, the variant count,
and the hint count.

### 8.3 Verify the bank

```
python scripts/verify_cpp_diagnostics.py
```

The verifier must report 0 failed checks. If a check fails, read the detail.
The detail names the test case and shows the expected and the actual output.

### 8.4 Seed the bank

```
python scripts/seed_cpp_diagnostics.py
```

The seeder inserts the new problem, its test cases, its hints, and its
reference solution. A student can then see the problem.

### 8.5 Add a check for the new problem

Open `backend/tests/test_cpp_problem_bank.py`. The structural tests read the
bank file. A new problem passes the structural tests automatically. Add a
targeted test only when the problem has a new shape.

---

## 9. Rules for a new problem

Obey these rules. A problem that breaks a rule will fail the verifier.

1. Use a unique id.
2. Keep one primary misconception per problem.
3. Give at least 3 visible, 2 hidden and 2 diagnostic test cases.
4. Mark at least one visible test case as a boundary case.
5. Make the mutation text occur in the reference solution.
6. Make the variant fail at least one test case.
7. Make the expected output come from the `model` function.
8. Write the reference solution with no compiler warning.
9. Keep every test file at LF endings with one final newline.
10. Write all prose in ASD-STE100 Simplified Technical English.

---

## 10. Commands

Author the bank data:

```
python scripts/build_cpp_diagnostics.py
```

Verify the bank:

```
python scripts/verify_cpp_diagnostics.py
python scripts/verify_cpp_diagnostics.py --no-sanitize
python scripts/verify_cpp_diagnostics.py --only CP25
```

Seed the bank into the database:

```
python scripts/seed_cpp_diagnostics.py
python scripts/seed_cpp_diagnostics.py --dry-run
python scripts/seed_cpp_diagnostics.py --only CP09 CP13
```

Run the repo test suite:

```
python -m pytest backend/tests/ -q
```

---

## 11. Files

| File | Purpose |
|---|---|
| `scripts/cpp_defs/` | The 32 problem definitions. Edit here. |
| `scripts/build_cpp_diagnostics.py` | The generator. It merges and writes the bank. |
| `scripts/verify_cpp_diagnostics.py` | The verifier. It compiles and runs everything. |
| `scripts/seed_cpp_diagnostics.py` | The seeder. It writes the database. |
| `data/cpp_diagnostics/problems.json` | The self-contained bank. 40 problems. |
| `data/cpp_diagnostics/solutions/` | The 40 reference solution sources. |
| `data/cpp_diagnostics/tests/` | The 305 test files, in `public` and `hidden`. |
| `data/cpp_diagnostics/variants/` | The 32 misconception variant sources. |
| `data/cpp_diagnostics/exports/` | The machine-readable verification report. |
| `backend/tests/test_cpp_problem_bank.py` | The structural repo tests. |

---

## 12. Limits of this method

1. The verifier needs `g++` and `python3` in a POSIX environment. On Windows
   it re-runs itself inside WSL.
2. The backend judge needs `g++` on `PATH`. A Windows host without `g++`
   returns `Compiler failed to start`. That is an environment limit, not a
   bank defect.
3. The bank proves that a variant fails a test. It does not prove that a real
   student holds the belief. Human review is still necessary.
4. The expected output comes from a Python model. A second model reduces the
   risk of a wrong model. It does not remove the risk.
