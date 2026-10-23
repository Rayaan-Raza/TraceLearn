# TraceLearn

**A programming practice platform that finds misconceptions across many attempts.**

TraceLearn is a research proof of concept (POC) for a Final Year Project. Students write code and submit it. The system runs the code and examines the result. Then it finds possible misconceptions in the student's programming knowledge.

TraceLearn does not examine each submission alone. It also uses the history of the student: earlier attempts, related problems, and earlier learner states. The research question is: does this history give better diagnosis than the current submission alone?

> **NOTE:** This document uses ASD-STE100 Simplified Technical English. Words in `code format` are technical names, file names, or commands. Type commands exactly as you see them.

---

## Contents

1. [Purpose of the POC](#1-purpose-of-the-poc)
2. [Limits of the POC](#2-limits-of-the-poc)
3. [Users](#3-users)
4. [How the system works](#4-how-the-system-works)
5. [Architecture](#5-architecture)
6. [Technology](#6-technology)
7. [Repository layout](#7-repository-layout)
8. [Misconception taxonomy](#8-misconception-taxonomy)
9. [Problem bank](#9-problem-bank)
10. [Database](#10-database)
11. [Evidence types](#11-evidence-types)
12. [The two diagnosis modes](#12-the-two-diagnosis-modes)
13. [Learner states](#13-learner-states)
14. [Hints](#14-hints)
15. [Code execution and the sandbox](#15-code-execution-and-the-sandbox)
16. [Security](#16-security)
17. [User interface](#17-user-interface)
18. [API reference](#18-api-reference)
19. [Synthetic data and the experiment](#19-synthetic-data-and-the-experiment)
20. [Requirements](#20-requirements)
21. [Install the software](#21-install-the-software)
22. [Configure the software](#22-configure-the-software)
23. [Start the software on your computer](#23-start-the-software-on-your-computer)
24. [Use the software for the first time](#24-use-the-software-for-the-first-time)
25. [Run the tests](#25-run-the-tests)
26. [Run the synthetic experiment](#26-run-the-synthetic-experiment)
27. [Deploy the software](#27-deploy-the-software)
28. [Demonstration procedure (5 minutes)](#28-demonstration-procedure-5-minutes)
29. [Rules for the code](#29-rules-for-the-code)
30. [Known limits](#30-known-limits)
31. [Troubleshooting](#31-troubleshooting)
32. [Other documents](#32-other-documents)

---

## 1. Purpose of the POC

The project has one high-risk assumption:

> Evidence from earlier attempts and related problems gives useful diagnostic information. The current submission alone does not give this information.

The POC tests this assumption. It compares two diagnosis modes:

| Mode | Data that the mode can use |
|------|----------------------------|
| **A. Current-only** | The current execution, the test results, the code patterns, and the current problem. |
| **B. History-aware** | All the data of mode A. Also: earlier attempts, recurrence on other problems, success on related problems, the earlier learner state, and hint history. |

The comparison is visible to the user. The teacher submission page shows the two diagnoses side by side. The experiment script calculates metrics for the two modes against labelled synthetic data.

---

## 2. Limits of the POC

The POC does **not** prove these statements:

- History-aware diagnosis is better for real students.
- The evidence weights are correct. The team selected temporary values for the weights.

The synthetic data shows that the pipeline operates. It does not show that the method helps real students. To show this, you must have real attempt sequences and independent human labels.

The POC does not claim to invent code analysis, databases, FastAPI, React, machine learning (ML), or large language models (LLM).

---

## 3. Users

| User | Tasks in the POC |
|------|------------------|
| Student | Join a class. Write code. Submit code. Read the test results, the diagnosis, and the hints. |
| Teacher or teaching assistant | Make classes and assignments. Examine diagnoses. Confirm, reject, or correct a diagnosis. Read the experiment metrics. |
| Project evaluator or supervisor | Follow the 5-minute demonstration. Examine the evidence and the comparison pages. |

---

## 4. How the system works

The system processes each submission in this sequence:

```
Student code
    ↓
Execution in the sandbox
    ↓
Test results (visible, hidden, and diagnostic tests)
    ↓
Static code analysis (Python ast module, or C++ patterns and compiler warnings)
    ↓
Evidence from earlier attempts on the same problem
    ↓
Evidence from the learner history (related problems, earlier state)
    ↓
Evidence fusion (fixed weights from a YAML file)
    ↓
Two diagnoses: current-only AND history-aware, each with a confidence value
    ↓
Learner state update (each change records its reason)
    ↓
Hint selection (3 template levels)
    ↓
Teacher review (the original diagnosis does not change)
```

The important parts are the diagnostic rules and the comparison of the two modes. The frameworks around them are not the research contribution.

---

## 5. Architecture

```
┌──────────────────┐   HTTPS (cookie session + CSRF token)   ┌──────────────────────┐
│  React frontend  │ ──────────────────────────────────────► │  FastAPI backend     │
│  (Monaco editor) │ ◄────────────────────────────────────── │  SQLite database     │
└──────────────────┘   results, diagnoses, hints, states     └──────────┬───────────┘
                                                                        │
                    ┌───────────────────────────────────────────────────┘
                    ▼
     sandbox (bubblewrap) → analysis → diagnosis (current-only | history-aware)
          → learner model → hints → evaluation exports
```

These design rules apply:

- The domain logic is in modules. It is not in the API routes.
- Evidence extraction and evidence interpretation are in different modules.
- Current-only diagnosis and history-aware diagnosis are in different modules.
- Each API route checks the identity and the permissions of the user.

---

## 6. Technology

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11 or later, FastAPI, SQLAlchemy, Pydantic, pytest |
| Database | SQLite. The models also operate with PostgreSQL. |
| Frontend | React, Vite, TypeScript, react-router, plain CSS, Monaco editor |
| Code analysis | Python `ast` module. Regular expressions and `g++` warnings for C++. |
| Code execution | `g++` and `python3` in a bubblewrap sandbox, with resource limits |
| Authentication | JSON Web Token (JWT) in an httpOnly cookie, bcrypt password hashes |
| Metrics | pandas and scikit-learn. These calculate F1 values and confusion matrices only. The diagnosis does not use ML. |

The POC does not use: browser-side code execution, Pyodide, payments, mobile apps, plagiarism detection, LSTM or XGBoost models, or LLM help for errors.

---

## 7. Repository layout

```
TraceLearn/
├── README.md                       ← this document
├── requirements.txt                ← Python packages
├── .env.example                    ← example settings (copy to .env)
├── .gitattributes                  ← line-ending policy
├── config/
│   └── evidence_weights.yaml       ← fixed weights and thresholds
├── backend/
│   ├── app/
│   │   ├── main.py                 ← FastAPI application, middleware, routers
│   │   ├── config.py               ← all settings
│   │   ├── api/                    ← API routes
│   │   ├── auth/                   ← tokens, passwords, access rules
│   │   ├── security/               ← request limits, security headers
│   │   ├── db/                     ← models, database connection, seed data
│   │   ├── schemas/                ← request and response formats
│   │   ├── execution/              ← sandbox, C++ runner, Python runner, test runner
│   │   ├── analysis/               ← static, test, runtime, difference, history analysis
│   │   ├── diagnosis/              ← taxonomy, rules, confidence, the two modes
│   │   ├── learner_model/          ← states, history with time limits, updater
│   │   ├── hints/                  ← hint policy and hint templates
│   │   ├── evaluation/             ← labels, metrics, comparison
│   │   └── services/               ← submission pipeline, demo data
│   └── tests/                      ← unit tests, contract tests, security tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 ← routes for each role
│   │   ├── api/                    ← API client and data types
│   │   ├── pages/student/          ← student pages
│   │   ├── pages/teacher/          ← teacher pages
│   │   ├── components/             ← shared components
│   │   ├── context/                ← sign-in state, current class
│   │   └── lib/                    ← labels and data calculations
│   └── vercel.json                 ← Vercel settings
├── data/
│   ├── problems/                   ← problems.json and reference solutions
│   ├── cpp_problems/               ← C++ diagnostic bank: the first 8 problems
│   ├── cpp_diagnostics/            ← C++ diagnostic bank: all 40 problems
│   ├── demo_sequences/             ← SYN001–SYN005 demonstration attempts
│   ├── evaluation_sequences/       ← EVAL holdout attempts (do not tune on these)
│   ├── annotations/                ← ground-truth labels (evaluation only)
│   └── exports/                    ← experiment output files
├── scripts/                        ← seed, reset, experiment, export, create_teacher,
│                                     build_cpp_tests, verify_cpp_reference,
│                                     build_cpp_diagnostics, verify_cpp_diagnostics,
│                                     seed_cpp_diagnostics
└── docs/                           ← research documents and UI design documents
```

---

## 8. Misconception taxonomy

### 8.1 Python misconceptions

The POC has 3 Python misconception categories and 2 other results:

| ID | Meaning | Typical evidence |
|----|---------|------------------|
| `M01_LOOP_BOUNDARY` | Incorrect loop boundary (off-by-one error) | `range(n+1)`, `<=` in place of `<`, incorrect number of iterations |
| `M02_INDEX_VALUE` | Confusion between an index and a value | `for x in nums: nums[x]` |
| `M03_MISSING_RETURN` | The function does not return the result | No `return`, or `print` in place of `return` |
| `NO_MISCONCEPTION` | No strong evidence of a misconception | — |
| `UNCERTAIN` | The evidence is weak or it conflicts | — |

### 8.2 C++ misconceptions

The C++ analyzer can find evidence for these categories:

`CPP_LOOP_BOUNDARY`, `CPP_OFF_BY_ONE`, `CPP_ARRAY_BOUNDS`, `CPP_UNINITIALIZED_VAR`, `CPP_INT_OVERFLOW`, `CPP_MISSING_BASE_CASE`, `CPP_ASSIGN_VS_COMPARE`, `CPP_WRONG_LOOP_DIR`, `CPP_RANGE_CHECK`, `CPP_STALE_EXIT`.

The C++ diagnostic bank writes its problems, hints, and diagnostic tests in a second vocabulary, `CPP-M01` to `CPP-M08`. [`backend/app/diagnosis/cpp_mapping.py`](backend/app/diagnosis/cpp_mapping.py) translates that vocabulary, and every diagnostic test tag, into the codes above. A failing C++ diagnostic test therefore reaches a diagnosis, the learner model, and a hint. The test suite [`backend/tests/test_cpp_end_to_end.py`](backend/tests/test_cpp_end_to_end.py) reads the bank at run time and fails when a tag or a misconception has no mapping.

> **NOTE:** A code pattern is only **evidence** for a misconception. The system must not change one pattern into a permanent label for the student.

---

## 9. Problem bank

### 9.1 Dataset problems

The dataset has 6 Python problems. There are 2 problems for each misconception family. Thus the system can find recurrence across different problems.

| ID | Task | Family |
|----|------|--------|
| P01 | Sum First N: return the sum of the integers from 0 to n, but not n | M01 |
| P02 | Count Positive: count the positive items in a list | M01 |
| P03 | First Negative: return the first negative **value**, not its index | M02 |
| P04 | Find Max Value: return the largest **value**, not its position | M02 |
| P05 | Square Number: return x squared | M03 |
| P06 | Absolute Difference: return the absolute difference of a and b | M03 |

Each problem has 3 types of tests:

- **Visible** tests. The student can see the input and the expected output.
- **Hidden** tests. The system runs them, but the student cannot see the input or the expected output.
- **Diagnostic** tests. These tests target one misconception. The student cannot see them.

### 9.2 C++ diagnostic problems

The bank in `data/cpp_diagnostics` holds 40 C++ problems. Each problem targets one C++ misconception from the taxonomy `cpp-taxonomy-0.1`. The bank has 305 test cases: 102 visible, 147 hidden and 56 diagnostic. It also holds 32 misconception variants and 120 scaffolding hints.

| ID | Task | Misconception |
|----|------|--------|
| CP01 | Sum First N: sum the integers 0 to n-1. The upper bound n is exclusive. | `CPP-M01` |
| CP02 | Largest Value: print the largest value, not its position. | `CPP-M02` |
| CP03 | Return, Do Not Print: the function returns the value. | `CPP-M03` |
| CP04 | Last Element: print the last element. Index `size()` is never valid. | `CPP-M04` |
| CP05 | Range Check: print IN when x is inside the closed range 1 to 10. | `CPP-M05` |
| CP06 | Zero Test: print ZERO when x equals 0. Compare, do not assign. | `CPP-M06` |
| CP07 | Factorial: compute n! by recursion. Each call approaches the base case. | `CPP-M07` |
| CP08 | First Position: find the first position of a target. The loop must stop. | `CPP-M08` |

The problems `CP09` to `CP40` give four more problems for each misconception. Read the full list in `data/cpp_diagnostics/problems.json`.

Read the bank method in [`docs/CPP_DIAGNOSTIC_BANK_METHOD.md`](docs/CPP_DIAGNOSTIC_BANK_METHOD.md). Read the measured results in [`docs/PROBLEM_VERIFICATION_REPORT.md`](docs/PROBLEM_VERIFICATION_REPORT.md).

Seed the bank into the database. After this command a student can practice on all 40 problems.

```
python scripts/seed_cpp_diagnostics.py
```

Verify the bank. The command needs `g++` with C++17.

```
python scripts/build_cpp_diagnostics.py
python scripts/verify_cpp_diagnostics.py
```

The verifier compiles each reference solution with `g++ -O2 -Wall -Wextra -std=c++17`. It runs every test case with a 2000 ms wall-clock limit and a 256 MB memory limit. It runs each test case three times to check determinism. It builds with `-fsanitize=address,undefined`. It then checks that every misconception variant fails at least one test. The full run reports 581 checks.

> **NOTE:** The verifier needs `g++` and `python3` in a POSIX environment. On Windows it re-runs itself inside WSL. The backend judge needs `g++` on `PATH`. A host without `g++` returns `Compiler failed to start`.

### 9.3 Hints

Each C++ diagnostic problem holds 3 hints. The levels follow a scaffolding order:

| Level | Type | Function |
|-------|------|----------|
| 1 | Guiding question | It points at the vulnerable code area. |
| 2 | Concept reminder | It explains the C++ concept. It does not give the answer. |
| 3 | Partial correction | It names the syntax to check. |

Every hint carries a misconception id. The student asks for each new level on the result page. The system records each hint that it shows.

### 9.4 Teacher problems

A teacher can write new C++ problems. Each problem has stdin input and an expected output for each test case. The teacher sets each test case as visible or hidden. Only the teacher who wrote the problem can see it. Students can see it only when the teacher assigns it to them.

---

## 10. Database

The database has these tables:

| Table | Contents |
|-------|----------|
| `users` | Email, password hash, role (student or teacher), display name, token version |
| `students` | Display name. `is_synthetic` is true for the SYN research students. |
| `problems` | Title, description, function name, language, topic, difficulty, tags, owner |
| `test_cases` | Type (`visible`, `hidden`, `diagnostic`), input, expected output, diagnostic tag |
| `submissions` | Source code, attempt number, execution status, output, run time. Ground-truth fields are for evaluation only. |
| `test_results` | Result of each test for each submission |
| `evidence_items` | Source, evidence code, direction, weight, details |
| `diagnoses` | Mode (`current_only` or `history_aware`), hypotheses, confidence, uncertainty, explanation |
| `learner_states` | One row for each student and misconception: state, confidence, evidence counts |
| `learner_state_history` | All state changes, with the reason for each change. The system only adds rows. |
| `teacher_reviews` | Teacher action, corrected label, comment, time. The original diagnosis does not change. |
| `hint_events` | Hint level and hint text for each submission |
| `classrooms` | Course code, name, owner teacher, join code |
| `classroom_members` | The students in each class |
| `assignments` | Problem, class, due date, notes, state (`active` or `closed`) |
| `assignment_students` | The students for each assignment |

The diagnosis modules cannot read the ground-truth labels. Only the evaluation code reads them.

When you start the backend with an older database file, the backend adds the new columns automatically.

---

## 11. Evidence types

| Source | Examples |
|--------|----------|
| **Execution** | Syntax error, IndexError, timeout, unexpected `None` |
| **Test** | Failure of a visible, hidden, or diagnostic test (for example, the upper-boundary test) |
| **Static** | `range(n+1)`, a value used as an index, no `return`, `print` in place of `return` |
| **Sequence** | An earlier attempt on the same problem: the pattern stayed, or the pattern went away |
| **History** | Recurrence on a different problem, success on a related problem, the earlier state |

All weights are in one file: [`config/evidence_weights.yaml`](config/evidence_weights.yaml). Each confidence value is between 0 and 1. Each diagnosis keeps a list of the evidence that supports it and the evidence that conflicts with it.

> **CAUTION:** Do not change the weights after you see the results of the holdout data (`data/evaluation_sequences/`). If you change them, the holdout results become invalid.

---

## 12. The two diagnosis modes

| Data | Current-only | History-aware |
|------|--------------|---------------|
| Earlier submissions | Not permitted | Permitted only if they are **before** the current submission |
| Earlier learner state | Not permitted | Permitted, with the same time limit |
| Evidence from other problems | Not permitted | Permitted |
| Later attempts | Not permitted | Not permitted |

Different modules contain the two modes. History-aware diagnosis is not a copy of current-only diagnosis. The test `test_no_future_history_leakage` makes sure that no later data goes into a diagnosis.

---

## 13. Learner states

Each student has one state for each misconception. These are the possible states:

| State | Meaning |
|-------|---------|
| `NEW` | The system saw evidence, but the misconception does not recur yet. |
| `PERSISTENT` | The misconception recurs on different problems. |
| `IMPROVING` | Related success occurs after a persistent state. |
| `RESOLVED` | The student shows recovery. |
| `RECURRED` | The misconception occurs again after the `RESOLVED` state. |
| `REQUIRES_TEACHER_REVIEW` | The evidence is weak or it conflicts. A teacher must examine it. |

The state machine obeys these rules:

1. One submission can never make a state `PERSISTENT`.
2. More attempts on the same problem can increase the confidence. Usually, the state stays `NEW`.
3. Recurrence on a **different** related problem is the main cause of `PERSISTENT`.
4. Each state change records its reason in JSON.
5. Success on related problems can decrease the confidence. It can also change the state to `IMPROVING` or `RESOLVED`.

The state machine uses explicit rules. It is not an ML model. Refer to [`docs/LEARNER_STATE_RULES.md`](docs/LEARNER_STATE_RULES.md).

The user interface shows the states with simpler labels:

| Learner state | Label in the interface |
|---------------|------------------------|
| `PERSISTENT`, `RECURRED` | Persistent |
| `IMPROVING` | Improving |
| `NEW` | Isolated |
| `REQUIRES_TEACHER_REVIEW` | Needs review |
| `RESOLVED` | No continuing issue |

---

## 14. Hints

The system has 3 hint levels for each Python misconception:

| Level | Type |
|-------|------|
| 1 | A question that helps the student to find the problem |
| 2 | A concept reminder |
| 3 | The area of code to examine |

When the diagnosis is uncertain or needs teacher review, the system gives 1 general hint. The student asks for each new level on the result page. The system records each hint that it shows.

---

## 15. Code execution and the sandbox

The backend runs all submitted code on the server. The system treats all submitted code as **untrusted**.

### 15.1 Layers of protection

| Layer | Function |
|-------|----------|
| bubblewrap sandbox | The code runs with no network. It cannot see the project files, the database, or the `.env` file. Its environment is empty. |
| Resource limits | Limits on CPU time, memory (256 MB, or 2 GB for the compiler), output size, and open files. A timeout stops all the processes of the submission. |
| Concurrency limit | Only `MAX_CONCURRENT_EXECUTIONS` submissions run at the same time. Each user also has an execution rate limit. |
| Source check | C++ code can only include standard headers, for example `#include <iostream>`. This stops attempts to read server files through compiler errors. |
| Analysis limit | The C++ pattern analysis runs in a separate process with a 3-second limit. This stops slow regular expressions on bad input. |

Python code runs in a new `python3 -I` process in the sandbox. It never runs in the server process. The system compares C++ output word by word. Thus spaces and line breaks do not change the result.

### 15.3 Measured limits

The team measured these limits in the judging environment. The measurement ran on `g++ 13.3.0` with C++17. Read the full log in [`docs/PROBLEM_VERIFICATION_REPORT.md`](docs/PROBLEM_VERIFICATION_REPORT.md).

| Limit | Value | Measured result |
|-------|-------|-----------------|
| Wall clock | 2000 ms | A program that loops forever stops after 2003 ms. The judge returns status `timeout`. |
| Memory | 256 MB | A program that asks for 512 MB throws `std::bad_alloc` after 33 ms. The judge returns `MemoryLimitExceeded`. |
| CPU | 3 s backstop | `RLIMIT_CPU` is `int(timeout) + 1`. The wall clock usually stops the process first. |

The verifier measures the reference solutions at a median of 4.63 ms and a median child peak of 71 MB. The limits leave a large margin.

> **NOTE:** A non-progress loop is not always caught by a timeout. The compiler can delete a loop that has no side effect and no exit. Refer to finding 1 in the verification report.

---

## 16. Security

### 16.1 Access rules

- All endpoints require sign-in. The only exceptions are `/health`, registration, and sign-in.
- A **student** can see only their own submissions, diagnoses, evidence, hints, and learner states.
- The system gets the student identity from the session. It never gets it from the request body.
- A **teacher** can see only the students in their own classes. Teachers can also see the synthetic `SYN` students.
- If a user cannot see an item, the API sends "404 Not Found". Thus users cannot find the IDs of other items.
- Students never receive the input or the expected output of hidden tests and diagnostic tests.
- No endpoint sends ground-truth labels.

### 16.2 Teacher accounts

Teachers can see the work of students. Thus a user cannot make a teacher account freely. Use one of these two methods:

- Set `TEACHER_SIGNUP_CODE` in `.env`. Give the code privately to each teacher. The teacher types the code on the registration page.
- Make the account from the command line:

  ```
  python scripts/create_teacher.py teacher@school.edu "Dr. Sarah Ahmed"
  ```

  The script asks for the password. Do not type the password on the command line.

### 16.3 Sessions

- The browser keeps the session in an httpOnly cookie. JavaScript cannot read this cookie.
- Each request that changes data must send a CSRF token in the `X-CSRF-Token` header. The frontend does this automatically.
- API clients can use `Authorization: Bearer <token>` in place of the cookie.
- Sign-out cancels all tokens of the user.
- Each token has a fixed algorithm (HS256), an issuer, an audience, and an expiry time.

### 16.4 Other protections

- Rate limits on sign-in, registration, class join, and code execution.
- A request body limit of 256 KB. A source code limit of 64 KB.
- Security headers on each response: Content-Security-Policy, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, Referrer-Policy, and HSTS (if cookies are secure).
- The API documentation pages (`/docs`) are off in production.
- The demo endpoints (`/api/demo/*`) are off by default. When they are on, only teachers can use them. They change only synthetic data.
- In production, the backend does not start if the settings are not safe. For example, it does not start with a short `SECRET_KEY`.

### 16.5 Secret files

The repository does not contain secrets. Git ignores these files:

- `.env` (your settings and secrets)
- `*.db` (the database, with accounts and password hashes)
- `node_modules/` and `frontend/dist/`

> **CAUTION:** Do not add `.env` or a `.db` file to Git. Do not send the teacher sign-up code in a public channel.

The file `backend/tests/test_security.py` tests all the rules in this section.

---

## 17. User interface

The frontend uses React, Vite, TypeScript, and react-router. The Monaco editor and the fonts are part of the build. The frontend does not load files from other servers.

### 17.1 Student pages

| Page | Function |
|------|----------|
| Dashboard | Shows the focus area, the progress counts, 2 charts, the assignments, and recommended problems. |
| Practice | Shows all the problems that the student can see, with their status. |
| Problem | Shows the Monaco editor (C++ or Python) and the visible tests. Has the RUN / SUBMIT button. |
| Result | Shows the test results, the expected output, your output, the diagnosis, and the hints. |
| Classroom | Lets the student join a class with a code. Shows current and earlier assignments. |
| Submissions | Shows all attempts. Click a row to see the code and the result. |
| Progress | Shows each concept as a timeline of real learner-state changes. |

### 17.2 Teacher pages

| Page | Function |
|------|----------|
| Class Overview | Shows the class statistics and the misconception chart. Lets the teacher make a new class. |
| Classroom | Shows the join code, the student list, the assignments, and recent submissions. |
| Assign Problem | Lets the teacher select a dataset problem or write a new C++ problem with tests. |
| Assigned Problems | Shows the results and a misconception chart for each assignment. |
| Misconceptions | Shows which students have each misconception, and the state. |
| Students | Shows each student and their worst state. |
| Student details | Shows the learner states, the recent submissions, and a timeline for each concept. |
| Submission | Shows the code, all tests (also hidden tests), the 2 diagnoses side by side, the evidence, and the review form. |
| Research | Shows the live experiment metrics. Lets the teacher replay the SYN demo data. Shows the sandbox status. |

The frontend selects pages from the role that the server sends. The backend also checks the permissions for each API call.

---

## 18. API reference

The base URL is `http://127.0.0.1:8000`. All `/api` routes require sign-in, except where the table shows "public". In development, the API documentation is at `http://127.0.0.1:8000/docs`.

| Method | Path | Who can use it |
|--------|------|----------------|
| GET | `/health` | Public |
| POST | `/api/auth/register` | Public (rate limit) |
| POST | `/api/auth/login` | Public (rate limit) |
| POST | `/api/auth/logout` | Signed-in user |
| GET | `/api/auth/me` | Signed-in user |
| GET | `/api/problems` | Signed-in user |
| GET | `/api/problems/{id}` | Signed-in user. Teacher problems: owner and assigned students only. |
| POST | `/api/problems` | Teacher |
| POST | `/api/submissions` | Student. The submission is always for the signed-in student. |
| POST | `/api/submissions/{id}/run-and-analyze` | The student who made the submission |
| POST | `/api/submissions/{id}/execute`, `/analyze`, `/diagnose`, `/next-hint` | The student who made the submission |
| GET | `/api/submissions/{id}` | The student, or the teacher of the student |
| GET | `/api/submissions/{id}/evidence`, `/diagnoses`, `/test-results`, `/hints`, `/reviews` | The student, or the teacher of the student |
| GET | `/api/students` | Teacher (own class members and SYN students) |
| GET | `/api/students/{id}/submissions`, `/timeline`, `/learner-profile` | The student, or the teacher of the student |
| POST | `/api/diagnoses/{id}/teacher-review` | The teacher of the student |
| GET | `/api/classrooms` | Signed-in user (own classes) |
| POST | `/api/classrooms` | Teacher |
| POST | `/api/classrooms/join` | Student (with the join code) |
| GET | `/api/classrooms/{id}` | Owner or member |
| GET | `/api/classrooms/{id}/overview`, `/members` | Owner |
| POST | `/api/classrooms/{id}/rotate-code` | Owner |
| DELETE | `/api/classrooms/{id}/members/{student_id}` | Owner |
| GET | `/api/classrooms/{id}/assignments` | Owner, or members (own assignments only) |
| POST | `/api/classrooms/{id}/assignments` | Owner |
| GET | `/api/assignments/mine` | Signed-in user |
| GET | `/api/assignments/{id}` | Owner, or an assigned student |
| PATCH | `/api/assignments/{id}` | Owner |
| GET | `/api/evaluation/comparison` | Teacher |
| GET | `/api/demo/status` | Teacher |
| POST | `/api/demo/reset`, `/api/demo/run-sequence/{SYNnnn}` | Teacher, only if `ENABLE_DEMO_ENDPOINTS=true` |

---

## 19. Synthetic data and the experiment

### 19.1 Demo sequences (`data/demo_sequences/`)

These sequences are for the demonstration. They show these cases:

- A loop-boundary misconception that recurs on related problems: `NEW` → `PERSISTENT` → `IMPROVING`.
- One isolated failure. It must not become `PERSISTENT`.
- An index/value misconception and its recovery.
- A missing-return misconception and its resolution.
- Weak evidence, or evidence that conflicts. This gives lower confidence or teacher review.

### 19.2 Evaluation sequences (`data/evaluation_sequences/`)

These are **holdout** sequences. Do not use them to design or tune the rules or the weights. Use them only after you freeze `config/evidence_weights.yaml`.

The sequences point to real Python source files. The system runs the code and extracts the evidence. The seed data does not contain precalculated diagnoses.

### 19.3 Metrics

The experiment calculates these values for each mode:

- Accuracy, macro precision, macro recall, and macro F1
- Confusion matrices
- `history_changed_predictions` and `history_changed_correctly`
- Number of false persistent results
- Number of persistent cases found
- Learner-state accuracy, where labels exist

> **CAUTION:** Do not write metrics into the interface manually. Do not say that history is better if the calculated results do not show it. Do not change the weights after you see the holdout results.

---

## 20. Requirements

| Item | Version or note |
|------|-----------------|
| Python | 3.11 or later (tested with 3.13) |
| Node.js | 18 or later |
| `g++` | Must support C++17. Necessary for C++ problems. |
| bubblewrap | Necessary in production (Linux). Not available on Windows or macOS. |
| Operating system | Linux for production. Windows or macOS for development only. |

---

## 21. Install the software

Do these steps in the repository folder.

1. Get the repository:

   ```
   git clone https://github.com/Rayaan-Raza/TraceLearn.git
   cd TraceLearn
   ```

2. Install the Python packages:

   ```
   python -m pip install -r requirements.txt
   ```

3. Install the frontend packages:

   ```
   cd frontend
   npm install
   cd ..
   ```

4. Copy the example settings file:

   - Windows (PowerShell): `copy .env.example .env`
   - Linux or macOS: `cp .env.example .env`

5. Fill in the database with the problems and the SYN students:

   ```
   python scripts/seed_database.py
   ```

---

## 22. Configure the software

Open `.env` in a text editor. The file `.env.example` explains each setting. These settings are the most important:

| Setting | Default | Function |
|---------|---------|----------|
| `APP_ENV` | `development` | Set to `production` on a server. Production applies all security checks. |
| `SECRET_KEY` | empty | Key for the session tokens. **Necessary in production.** Use 32 or more random characters. |
| `TEACHER_SIGNUP_CODE` | empty | Code for teacher registration. If it is empty, teacher registration is off. |
| `ENABLE_DEMO_ENDPOINTS` | `false` | Turns on the SYN demo replay. Use `true` on your own computer only. |
| `SERVE_FRONTEND` | `false` | The backend also sends the built frontend from `frontend/dist`. |
| `SANDBOX_MODE` | `auto` | `auto`: use bubblewrap if it is available. `bwrap`: always require it. `none`: limits only. |
| `REQUIRE_SANDBOX` | `true` in production | Do not run code without bubblewrap. |
| `CORS_ORIGINS` | the Vite address | Other web addresses that can call the API. |
| `COOKIE_SECURE` | `true` in production | Send cookies only on HTTPS. |
| `DATABASE_URL` | `sqlite:///./tracelearn.db` | Database address |
| `EVIDENCE_WEIGHTS_PATH` | `./config/evidence_weights.yaml` | Weights file |

To make a random secret key, type:

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output into `SECRET_KEY` in `.env`.

> **NOTE:** Change the weights, the thresholds, and the learner-state limits only in `config/evidence_weights.yaml`. Freeze this file before the holdout evaluation.

---

## 23. Start the software on your computer

You must use 2 terminals. Open each terminal in the repository folder.

### 23.1 Before you start

Make these changes in `.env`:

1. Set `TEACHER_SIGNUP_CODE` to a code of your choice.
2. Set `ENABLE_DEMO_ENDPOINTS=true` if you want the SYN demo replay.

### 23.2 Terminal 1: the backend

1. Type this command:

   ```
   uvicorn backend.app.main:app --reload --port 8000
   ```

2. Make sure that the output shows `Application startup complete.`
3. Make sure that the output does not show a `Traceback`.

> **NOTE:** On Windows, the backend shows a warning that bubblewrap is not available. This is the expected result on your own computer.

### 23.3 Terminal 2: the frontend

1. Type these commands:

   ```
   cd frontend
   npm run dev
   ```

2. Open `http://localhost:5173` in your web browser.

The Vite server sends all `/api` requests to the backend on port 8000. Thus the browser sees one address, and the cookies operate correctly.

### 23.4 Stop the software

Push **Ctrl+C** in each terminal.

---

## 24. Use the software for the first time

### 24.1 Make a teacher account and a class

1. Open `http://localhost:5173`.
2. Click **Create account**.
3. Type your name, email, and password. The password must have 8 or more characters.
4. Select **I am a teacher**.
5. Type the teacher invite code from `.env`.
6. Click **Create account**.
7. Type a course code and a course name. Then click **Create classroom**.
8. Go to the **Classroom** page. Record the join code.

### 24.2 Make a student account and join the class

1. Open a private window in your web browser.
2. Open `http://localhost:5173`.
3. Click **Create account**. Do not select **I am a teacher**.
4. Go to the **Classroom** page.
5. Type the join code. Then click **Join class**.

### 24.3 Give an assignment and submit code

1. As the teacher, go to **Classroom** → **Assign Problem**.
2. Select a problem, or write a new C++ problem. Then click **Assign to class**.
3. As the student, go to **Practice**. Click the problem.
4. Write the code in the editor. Then click **Run / Submit**.
5. Read the result. Click **Show a hint** if you need help.
6. As the teacher, open **Students** → the student → the submission.
7. Compare the 2 diagnoses. Save a review.

---

## 25. Run the tests

1. Go to the repository folder.
2. Type this command:

   ```
   python -m pytest backend/tests/ -v
   ```

3. Make sure that all tests pass.

The tests examine these items:

- Execution: success, failure, and timeout
- Static patterns for M01, M02, and M03
- Current-only diagnosis cannot use history
- History-aware diagnosis uses only earlier data (no future data)
- Repetition on the same problem does not automatically give `PERSISTENT`
- Recurrence on different problems can give `PERSISTENT`
- Diagnosis and API responses do not contain ground-truth labels
- Teacher review does not change the original diagnosis
- Security (`test_security.py`): sign-in on each endpoint, access between users, CSRF, false tokens, sign-out, hidden test data, input limits, and sandbox isolation

To make sure that the frontend builds correctly, type:

```
cd frontend
npm run build
```

---

## 26. Run the synthetic experiment

1. Type this command:

   ```
   python scripts/run_synthetic_experiment.py
   ```

2. Examine the files in `data/exports/`.

The script does these steps:

1. It deletes the database and makes a new one.
2. It adds the problems and the SYN students.
3. It runs each demo attempt through the full pipeline.
4. It compares the predictions with the labels.
5. It writes the results to `data/exports/`.

The script makes these files:

- `submission_predictions.csv`
- `evidence_items.csv`
- `state_transitions.csv`
- `experiment_summary.json`
- `confusion_current_only.csv` and `confusion_history_aware.csv`

These scripts are also available:

| Script | Function |
|--------|----------|
| `python scripts/reset_demo.py` | Deletes the data of the SYN students only. Real users do not change. |
| `python scripts/export_results.py` | Writes the export files again. |
| `python scripts/create_teacher.py` | Makes a teacher account. |

> **CAUTION:** `run_synthetic_experiment.py` deletes the database file `tracelearn.db`. Do not run it on a database with real users.

---

## 27. Deploy the software

The deployment has 2 parts. The backend must run on a Linux server. The frontend can run on Vercel.

> **NOTE:** Vercel cannot run the backend. The backend must compile and run code in a sandbox, and it must keep a database file. Vercel functions cannot do these tasks.

### 27.1 Deploy the backend on a Linux server

Use a Linux server that permits bubblewrap, for example a virtual machine from DigitalOcean or Azure. Container platforms (for example Render or Railway) usually do not permit bubblewrap.

1. Install the system packages:

   ```
   sudo apt install python3 python3-pip python3-venv g++ bubblewrap git
   ```

2. Get the repository and install the Python packages. Refer to [section 21](#21-install-the-software).
3. In `.env`, set these values:

   ```
   APP_ENV=production
   SECRET_KEY=<random value of 32 or more characters>
   TEACHER_SIGNUP_CODE=<private code>
   COOKIE_SECURE=true
   ENABLE_DEMO_ENDPOINTS=false
   ```

4. Fill in the database:

   ```
   python3 scripts/seed_database.py
   ```

5. Start the backend:

   ```
   uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1
   ```

6. Put an HTTPS reverse proxy (for example Caddy or nginx) in front of port 8000.
7. Make sure that `https://<your backend address>/health` shows `{"status":"ok"}`.

> **CAUTION:** If the backend does not start, read the error. In production, the backend stops if a setting is not safe. Do not turn off these checks.

### 27.2 Deploy the frontend on Vercel

1. Open `frontend/vercel.json`.
2. Add this rewrite **before** the current rewrite. Replace `YOUR-BACKEND-DOMAIN` with your backend address.

   ```json
   { "source": "/api/(.*)", "destination": "https://YOUR-BACKEND-DOMAIN/api/$1" }
   ```

3. Commit and push the change.
4. On Vercel, import the GitHub repository.
5. Set **Root Directory** to `frontend`.
6. Make sure that Vercel selects **Vite**, the build command `npm run build`, and the output folder `dist`.
7. Click **Deploy**.

The rewrite sends all `/api` requests through Vercel to the backend. Thus the browser sees one address, and the sign-in cookies operate correctly.

> **NOTE:** Through Vercel, all requests come to the backend from the Vercel addresses. Thus the limits for each address apply to all users together. Before a full class registers, increase these values in the backend `.env`: `REGISTER_ATTEMPTS_PER_HOUR=500` and `LOGIN_ATTEMPTS_PER_MINUTE=60`. The limit for each account continues to stop password attacks.

### 27.3 Alternative: one server for the two parts

You can also send the frontend from the backend:

1. Build the frontend: `cd frontend`, then `npm ci`, then `npm run build`.
2. Set `SERVE_FRONTEND=true` in `.env`.
3. Start the backend as in [section 27.1](#271-deploy-the-backend-on-a-linux-server).

---

## 28. Demonstration procedure (5 minutes)

Before the demonstration, set `ENABLE_DEMO_ENDPOINTS=true` and start the software. Sign in as a teacher.

1. **Reset.** Go to **Research**. Click **Reset synthetic data**.
2. **SYN002 (isolated mistake).** Click **Run SYN002**. This student makes one off-by-one error and then succeeds on a related problem. Current-only diagnosis can show M01 evidence. History-aware diagnosis must not show a confident `PERSISTENT` state. The message is: *one failure is evidence, not a permanent label.*
3. **SYN001 (persistent).** Click **Run SYN001**. This student makes the same error on P01, tries again, and then makes the error on P02. The recurrence on different problems moves the state to `PERSISTENT`.
4. **Comparison.** Open SYN001 → a submission. Show which history evidence changed the confidence or the state.
5. **Corrected attempt.** Show that the evidence decreases and the state moves to `IMPROVING`.
6. **Teacher view.** Show the diagnosis, the confidence, the evidence, and the review form.
7. **Experiment view.** Go to **Research**. Show the calculated metrics for the 2 modes. The interface does not contain fixed metric values.

---

## 29. Rules for the code

The team obeys these rules:

1. Do not invent experiment results.
2. Do not call the learner-state machine an ML model.
3. Keep the domain logic out of the API routes.
4. Keep evidence extraction separate from evidence interpretation.
5. Keep the two diagnosis modes separate. Each mode must have its own tests.
6. Each diagnosis must show the reason for its result.
7. Each learner-state change must record its reason.
8. One submission must never make a state `PERSISTENT`.
9. Success on a related problem must be able to decrease the confidence.
10. Weak evidence, or evidence that conflicts, can give `UNCERTAIN` or teacher review.
11. Keep the raw execution and test evidence.
12. Do not change a system diagnosis after a teacher correction.
13. Do not use LLM calls in the diagnosis core.
14. Only the evaluation code can read the ground-truth labels.
15. History must contain only data from before the submission. Do not use future data.
16. Each API route must check the identity and the permissions of the user.
17. Do not send hidden test data to students.
18. Do not put secrets in the repository.

---

## 30. Known limits

- The isolation of submitted code requires bubblewrap. Without it, do not let other persons use the server.
- The rate limits are in memory, for each process. If you use more than one worker, also add limits at the reverse proxy.
- C++ runtime evidence is not complete. A C++ crash or timeout is recorded on the submission, but it is not yet linked to a misconception. The mapping table in `backend/app/diagnosis/cpp_mapping.py` covers the static and the diagnostic evidence.
- The diagnosis uses rules only. It does not use ML or LLM.
- The data is synthetic only. The metrics show that the POC operates. They do not show that it helps real students.
- The Python bank holds 3 misconceptions and 6 problems. The C++ diagnostic bank adds 8 misconceptions (`CPP-M01` to `CPP-M08`) across 40 problems, and all of them reach the same learner model. The planned full system has more.
- The evidence weights are temporary values. They are not validated with real data.

---

## 31. Troubleshooting

| Problem | Possible cause | Action |
|---------|----------------|--------|
| `ModuleNotFoundError: backend` | The terminal is not in the repository folder. | Go to the repository folder. Then type the command again. |
| The backend does not start in production | A setting is not safe. | Read the error list. Usually `SECRET_KEY` has no value or is too short. |
| `Status code 204 must not have a response body` | You have an old version of the code. | Get the latest version: `git pull`. |
| "Code execution requires bubblewrap" | bubblewrap is not installed. | Type `sudo apt install bubblewrap`. In Docker, permit unprivileged namespaces. |
| The sign-in page comes back after each reload | The browser does not keep the cookies. | In development, use the Vite address (port 5173). In production, use one address (Vercel rewrite or `SERVE_FRONTEND`). `COOKIE_SECURE=true` requires HTTPS. |
| "CSRF token missing or invalid" | The request has the cookie but not the CSRF header. | Use the frontend client, or use a Bearer token. |
| "Too many requests" (429) | A rate limit stopped the request. | Wait 1 minute. Then try again. |
| The problem list is empty | The database has no problems. | Type `python scripts/seed_database.py`. |
| The data is old or incorrect | The database has old data. | Delete `tracelearn.db`. Then type `python scripts/seed_database.py`. |
| Teacher registration fails | The invite code is incorrect or empty. | Set `TEACHER_SIGNUP_CODE` in `.env`. Restart the backend. |
| The metrics look too good | Possibly someone tuned the weights on the holdout data. | Do not change the weights after holdout. Report the real results. |

---

## 32. Other documents

| File | Contents |
|------|----------|
| [`docs/MASTER_POC.md`](docs/MASTER_POC.md) | Master POC document: all features and the demonstration plan |
| [`docs/POC_SCOPE.md`](docs/POC_SCOPE.md) | Scope and time-order design |
| [`docs/TAXONOMY.md`](docs/TAXONOMY.md) | Definitions of the misconceptions |
| [`docs/LEARNER_STATE_RULES.md`](docs/LEARNER_STATE_RULES.md) | Rules for `NEW` and `PERSISTENT`, and the state changes |
| [`docs/EXPERIMENT.md`](docs/EXPERIMENT.md) | Fixed weights and the holdout policy |
| [`docs/MISCONCEPTION_COVERAGE_MATRIX.md`](docs/MISCONCEPTION_COVERAGE_MATRIX.md) | Coverage requirement for each misconception |
| [`docs/CPP_MISCONCEPTION_TEST_PLAN.md`](docs/CPP_MISCONCEPTION_TEST_PLAN.md) | Test design rules for each C++ misconception |
| [`docs/CPP_DIAGNOSTIC_BANK_METHOD.md`](docs/CPP_DIAGNOSTIC_BANK_METHOD.md) | How the team built the 40-problem bank, and how you add a problem |
| [`docs/PROBLEM_VERIFICATION_REPORT.md`](docs/PROBLEM_VERIFICATION_REPORT.md) | Compilation logs, test assertions, memory metrics |
| [`docs/ui/`](docs/ui/) | User interface design documents and the demonstration script |
| [`docs/CI_CD.md`](docs/CI_CD.md) | CI/CD workflows, release tags and the bundle smoke test |
| [`.env.example`](.env.example) | All settings, with an explanation of each |

---

## License and academic use

This software is for the Final Year Project proposal demonstration and supervised research. Do not deploy it as a production learning platform without these items:

- A secure execution environment
- Evaluation with real students
- A full security and product review
