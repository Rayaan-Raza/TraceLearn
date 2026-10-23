# Schema and integration guide

Date: 10 October 2026
Audience: Backend developers and the project team
Standard: ASD-STE100 Simplified Technical English
Status: Complete

---

## 1. Purpose

This guide describes the canonical problem bank. It describes the database schema, the API, and the execution limits. It also gives the install, migration, and rollback steps.

The guide follows the existing repository patterns. The working website tables keep their current behavior. The new tables add bank features only.

## 2. Architecture summary

| Component | Technology | Function |
|---|---|---|
| Backend API | FastAPI (Python 3.11 or later) | Serves the endpoints. |
| Data layer | SQLAlchemy 2.0 ORM | Maps Python classes to tables. |
| Database | SQLite (development) or PostgreSQL (production) | Holds all data. |
| Frontend | React, Vite, TypeScript | Shows the student and teacher pages. |
| Execution | bubblewrap sandbox plus resource limits | Runs untrusted C++ code. |
| Compiler | g++ with C++17 | Compiles the student code. |

The backend runs all untrusted code in a sandbox. The sandbox uses bubblewrap on Linux. On Windows and macOS the server uses resource limits only. That mode is for development only.

## 3. Database schema

### 3.1 Existing tables (extended)

The website already uses these tables. The bank adds new columns only. Old rows keep their values.

| Table | New column | Type | Function |
|---|---|---|---|
| `problems` | `language_standard` | `VARCHAR(8)` | C++ standard, for example `cpp17`. |
| `problems` | `input_spec` | `TEXT` | Input format text. |
| `problems` | `output_spec` | `TEXT` | Output format text. |
| `problems` | `constraints` | `TEXT` | Input limits. |
| `test_cases` | `time_limit_ms` | `INTEGER NULL` | Per-test time limit. NULL uses the server setting. |
| `test_cases` | `memory_limit_mb` | `INTEGER NULL` | Per-test memory limit. NULL uses the server setting. |

The column `problems.created_by_user_id` marks a shared dataset problem when it is NULL. The bank holds only those shared problems.

### 3.2 New bank tables

The migration creates these five tables. `init_db()` creates a missing table automatically.

| Table | Function |
|---|---|
| `problem_solutions` | Reference solutions. It holds the verification status and the license. |
| `problem_tags` | Search tags. One row per problem and tag. |
| `problem_hints` | Per-problem hints. They override the template hints. |
| `problem_provenance` | Source record. It links a problem to its dataset. |
| `problem_quality_checks` | Quality-check results. One row per problem and check. |

Key columns:

| Table | Important columns |
|---|---|
| `problem_solutions` | `problem_id`, `language`, `source_code`, `verification_status`, `license` |
| `problem_tags` | `problem_id`, `tag` (unique together) |
| `problem_hints` | `problem_id`, `misconception_id`, `level`, `text` |
| `problem_provenance` | `problem_id` (primary key), `dataset_source`, `source_sha256`, `parser_version` |
| `problem_quality_checks` | `problem_id`, `check_code`, `passed`, `detail` |

The verification status has three values: `unverified`, `verified`, and `failed`.

### 3.3 Quality-check codes

The bank loader writes these checks for each problem.

| Check code | Pass condition |
|---|---|
| `statement_length` | The statement holds 80 or more characters. |
| `has_input_spec` | The input format is not empty. |
| `has_output_spec` | The output format is not empty. |
| `has_sample_tests` | The problem holds one or more samples. |
| `has_cpp_submissions` | The source record shows C++ submissions. |
| `license_recorded` | The source states a license. |

## 4. Install and migration steps

Do these steps in the repository folder.

1. Install the Python packages:

   ```
   python -m pip install -r requirements.txt
   ```

2. Create or update the database schema:

   ```
   python scripts/seed_database.py
   ```

   `seed_database.py` calls `init_db()`. `init_db()` creates each missing table. It also adds the new columns to an older `problems` or `test_cases` table.

3. Load the problem bank from the normalized dataset tables:

   ```
   python scripts/load_problem_bank.py
   ```

   The loader reads `data/Data_from_Datasets/intermediate/normalized/problems/problems.jsonl`. It loads only the rows with `student_ready=true`. The loader is safe to run again. A second run updates the same rows.

4. Check the loaded rows:

   ```
   python -c "from backend.app.db.database import SessionLocal; from backend.app.db.models import Problem; db = SessionLocal(); print(db.query(Problem).filter(Problem.id.like('B%')).count())"
   ```

Useful loader options:

| Option | Function |
|---|---|
| `--all` | Load every problem, not only the ready rows. |
| `--limit N` | Load at most N rows. |
| `--force` | Update the rows from an earlier run. |
| `--input PATH` | Use a different JSONL file. |

## 5. Rollback steps

Do these steps to remove the bank.

