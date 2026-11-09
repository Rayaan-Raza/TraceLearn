"""Load problems and baseline rows into the database."""
from __future__ import annotations
import json
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.db.database import init_db
from backend.app.db.models import Problem, ProblemHint, ProblemSolution, Student, TestCase, TestType

PROBLEMS_JSON = Path("data/problems/problems.json")
CPP_BANK_JSON = Path("data/cpp_diagnostics/problems.json")
# 6 Python problems (36 tests) + the 40-problem C++ diagnostic bank (309 tests).
SEED_EXPECTED_COUNTS = {"problems": 46, "test_cases": 345, "students": 5}
_TOPIC_BY_TAG = {"loops": "Loops", "lists": "Arrays", "functions": "Functions"}


def _topic(row: dict) -> str:
    if row.get("topic"):
        return row["topic"]
    for tag in row.get("concept_tags", []):
        if tag in _TOPIC_BY_TAG:
            return _TOPIC_BY_TAG[tag]
    return "General"

def seed_problems(db: Session) -> None:
    if db.query(Problem).count() > 0:
        # Backfill metadata on databases created before these columns existed.
        for p in db.query(Problem).filter(Problem.created_by_user_id.is_(None), Problem.topic == "").all():
            p.topic = _topic({"concept_tags": json.loads(p.concept_tags or "[]")})
        return
    payload = json.loads(PROBLEMS_JSON.read_text(encoding="utf-8"))
    for row in payload["problems"]:
        db.add(Problem(
            id=row["id"], slug=row["slug"], title=row["title"], description=row["description"],
            function_name=row["function_name"],
            concept_tags=json.dumps(row.get("concept_tags", [])),
            prerequisite_tags=json.dumps(row.get("prerequisite_tags", [])),
            starter_code=row["starter_code"],
            language=row.get("language") or "python",
            topic=_topic(row),
            difficulty=row.get("difficulty") or "Easy",
            created_by_user_id=None,
        ))
        for tc in row["test_cases"]:
            db.add(TestCase(
                id=tc["id"], problem_id=row["id"], test_type=TestType(tc["test_type"]),
                name=tc["name"], input_json=json.dumps(tc["input_json"]),
                expected_output_json=json.dumps(tc["expected_output_json"]),
                diagnostic_tag=tc.get("diagnostic_tag"),
            ))

def seed_cpp_bank(db: Session) -> None:
    """The C++ diagnostic bank: problems, tests (stdin/stdout), hints and reference solutions.

    Idempotent per problem, so it also fills in a database seeded before the bank existed.
    """
    if not CPP_BANK_JSON.exists():
        return
    for row in json.loads(CPP_BANK_JSON.read_text(encoding="utf-8"))["problems"]:
        if db.get(Problem, row["id"]) is not None:
            continue
        db.add(Problem(
            id=row["id"], slug=row["slug"], title=row["title"], description=row["statement_markdown"],
            function_name="main", concept_tags="[]", prerequisite_tags="[]", starter_code="",
            language="cpp", language_standard=row.get("language_standard") or "cpp17",
            topic=row.get("primary_topic") or "General", difficulty=row.get("difficulty") or "",
            created_by_user_id=None,
        ))
        for case in row["test_cases"]:
            db.add(TestCase(
                id=case["id"], problem_id=row["id"], test_type=TestType(case["db_type"]), name=case["name"],
                input_json=json.dumps({"stdin": case["stdin"]}), expected_output_json=json.dumps(case["expected_output"]),
                diagnostic_tag=case.get("diagnostic_tag"), time_limit_ms=case.get("time_limit_ms"),
                memory_limit_mb=case.get("memory_limit_mb"),
            ))
        for hint in row.get("hints") or []:
            db.add(ProblemHint(problem_id=row["id"], misconception_id=hint["related_misconception_id"],
                               level=int(hint["order"]), text=hint["hint_text"]))
        if row.get("reference_solution_source"):
            db.add(ProblemSolution(problem_id=row["id"], language="cpp", language_standard=row.get("language_standard") or "cpp17",
                                   source_code=row["reference_solution_source"]))


def seed_students(db: Session) -> None:
    if db.query(Student).count() > 0:
        return
    for name in ("SYN001", "SYN002", "SYN003", "SYN004", "SYN005"):
        db.add(Student(display_name=name, is_synthetic=True))

def run_seed(db: Session) -> None:
    seed_problems(db)
    seed_cpp_bank(db)
    seed_students(db)
    db.commit()

def seed_database() -> None:
    from backend.app.db.database import SessionLocal
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()
