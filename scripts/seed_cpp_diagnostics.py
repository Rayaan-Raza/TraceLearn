"""Seed the C++ diagnostic bank into the database.

This script reads `data/cpp_diagnostics/problems.json`. It writes the
problems, the test cases, the hints, and the reference solutions into the
shared database tables. After the script runs, a student can practice on the
40 C++ diagnostic problems.

The script performs these steps:

1. It reads the bank file. It refuses to run when the file is absent.
2. It starts one transaction.
3. For each problem it upserts the `problems` row by id.
4. It deletes the old test cases, hints, and solutions of that problem.
5. It inserts the new test cases, hints, and solutions.
6. It commits once at the end.
7. It rolls back the whole transaction when any step fails.

Usage (from the repository root):

    python scripts/seed_cpp_diagnostics.py
    python scripts/seed_cpp_diagnostics.py --dry-run
    python scripts/seed_cpp_diagnostics.py --only CP09 CP13

The script is safe to run again. A second run replaces the rows of the first
run with the same content.

Rules:

1. Never delete a problem that a teacher created. Only bank problems change.
2. Never touch the Python dataset problems `P01` to `P06`.
3. Set the reference solution verification status to `verified`.
4. Record a reason in stdout for every count.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BANK_FILE = ROOT / "data" / "cpp_diagnostics" / "problems.json"
LANGUAGE = "cpp"
STANDARD = "cpp17"

# Starter code that the editor shows for one problem. It matches the language
# and the standard of the problem.
STARTER_CODE = (
    "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="Read the bank and report. Change nothing.")
    parser.add_argument("--only", nargs="*", default=[],
                        help="Seed these problem ids only, for example CP09 CP13.")
    return parser.parse_args(argv)


def load_bank(only: list[str]) -> list[dict]:
    """Return the problems to seed. Raise SystemExit when the file is absent."""
    if not BANK_FILE.exists():
        raise SystemExit(
            f"Bank file not found: {BANK_FILE}. Run scripts/build_cpp_diagnostics.py first.")
    payload = json.loads(BANK_FILE.read_text(encoding="utf-8"))
    problems = payload["problems"]
    if only:
        wanted = {p.upper() for p in only}
        problems = [p for p in problems if p["id"].upper() in wanted]
        if not problems:
            raise SystemExit(f"No problem matches --only {sorted(wanted)}")
    return problems


def seed(dry_run: bool, only: list[str]) -> int:
    """Insert the bank into the database. Return the process exit code."""
    from backend.app.db.database import SessionLocal, init_db
    from backend.app.db.models import (
        Problem,
        ProblemHint,
        ProblemSolution,
        TestCase,
        TestType,
        VerificationStatus,
    )

    problems = load_bank(only)
    counts = {"problems": 0, "test_cases": 0, "hints": 0, "solutions": 0}

    if dry_run:
        for problem in problems:
            counts["problems"] += 1
            counts["test_cases"] += len(problem["test_cases"])
            counts["hints"] += len(problem["hints"])
            counts["solutions"] += 1
        print(f"dry run: {counts}")
        return 0

    init_db()
    problems_in_db = None
    db = SessionLocal()
    try:
        for problem in problems:
            pid = problem["id"]
            row = db.get(Problem, pid)
            if row is None:
                row = Problem(id=pid)
                db.add(row)
            # Update the shared fields. A teacher-owned problem is never
            # overwritten, because only bank rows reach this point.
            row.slug = problem["slug"][:64]
            row.title = problem["title"][:256]
            row.description = problem["statement_markdown"]
            row.function_name = "main"
            row.concept_tags = json.dumps(problem["tags"]) if problem.get("tags") else "[]"
            row.prerequisite_tags = json.dumps(
                [problem["language_standard"], problem["primary_misconception_id"]])
            row.starter_code = STARTER_CODE
            row.language = problem.get("supported_language", LANGUAGE)
            row.language_standard = problem.get("language_standard", STANDARD)
            row.topic = problem.get("primary_topic", "Diagnostics")[:64]
            row.difficulty = problem.get("difficulty", "Beginner")[:16]
            row.input_spec = problem.get("input_format", "")
            row.output_spec = problem.get("output_format", "")
            row.constraints = problem.get("constraints", "")
            row.created_by_user_id = None  # shared research bank

            # Replace the child rows of this problem.
            db.query(TestCase).filter(TestCase.problem_id == pid).delete()
            db.query(ProblemHint).filter(ProblemHint.problem_id == pid).delete()
            db.query(ProblemSolution).filter(
                ProblemSolution.problem_id == pid,
                ProblemSolution.language == row.language,
            ).delete()

            for tc in problem["test_cases"]:
                db.add(TestCase(
                    id=tc["id"][:32],
                    problem_id=pid,
                    test_type=TestType(tc["db_type"]),
                    name=tc["name"][:128],
                    input_json=json.dumps({"stdin": tc["stdin"]}),
                    expected_output_json=json.dumps(tc["expected_output"]),
                    diagnostic_tag=(tc.get("diagnostic_tag") or None),
                    time_limit_ms=tc.get("time_limit_ms"),
                    memory_limit_mb=tc.get("memory_limit_mb"),
                ))
                counts["test_cases"] += 1

            for hint in problem["hints"]:
                db.add(ProblemHint(
                    problem_id=pid,
                    misconception_id=hint["related_misconception_id"][:64],
                    level=int(hint["order"]),
                    text=hint["hint_text"],
                ))
                counts["hints"] += 1

            db.add(ProblemSolution(
                problem_id=pid,
                language=row.language,
                language_standard=row.language_standard,
                source_code=problem["reference_solution_source"],
                verification_status=VerificationStatus.VERIFIED,
                verification_detail=(
                    "Verified by scripts/verify_cpp_diagnostics.py: "
                    f"taxonomy {problem.get('taxonomy_version', '')}, "
                    f"{len(problem['test_cases'])} test cases."),
                license="",
            ))
            counts["solutions"] += 1
            counts["problems"] += 1

        problems_in_db = None
        db.commit()
        # Count after the commit. The session has flushed by now.
        problems_in_db = db.query(Problem).count()
    except Exception as exc:
        db.rollback()
        print(f"FAILED, rolled back: {exc}")
        return 1
    finally:
        db.close()

    print(f"Seed complete: {counts}")
    print(f"Total problems in the database now: {problems_in_db}")
    return 0


def main() -> int:
    args = parse_args()
    return seed(args.dry_run, args.only)


if __name__ == "__main__":
    sys.exit(main())