1. Delete the bank problems and their child rows:

   ```
   python -c "from backend.app.db.database import SessionLocal, init_db; from backend.app.db.models import Problem, TestCase, ProblemSolution, ProblemTag, ProblemHint, ProblemProvenance, ProblemQualityCheck; init_db(); db = SessionLocal(); ids = [p.id for p in db.query(Problem).filter(Problem.id.like('B%')).all()]; db.query(TestCase).filter(TestCase.problem_id.in_(ids)).delete(); db.query(ProblemSolution).filter(ProblemSolution.problem_id.in_(ids)).delete(); db.query(ProblemTag).filter(ProblemTag.problem_id.in_(ids)).delete(); db.query(ProblemHint).filter(ProblemHint.problem_id.in_(ids)).delete(); db.query(ProblemProvenance).filter(ProblemProvenance.problem_id.in_(ids)).delete(); db.query(ProblemQualityCheck).filter(ProblemQualityCheck.problem_id.in_(ids)).delete(); db.query(Problem).filter(Problem.id.in_(ids)).delete(); db.commit()"
   ```

2. Restore the earlier code with Git:

   ```
   git revert <commit>
   ```

The new columns stay in the old tables after a rollback. They hold their default values. They do not change the website behavior.

## 6. API reference

All endpoints require sign-in. Send a bearer token or the session cookie.

### 6.1 Public bank endpoints

| Method | Path | Function |
|---|---|---|
| GET | `/api/bank/problems` | List the bank problems. |
| GET | `/api/bank/problems/{problem_id}` | Show one problem statement. |
| GET | `/api/bank/tags` | List the tags and their problem counts. |
| POST | `/api/bank/problems/{problem_id}/run` | Run student code against the tests. |
| POST | `/api/bank/problems/{problem_id}/solutions` | Attach and verify a reference solution. Teachers only. |

List endpoint filters:

| Parameter | Function |
|---|---|
| `q` | Search the title and the statement. |
| `tag` | Show only the problems with this tag. |
| `difficulty` | Show only this difficulty. |
| `language` | Show only this language. |
| `limit` | Page size. 1 to 100. Default 50. |
| `offset` | Skip this many rows. |

Run request body:

```json
{"source_code": "#include <iostream>\nint main(){return 0;}"}
```

Run response fields:

| Field | Function |
|---|---|
| `execution_status` | `success`, `wrong_answer`, `syntax_error`, `timeout`, `runtime_error`, or `system_error`. |
| `passed_count` | Number of tests passed. |
| `total_count` | Number of tests run. |
| `results` | One entry per test. It holds `index`, `test_type`, `passed`, and `runtime_ms`. |

### 6.2 Security invariants

These rules apply to every endpoint. The tests in `backend/tests/test_problem_bank.py` check them.

1. A public endpoint never returns the input of a hidden test.
2. A public endpoint never returns the expected output of a hidden test.
3. A public endpoint never returns the name of a hidden test.
4. A public endpoint never returns a reference solution.
5. A student never receives the provenance record or the quality checks.
6. A teacher receives the provenance record and the quality checks.
7. The run endpoint returns an error when the sandbox is not available.

## 7. Execution queue and limits

The run endpoint uses the same execution path as the website submissions.

| Limit | Source | Default |
|---|---|---|
| CPU time | bubblewrap plus `RLIMIT_CPU` | Test limit plus one second. |
| Memory | `RLIMIT_AS` | Test `memory_limit_mb` or 256 MB. |
| Wall-clock | `subprocess` timeout | Test `time_limit_ms` or 5 seconds. |
| Output | File size cap | 64 KB. |
| Concurrency | Global semaphore | 4 runs. |
| Compile time | Compile timeout | 30 seconds. |

The service applies the per-test limits first. It uses the server settings when a test case holds no limit. A rate limit also applies: 12 runs each minute for each student.

## 8. How the website uses the bank

The bank problems are shared dataset problems. They behave like the current research problems.

- The problem list shows the bank problems to each signed-in student.
- The bank detail endpoint returns the public samples only.
- The student code runs in the sandbox with the test limits.
- The teacher can attach a reference solution. The server verifies it against the public tests.
- The hints in `problem_hints` override the template hints.

## 9. Testing and verification

Run the bank tests:

```
python -m pytest backend/tests/test_problem_bank.py -v
```

Run all tests:

```
python -m pytest backend/tests/ -v
```

Note: three security tests need a local `g++` compiler. They fail on a computer without `g++`. This failure is normal on Windows development machines.

The bank tests check these items:

1. The migration creates the five new tables.
2. The loader inserts each problem one time only.
3. The list endpoint filters by text and by tag.
4. The detail endpoint hides the hidden tests.
5. The run endpoint applies the per-test limits.
6. The run endpoint redacts the hidden outputs.
7. The solution endpoint records the verification status.

## 10. Data flow

The bank data moves in this order:

```
Datasets_RAW (read-only)
    -> normalized problems.jsonl (Agent 1 ingestion)
    -> scripts/load_problem_bank.py
    -> problems, test_cases, and the five bank tables
    -> /api/bank endpoints
    -> React frontend
```

The loader keeps the source hash and the parser version. This keeps the origin of each bank problem traceable.
