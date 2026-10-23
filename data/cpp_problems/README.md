# C++ misconception diagnostic bank

Taxonomy version: `cpp-taxonomy-0.1`
Date: 10 October 2026
Author: Agent 4, C++ test author and quality judge

## 1. What this folder holds

This folder holds the diagnostic tests for the C++ misconceptions `CPP-M01`
to `CPP-M08`. Each misconception has one problem, a verified reference
solution, and negative controls.

The bank answers one question: does each test case pass a correct solution and
fail a specific misconception?

## 2. Layout

```
data/cpp_problems/
├── README.md                     ← this file
├── problems.json                 ← problems and their test cases
├── tests/
│   ├── manifest.json             ← test index, checksums, sandbox limits
│   ├── public/<CPnn>/NN.in       ← visible input
│   ├── public/<CPnn>/NN.out      ← visible expected output
│   ├── hidden/<CPnn>/NN.in       ← hidden and diagnostic input
│   └── hidden/<CPnn>/NN.out      ← hidden and diagnostic expected output
├── solutions/CPnn.cpp            ← verified reference solution
├── variants/                     ← misconception variants and hard negatives
│   ├── CPnn__CPP-Mnn_a.cpp       ← a variant that holds the misconception
│   ├── CPnn__HARDNEG_*.cpp       ← correct code that looks suspicious
│   └── manifest.json             ← the expected result for each variant
└── exports/verification_report.json  ← machine-readable run output
```

## 3. Rules

1. A student can see the files in `tests/public`. A student cannot see the
   files in `tests/hidden`.
2. Diagnostic tests sit in `tests/hidden`.
3. The file number `NN` is the global order of the test inside its problem.
4. Every test file uses Unix `\n` endings and ends with one newline.
5. Every test case records a 2000 ms wall-clock limit and a 256 MB memory
   limit.
6. Problems in `solutions/` are correct. Problems in `variants/` hold a
   defect on purpose.

## 4. Commands

Author the test cases again:

```
python scripts/build_cpp_tests.py
```

Verify the bank:

```
python scripts/verify_cpp_reference.py
```

Run the repo test suite:

```
python -m pytest backend/tests/ -q
```

## 5. Documents

| File | Contents |
|---|---|
| [`docs/CPP_MISCONCEPTION_TEST_PLAN.md`](../../docs/CPP_MISCONCEPTION_TEST_PLAN.md) | Test design rules for each misconception |
| [`docs/PROBLEM_VERIFICATION_REPORT.md`](../../docs/PROBLEM_VERIFICATION_REPORT.md) | Compilation logs, test assertions, memory metrics |
| [`docs/MISCONCEPTION_COVERAGE_MATRIX.md`](../../docs/MISCONCEPTION_COVERAGE_MATRIX.md) | The coverage requirement for each misconception |
| [`docs/TAXONOMY.md`](../../docs/TAXONOMY.md) | Misconception definitions |

## 6. Note on the label

A test failure gives evidence. It does not give a label. A wrong answer can
come from an algorithm error, a missing edge case, or a wrong reading of the
problem. Keep this separation when you use this bank.
