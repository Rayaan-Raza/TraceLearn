# C++ diagnostic bank

Taxonomy version: `cpp-taxonomy-0.1`
Date: 10 October 2026
Author: Agent 4, Lead Curriculum Engineer and C++ QA Architect

## 1. What this folder holds

This folder holds 40 C++ diagnostic problems. Each problem targets one
misconception from the taxonomy `CPP-M01` to `CPP-M08`. The problems `CP01` to
`CP08` came from the first bank. The problems `CP09` to `CP40` are new.

The bank answers one question: does each test case pass a correct solution and
fail a specific misconception?

## 2. Layout

```
data/cpp_diagnostics/
├── README.md                          ← this file
├── problems.json                      ← 40 problems, test cases and hints
├── manifest.json                      ← counts, checksums, limits
├── solutions/CPnn.cpp                 ← reference solution source
├── tests/
│   ├── public/<CPnn>/NN.in            ← visible input
│   ├── public/<CPnn>/NN.out           ← visible expected output
│   ├── hidden/<CPnn>/NN.in            ← hidden and diagnostic input
│   └── hidden/<CPnn>/NN.out           ← hidden and diagnostic expected output
├── variants/CPnn__CPP-M0X_a.cpp       ← misconception variant
└── exports/verification_report.json   ← machine-readable run output
```

## 3. Counts

| Item | Count |
|---|---:|
| Problems | 40 |
| Test cases | 305 |
| Visible test cases | 102 |
| Hidden test cases | 147 |
| Diagnostic test cases | 56 |
| Misconception variants | 32 |
| Scaffolding hints | 120 |
| Misconception categories | 8 |

## 4. Rules

1. A student can see the files in `tests/public`. A student cannot see the
   files in `tests/hidden`.
2. Diagnostic tests sit in `tests/hidden`.
3. The file number `NN` is the global order of the test inside its problem.
4. Every test file uses Unix `\n` endings and ends with one newline.
5. Every test case records a 2000 ms wall-clock limit and a 256 MB memory
   limit.
6. Problems in `solutions/` are correct. Files in `variants/` hold a defect on
   purpose.

## 5. Commands

Build the bank data:

```
python scripts/build_cpp_diagnostics.py
```

Verify the bank:

```
python scripts/verify_cpp_diagnostics.py
```

Seed the bank into the database:

```
python scripts/seed_cpp_diagnostics.py
```

Run the repo test suite:

```
python -m pytest backend/tests/ -q
```

## 6. Documents

| File | Contents |
|---|---|
| [`docs/CPP_DIAGNOSTIC_BANK_METHOD.md`](../../docs/CPP_DIAGNOSTIC_BANK_METHOD.md) | How the team built the bank, and how you add a problem |
| [`docs/CPP_MISCONCEPTION_TEST_PLAN.md`](../../docs/CPP_MISCONCEPTION_TEST_PLAN.md) | Test design rules for each misconception |
| [`docs/PROBLEM_VERIFICATION_REPORT.md`](../../docs/PROBLEM_VERIFICATION_REPORT.md) | Compilation logs, test assertions, memory metrics |
| [`docs/MISCONCEPTION_COVERAGE_MATRIX.md`](../../docs/MISCONCEPTION_COVERAGE_MATRIX.md) | The coverage requirement for each misconception |
| [`docs/TAXONOMY.md`](../../docs/TAXONOMY.md) | Misconception definitions |

## 7. Note on the label

A test failure gives evidence. It does not give a label. A wrong answer can
come from an algorithm error, a missing edge case, or a wrong reading of the
problem. Keep this separation when you use this bank.
