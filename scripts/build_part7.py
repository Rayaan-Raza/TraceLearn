from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
    print("w", rel)

# Fix taxonomy ALL_LABELS
tax = (ROOT / "backend/app/diagnosis/taxonomy.py").read_text(encoding="utf-8")
if "ALL_LABELS" not in tax:
    tax = tax.strip() + "\nALL_LABELS = ALL_MISCONCEPTIONS + [NO_MISCONCEPTION, UNCERTAIN]\n"
    (ROOT / "backend/app/diagnosis/taxonomy.py").write_text(tax, encoding="utf-8")

# Demo code files
codes = {
    "SYN001_P01_a1.py": "def sum_first_n(n):\n    total = 0\n    for i in range(n + 1):\n        total += i\n    return total\n",
    "SYN001_P01_a2.py": "def sum_first_n(n):\n    s = 0\n    for i in range(n + 1):\n        s += i\n    return s\n",
    "SYN001_P02_a1.py": "def count_positive(nums):\n    c = 0\n    for i in range(len(nums)):\n        if nums[i] > 0:\n            c += 1\n    return c - (1 if nums else 0)\n",
    "SYN001_P02_a2.py": "def count_positive(nums):\n    count = 0\n    for x in nums:\n        if x > 0:\n            count += 1\n    return count\n",
    "SYN002_P01_a1.py": "def sum_first_n(n):\n    total = 0\n    for i in range(n + 1):\n        total += i\n    return total\n",
    "SYN002_P01_a2.py": "def sum_first_n(n):\n    return sum(range(n))\n",
    "SYN002_P02_a1.py": "def count_positive(nums):\n    count = 0\n    for x in nums:\n        if x > 0:\n            count += 1\n    return count\n",
    "SYN003_P03_a1.py": "def first_negative(nums):\n    for x in nums:\n        if nums[x] < 0:\n            return nums[x]\n    return None\n",
    "SYN003_P04_a1.py": "def find_max_value(nums):\n    if not nums:\n        return None\n    best_i = 0\n    for i in range(len(nums)):\n        if i > best_i:\n            best_i = i\n    return best_i\n",
    "SYN003_P04_a2.py": "def find_max_value(nums):\n    if not nums:\n        return None\n    best = nums[0]\n    for x in nums:\n        if x > best:\n            best = x\n    return best\n",
    "SYN004_P05_a1.py": "def square_number(x):\n    result = x * x\n    print(result)\n",
    "SYN004_P06_a1.py": "def absolute_difference(a, b):\n    if a >= b:\n        diff = a - b\n    else:\n        diff = b - a\n",
    "SYN004_P05_a2.py": "def square_number(x):\n    return x * x\n",
    "SYN004_P06_a2.py": "def absolute_difference(a, b):\n    if a >= b:\n        return a - b\n    return b - a\n",
    "SYN005_P01_a1.py": "def sum_first_n(n):\n    # ambiguous: uses n+1 but only for positive n\n    if n <= 0:\n        return 0\n    total = 0\n    for i in range(n + 1):\n        total += i\n    return total\n",
    "EVAL001_P01_a1.py": "def sum_first_n(n):\n    return sum(range(n + 1))\n",
    "EVAL001_P03_a1.py": "def first_negative(nums):\n    for i in range(len(nums)):\n        if nums[i] < 0:\n            return i\n    return None\n",
    "EVAL002_P05_a1.py": "def square_number(x):\n    y = x * x\n",
    "EVAL002_P02_a1.py": "def count_positive(nums):\n    return len([x for x in nums if x > 0])\n",
}

for fname, content in codes.items():
    folder = "data/demo_sequences/code" if fname.startswith("SYN") else "data/evaluation_sequences/code"
    w(f"{folder}/{fname}", content)

