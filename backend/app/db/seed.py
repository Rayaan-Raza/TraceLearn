"""Load problems and baseline rows into the database."""
from __future__ import annotations
import json
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.db.database import init_db
from backend.app.db.models import Problem, Student, TestCase, TestType

PROBLEMS_JSON = Path("data/problems/problems.json")
SEED_EXPECTED_COUNTS = {"problems": 6, "test_cases": 36, "students": 5}

def seed_problems(db: Session) -> None:
    if db.query(Problem).count() > 0:
        return
    payload = json.loads(PROBLEMS_JSON.read_text(encoding="utf-8"))
    for row in payload["problems"]:
        db.add(Problem(
            id=row["id"], slug=row["slug"], title=row["title"], description=row["description"],
            function_name=row["function_name"],
            concept_tags=json.dumps(row.get("concept_tags", [])),
            prerequisite_tags=json.dumps(row.get("prerequisite_tags", [])),
            starter_code=row["starter_code"],
        ))
        for tc in row["test_cases"]:
            db.add(TestCase(
                id=tc["id"], problem_id=row["id"], test_type=TestType(tc["test_type"]),
                name=tc["name"], input_json=json.dumps(tc["input_json"]),
                expected_output_json=json.dumps(tc["expected_output_json"]),
                diagnostic_tag=tc.get("diagnostic_tag"),
            ))

def seed_students(db: Session) -> None:
    if db.query(Student).count() > 0:
        return
    for name in ("SYN001", "SYN002", "SYN003", "SYN004", "SYN005"):
        db.add(Student(display_name=name, is_synthetic=True))

def run_seed(db: Session) -> None:
    seed_problems(db)
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
