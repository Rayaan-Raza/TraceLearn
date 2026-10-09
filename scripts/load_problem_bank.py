"""Load the canonical problem bank from the normalized dataset tables.

Reads one JSONL row per problem and writes the shared bank tables:
`problems`, `test_cases`, `problem_tags`, `problem_provenance` and
`problem_quality_checks`. Bank problems use short ids with the prefix `B`.
The dataset canonical id is kept in `problem_provenance.canonical_id`, so a
second run updates the same rows instead of creating duplicates.

Usage (from the repository root):

    python scripts/load_problem_bank.py
    python scripts/load_problem_bank.py --all --limit 100
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.database import SessionLocal, init_db  # noqa: E402
from backend.app.db.models import (  # noqa: E402
    Problem,
    ProblemProvenance,
    ProblemQualityCheck,
    ProblemTag,
    TestCase,
    TestType,
)

DEFAULT_INPUT = Path("data/Data_from_Datasets/intermediate/normalized/problems/problems.jsonl")
STARTER_CODE = (
    "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
)
MIN_STATEMENT_CHARS = 80
_ID_PREFIX = "B"
_ID_WIDTH = 6

# Statements hold section headings. These headings are not useful as topics.
_NON_TOPIC_HEADINGS = {
    "input", "output", "sample input", "sample output",
    "output for the sample input", "constraints", "description",
    "problem description", "examples", "task",
}


def _next_bank_id(db) -> str:
    """Return the next free short bank id, for example B000007."""
    rows = db.query(Problem.id).filter(Problem.id.like(f"{_ID_PREFIX}%")).all()
    top = 0
    for (pid,) in rows:
        try:
            top = max(top, int(pid[len(_ID_PREFIX):]))
        except ValueError:
            continue
    return f"{_ID_PREFIX}{top + 1:0{_ID_WIDTH}d}"


def _topic(row: dict) -> str:
    """Pick a coarse topic from the statement section headings."""
    for heading in row.get("section_headings") or []:
        h = str(heading).strip()
        if h and h.lower() not in _NON_TOPIC_HEADINGS:
            return h[:64]
    return "General"


def _spec(row: dict, *names: str) -> str:
    for n in names:
        val = row.get(n)
        if val:
            return str(val)
    return ""


def _quality_checks(row: dict, statement: str) -> list[tuple[str, bool, str]]:
    """Return the quality-check rows for one problem row."""
    stmt = statement or ""
    checks = [
        ("statement_length", len(stmt) >= MIN_STATEMENT_CHARS,
         f"{len(stmt)} characters"),
        ("has_input_spec", bool(_spec(row, "input_spec", "input_description")), ""),
        ("has_output_spec", bool(_spec(row, "output_spec", "output_description")), ""),
        ("has_sample_tests", int(row.get("sample_test_count") or 0) > 0,
         f"{int(row.get('sample_test_count') or 0)} samples"),
        ("has_cpp_submissions", int(row.get("cpp_submission_count") or 0) > 0,
         f"{int(row.get('cpp_submission_count') or 0)} C++ submissions"),
        ("license_recorded", bool(row.get("source_license")),
         row.get("source_license") or "source license not recorded"),
    ]
    return checks


def load_bank(input_path: Path, *, ready_only: bool = True, limit: int = 0,
              force: bool = False) -> dict[str, int]:
    """Load bank rows from the JSONL file. Return a summary of the work."""
    init_db()
    db = SessionLocal()
    inserted = updated = skipped = 0
    try:
        rows = []
        with input_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("record_type", "problem") != "problem":
                    continue
                if ready_only and not row.get("student_ready"):
                    continue
                rows.append(row)
        if limit:
            rows = rows[:limit]

        for row in rows:
            canonical = str(row.get("problem_id") or "")
            if not canonical:
                skipped += 1
                continue
            statement = _spec(row, "statement_text", "statement") or ""
            if len(statement) < MIN_STATEMENT_CHARS:
                skipped += 1
                continue

            prov = db.query(ProblemProvenance).filter(
                ProblemProvenance.canonical_id == canonical).first()
            problem = db.get(Problem, prov.problem_id) if prov else None
            if problem is not None and not force:
                skipped += 1
                continue

            dataset = str(row.get("source_dataset") or row.get("dataset_source") or "").upper()
            topic = _topic(row)
            fields = {
                "slug": canonical.lower()[:64],
                "title": (row.get("title") or "(untitled)")[:256],
                "description": statement,
                "function_name": "main",
                "concept_tags": json.dumps([dataset.lower(), topic.lower()]),
                "prerequisite_tags": "[]",
                "starter_code": STARTER_CODE,
                "language": "cpp",
                "language_standard": "cpp17",
                "topic": topic,
                "difficulty": "Easy",
                "input_spec": _spec(row, "input_spec", "input_description"),
                "output_spec": _spec(row, "output_spec", "output_description"),
                "constraints": _spec(row, "constraints") or "",
                "created_by_user_id": None,  # shared dataset problem
            }
            if problem is None:
                problem = Problem(id=_next_bank_id(db), **fields)
                db.add(problem)
                db.flush()  # assign the id before child rows use it
                inserted += 1
            else:
                for key, value in fields.items():
                    setattr(problem, key, value)
                updated += 1
                db.query(TestCase).filter(TestCase.problem_id == problem.id).delete()

            for i, tc in enumerate(row.get("sample_tests") or [], start=1):
                db.add(TestCase(
                    id=f"{problem.id}-{i}",
                    problem_id=problem.id,
                    test_type=TestType.VISIBLE,
                    name=f"Sample {i}",
                    input_json=json.dumps({"stdin": tc.get("input", "")}),
                    expected_output_json=json.dumps(str(tc.get("expected_output", "")).strip()),
                ))

            if prov is None:
                prov = ProblemProvenance(problem_id=problem.id, canonical_id=canonical)
                db.add(prov)
            prov.dataset_source = dataset
            prov.source_problem_id = str(row.get("source_problem_id") or "")
            prov.source_url = row.get("source_url") or ""
            prov.source_license = row.get("source_license") or ""
            prov.license_verified = False
            prov.provenance_ref = row.get("provenance_ref") or ""
            prov.source_sha256 = row.get("source_sha256") or ""
            prov.parser_version = row.get("parser_version") or ""
            prov.ingestion_run_id = row.get("ingestion_run_id") or ""

            tags = {dataset.lower(), topic.lower()}
            for t in row.get("concept_tags") or []:
                tags.add(str(t).strip().lower()[:48])
            db.query(ProblemTag).filter(ProblemTag.problem_id == problem.id).delete()
            for t in sorted(tags):
                if t:
                    db.add(ProblemTag(problem_id=problem.id, tag=t))

            db.query(ProblemQualityCheck).filter(
                ProblemQualityCheck.problem_id == problem.id).delete()
            for code, passed, detail in _quality_checks(row, statement):
                db.add(ProblemQualityCheck(
                    problem_id=problem.id, check_code=code, passed=passed,
                    detail=detail[:512]))

        db.commit()
    finally:
        db.close()
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the TraceLearn problem bank.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Path to the normalized problems JSONL file.")
    parser.add_argument("--all", action="store_true",
                        help="Load every problem, not only student-ready rows.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Load at most this many rows. 0 means no limit.")
    parser.add_argument("--force", action="store_true",
                        help="Update rows that exist from an earlier run.")
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")
    summary = load_bank(args.input, ready_only=not args.all,
                        limit=args.limit, force=args.force)
    print("Bank load complete:", summary)


if __name__ == "__main__":
    main()