sequences = {
    "SYN001.json": {
        "student_id": "SYN001",
        "description": "Persistent loop-boundary misconception",
        "attempts": [
            {"problem_id": "P01", "attempt_number": 1, "source_file": "code/SYN001_P01_a1.py", "ground_truth_misconception": "M01_LOOP_BOUNDARY", "ground_truth_state": "NEW"},
            {"problem_id": "P01", "attempt_number": 2, "source_file": "code/SYN001_P01_a2.py", "ground_truth_misconception": "M01_LOOP_BOUNDARY", "ground_truth_state": "NEW"},
            {"problem_id": "P02", "attempt_number": 1, "source_file": "code/SYN001_P02_a1.py", "ground_truth_misconception": "M01_LOOP_BOUNDARY", "ground_truth_state": "PERSISTENT"},
            {"problem_id": "P02", "attempt_number": 2, "source_file": "code/SYN001_P02_a2.py", "ground_truth_misconception": "NO_MISCONCEPTION", "ground_truth_state": "IMPROVING"},
        ],
    },
    "SYN002.json": {
        "student_id": "SYN002",
        "description": "Isolated loop error",
        "attempts": [
            {"problem_id": "P01", "attempt_number": 1, "source_file": "code/SYN002_P01_a1.py", "ground_truth_misconception": "M01_LOOP_BOUNDARY", "ground_truth_state": "NEW"},
            {"problem_id": "P01", "attempt_number": 2, "source_file": "code/SYN002_P01_a2.py", "ground_truth_misconception": "NO_MISCONCEPTION", "ground_truth_state": "NEW"},
            {"problem_id": "P02", "attempt_number": 1, "source_file": "code/SYN002_P02_a1.py", "ground_truth_misconception": "NO_MISCONCEPTION", "ground_truth_state": "NEW"},
        ],
    },
    "SYN003.json": {
        "student_id": "SYN003",
        "description": "Persistent index/value misconception",
        "attempts": [
            {"problem_id": "P03", "attempt_number": 1, "source_file": "code/SYN003_P03_a1.py", "ground_truth_misconception": "M02_INDEX_VALUE", "ground_truth_state": "NEW"},
            {"problem_id": "P04", "attempt_number": 1, "source_file": "code/SYN003_P04_a1.py", "ground_truth_misconception": "M02_INDEX_VALUE", "ground_truth_state": "PERSISTENT"},
            {"problem_id": "P04", "attempt_number": 2, "source_file": "code/SYN003_P04_a2.py", "ground_truth_misconception": "NO_MISCONCEPTION", "ground_truth_state": "IMPROVING"},
        ],
    },
    "SYN004.json": {
        "student_id": "SYN004",
        "description": "Missing-return misconception that resolves",
        "attempts": [
            {"problem_id": "P05", "attempt_number": 1, "source_file": "code/SYN004_P05_a1.py", "ground_truth_misconception": "M03_MISSING_RETURN", "ground_truth_state": "NEW"},
            {"problem_id": "P06", "attempt_number": 1, "source_file": "code/SYN004_P06_a1.py", "ground_truth_misconception": "M03_MISSING_RETURN", "ground_truth_state": "PERSISTENT"},
            {"problem_id": "P05", "attempt_number": 2, "source_file": "code/SYN004_P05_a2.py", "ground_truth_misconception": "NO_MISCONCEPTION", "ground_truth_state": "IMPROVING"},
            {"problem_id": "P06", "attempt_number": 2, "source_file": "code/SYN004_P06_a2.py", "ground_truth_misconception": "NO_MISCONCEPTION", "ground_truth_state": "RESOLVED"},
        ],
    },
    "SYN005.json": {
        "student_id": "SYN005",
        "description": "Ambiguous conflicting evidence",
        "attempts": [
            {"problem_id": "P01", "attempt_number": 1, "source_file": "code/SYN005_P01_a1.py", "ground_truth_misconception": "UNCERTAIN", "ground_truth_state": "REQUIRES_TEACHER_REVIEW"},
        ],
    },
    "EVAL001.json": {
        "student_id": "EVAL001",
        "description": "Holdout evaluation sequence 1",
        "attempts": [
            {"problem_id": "P01", "attempt_number": 1, "source_file": "code/EVAL001_P01_a1.py", "ground_truth_misconception": "M01_LOOP_BOUNDARY", "ground_truth_state": "NEW"},
            {"problem_id": "P03", "attempt_number": 1, "source_file": "code/EVAL001_P03_a1.py", "ground_truth_misconception": "M02_INDEX_VALUE", "ground_truth_state": "NEW"},
        ],
    },
    "EVAL002.json": {
        "student_id": "EVAL002",
        "description": "Holdout evaluation sequence 2",
        "attempts": [
            {"problem_id": "P05", "attempt_number": 1, "source_file": "code/EVAL002_P05_a1.py", "ground_truth_misconception": "M03_MISSING_RETURN", "ground_truth_state": "NEW"},
            {"problem_id": "P02", "attempt_number": 1, "source_file": "code/EVAL002_P02_a1.py", "ground_truth_misconception": "NO_MISCONCEPTION", "ground_truth_state": "NEW"},
        ],
    },
}

for fname, data in sequences.items():
    folder = "data/demo_sequences" if fname.startswith("SYN") else "data/evaluation_sequences"
    w(f"{folder}/{fname}", json.dumps(data, indent=2))

# Update seed for 5 students
w("backend/app/db/seed.py", '''
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
''')

print("data+seed done")
