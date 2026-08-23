from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

def w(rel, text):
    (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / rel).write_text(text.strip() + "\n", encoding="utf-8", newline="\n")

w("backend/app/db/seed.py", """
\"\"\"Load problems and baseline rows into the database.\"\"\"
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.db.database import init_db
from backend.app.db.models import Problem, Student, TestCase, TestVisibility

PROBLEMS_JSON = Path("data/problems/problems.json")

SEED_EXPECTED_COUNTS = {
    "problems": 6,
    "test_cases": 36,
    "students": 3,
}


def _visibility(raw: str) -> TestVisibility:
    return TestVisibility(raw)


def seed_problems(db: Session) -> None:
    if db.query(Problem).count() > 0:
        return
    payload = json.loads(PROBLEMS_JSON.read_text(encoding="utf-8"))
    for row in payload["problems"]:
        db.add(
            Problem(
                id=row["id"],
                title=row["title"],
                description=row["description"],
                starter_code=row["starter_code"],
                difficulty=row.get("difficulty", "intro"),
                taxonomy_tags=json.dumps(row.get("taxonomy_tags", [])),
            )
        )
        for tc in row["test_cases"]:
            db.add(
                TestCase(
                    id=tc["id"],
                    problem_id=row["id"],
                    name=tc["name"],
                    stdin=tc.get("stdin", ""),
                    expected_stdout=tc["expected_stdout"],
                    visibility=_visibility(tc["visibility"]),
                    sort_order=tc.get("sort_order", 0),
                    diagnostic_tag=tc.get("diagnostic_tag"),
                )
            )


def seed_students(db: Session) -> None:
    if db.query(Student).count() > 0:
        return
    demo = [
        ("demo-alice", "Alice Demo"),
        ("demo-bob", "Bob Demo"),
        ("demo-carol", "Carol Demo"),
    ]
    for external_id, name in demo:
        db.add(Student(external_id=external_id, display_name=name))


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
""")

w("scripts/seed_database.py", """
\"\"\"CLI entrypoint to initialize and seed the TraceLearn database.\"\"\"
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.seed import SEED_EXPECTED_COUNTS, seed_database


def main() -> None:
    seed_database()
    print("Seed complete:", SEED_EXPECTED_COUNTS)


if __name__ == "__main__":
    main()
""")

w("data/annotations/ground_truth.json", """
{
  \"version\": \"poc-v1\",
  \"submissions\": []
}
""")

print("seed ok")
