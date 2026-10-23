"""Tests for the canonical problem bank: schema, loader, API and execution."""
import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import inspect

from backend.app.db.database import SessionLocal, engine
from backend.app.db.models import (
    Problem,
    ProblemProvenance,
    ProblemQualityCheck,
    ProblemSolution,
    TestCase,
    TestType,
)
from scripts.load_problem_bank import load_bank
from tests.conftest import make_user

BANK_TABLES = {
    "problem_solutions",
    "problem_tags",
    "problem_hints",
    "problem_provenance",
    "problem_quality_checks",
}


def _fixture_rows() -> list[dict]:
    """Two student-ready rows in the normalized problems.jsonl shape."""
    return [
        {
            "record_type": "problem",
            "problem_id": "tl-test-alpha",
            "source_dataset": "PROJECT_CODENET",
            "source_problem_id": "p90001",
            "title": "Zephyr Sum",
            "statement_text": "Zephyr Sum test problem. " + "Read two integers and print their sum. " * 4,
            "input_spec": "One line with two integers.",
            "output_spec": "One line with the sum.",
            "constraints": "1 <= a, b <= 100",
            "sample_test_count": 2,
            "sample_tests": [
                {"test_index": 1, "input": "1 2\n", "expected_output": "3\n"},
                {"test_index": 2, "input": "10 20\n", "expected_output": "30\n"},
            ],
            "language_scope": "multi-language",
            "statement_format": "html",
            "source_license": None,
            "provenance_ref": "test/p90001.html",
            "source_sha256": "a" * 64,
            "parser_version": "ingest_sources.py/test",
            "ingestion_run_id": "run-test",
            "cpp_submission_count": 12,
            "student_ready": True,
        },
        {
            "record_type": "problem",
            "problem_id": "tl-test-beta",
            "source_dataset": "PROGpedia",
            "source_problem_id": "00099999",
            "title": "Quasar Count",
            "statement_text": "Quasar Count test problem. " + "Count the positive integers in the list. " * 4,
            "input_spec": "A list of integers.",
            "output_spec": "One count.",
            "sample_test_count": 1,
            "sample_tests": [
                {"test_index": 1, "input": "1 -2 3\n", "expected_output": "2\n"},
            ],
            "language_scope": "multi-language",
            "statement_format": "markdown",
            "source_license": None,
            "provenance_ref": "test/00099999/statement.md",
            "source_sha256": "b" * 64,
            "parser_version": "ingest_sources.py/test",
            "ingestion_run_id": "run-test",
            "cpp_submission_count": 0,
            "student_ready": True,
        },
    ]


def _write_fixture(rows: list[dict]) -> Path:
    fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    with fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return Path(fh.name)


@pytest.fixture
def loaded(db):
    """Load the fixture bank rows and return the two created problem ids."""
    summary = load_bank(_write_fixture(_fixture_rows()), force=True)
    assert summary["inserted"] + summary["updated"] == 2
    ids = [
        p.id for p in db.query(Problem)
        .filter(Problem.title.in_(["Zephyr Sum", "Quasar Count"]))
        .all()
    ]
    return ids


def test_bank_tables_exist(db):
    from backend.app.db.database import init_db

    init_db()
    tables = set(inspect(engine).get_table_names())
    assert BANK_TABLES <= tables


def test_loader_is_idempotent(db):
    path = _write_fixture([_fixture_rows()[0]])
    first = load_bank(path)
    second = load_bank(path)
    assert first["inserted"] == 1 and first["skipped"] == 0
    assert second["inserted"] == 0 and second["skipped"] == 1
    problem = db.query(Problem).filter(Problem.title == "Zephyr Sum").one()
    prov = db.get(ProblemProvenance, problem.id)
    assert prov is not None and prov.canonical_id == "tl-test-alpha"
    checks = {
        c.check_code: c.passed
        for c in db.query(ProblemQualityCheck).filter(
            ProblemQualityCheck.problem_id == problem.id
        ).all()
    }
    assert checks["statement_length"] is True
    assert checks["has_input_spec"] is True
    assert checks["license_recorded"] is False
    # Samples become visible test cases with the stdin payload shape.
    tcs = db.query(TestCase).filter(TestCase.problem_id == problem.id).all()
    assert len(tcs) == 2 and all(t.test_type == TestType.VISIBLE for t in tcs)
    assert json.loads(tcs[0].input_json)["stdin"] == "1 2\n"


def test_bank_list_and_search(loaded):
    student, _ = make_user("student")
    r = student.get("/api/bank/problems")
    assert r.status_code == 200
    titles = [p["title"] for p in r.json()]
    assert "Zephyr Sum" in titles and "Quasar Count" in titles
    r = student.get("/api/bank/problems", params={"q": "Quasar"})
    assert [p["title"] for p in r.json()] == ["Quasar Count"]
    r = student.get("/api/bank/problems", params={"q": "NoSuchProblem"})
    assert r.json() == []
    r = student.get("/api/bank/problems", params={"tag": "progpedia"})
    assert [p["title"] for p in r.json()] == ["Quasar Count"]
    r = student.get("/api/bank/tags")
    assert r.status_code == 200
    tags = {t["tag"] for t in r.json()}
    assert "project_codenet" in tags and "progpedia" in tags


def test_bank_detail_hides_hidden_tests(loaded):
    student, _ = make_user("student")
    db = SessionLocal()
    try:
        problem = db.query(Problem).filter(Problem.title == "Zephyr Sum").one()
        db.add(TestCase(
            id=f"{problem.id}-H1", problem_id=problem.id,
            test_type=TestType.HIDDEN, name="secret case",
            input_json=json.dumps({"stdin": "HIDDEN_INPUT_7 8"}),
            expected_output_json=json.dumps("15"),
        ))
        db.commit()
        pid = problem.id
    finally:
        db.close()
    r = student.get(f"/api/bank/problems/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["sample_count"] == 2
    assert body["hidden_count"] == 1
    # The visible sample is returned; the hidden case is not.
    assert any(
        t["input"] == "1 2\n" and t["expected_output"] == "3"
        for t in body["sample_tests"]
    )
    assert "HIDDEN_INPUT_7 8" not in r.text
    assert "secret case" not in r.text
    # Students get no provenance or quality internals.
    assert body["provenance"] is None and body["quality"] == []


def test_bank_detail_teacher_sees_provenance(loaded):
    teacher, _ = make_user("teacher")
    db = SessionLocal()
    try:
        pid = db.query(Problem).filter(Problem.title == "Quasar Count").one().id
    finally:
        db.close()
    r = teacher.get(f"/api/bank/problems/{pid}")
    assert r.status_code == 200
    assert r.json()["provenance"]["source_problem_id"] == "00099999"
    codes = {c["check_code"] for c in r.json()["quality"]}
    assert "license_recorded" in codes


def test_bank_run_redacts_hidden_output(loaded, monkeypatch):
    from backend.app.execution.runner import ExecutionResult
    from backend.app.services import bank_service

    calls = []

    class FakeSession:
        def run(self, stdin_data, timeout_s, memory_mb=None):
            calls.append((stdin_data, timeout_s, memory_mb))
            out = {
                "1 2\n": "3\n",
                "10 20\n": "30\n",
                "HIDDEN_INPUT_7 8": "15\n",
            }.get(stdin_data, "")
            return ExecutionResult(status="success", stdout=out, return_value=out)

        def cleanup(self):
            pass

    monkeypatch.setattr(bank_service, "compile_cpp", lambda src: (FakeSession(), None))

    student, _ = make_user("student")
    db = SessionLocal()
    try:
        problem = db.query(Problem).filter(Problem.title == "Zephyr Sum").one()
        db.add(TestCase(
            id=f"{problem.id}-H1", problem_id=problem.id,
            test_type=TestType.HIDDEN, name="secret case",
            input_json=json.dumps({"stdin": "HIDDEN_INPUT_7 8"}),
            expected_output_json=json.dumps("15"),
            time_limit_ms=1234, memory_limit_mb=128,
        ))
        db.commit()
        pid = problem.id
    finally:
        db.close()

    r = student.post(f"/api/bank/problems/{pid}/run", json={"source_code": "int main(){return 0;}"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_count"] == 3 and body["passed_count"] == 3
    visible = [x for x in body["results"] if x["test_type"] == "visible"]
    hidden = [x for x in body["results"] if x["test_type"] == "hidden"]
    assert all(
        x["actual_output"] is not None and x["expected_output"] is not None for x in visible
    )
    assert all(
        x["actual_output"] is None and x["expected_output"] is None for x in hidden
    )
    assert "HIDDEN_INPUT_7 8" not in r.text
    # Per-test limits reach the runner; other tests use the server default.
    assert (1.234, 128) in [(c[1], c[2]) for c in calls]


def test_bank_run_requires_auth(loaded):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    anon = TestClient(app)
    r = anon.post("/api/bank/problems/P01/run", json={"source_code": "int main(){}"})
    assert r.status_code == 401


def test_bank_run_unknown_problem_404():
    student, _ = make_user("student")
    r = student.post("/api/bank/problems/B999999/run", json={"source_code": "int main(){}"})
    assert r.status_code == 404


def test_bank_solution_verification(loaded, monkeypatch):
    from backend.app.execution.runner import ExecutionResult
    from backend.app.services import bank_service

    class FakeSession:
        def run(self, stdin_data, timeout_s, memory_mb=None):
            out = {"1 2\n": "3\n", "10 20\n": "30\n"}.get(stdin_data, "")
            return ExecutionResult(status="success", stdout=out, return_value=out)

        def cleanup(self):
            pass

    monkeypatch.setattr(bank_service, "compile_cpp", lambda src: (FakeSession(), None))
    teacher, _ = make_user("teacher")
    db = SessionLocal()
    try:
        pid = db.query(Problem).filter(Problem.title == "Zephyr Sum").one().id
    finally:
        db.close()
    r = teacher.post(
        f"/api/bank/problems/{pid}/solutions",
        json={"source_code": "int main(){return 0;}", "license": "MIT"},
    )
    assert r.status_code == 201
    assert r.json()["verification_status"] == "verified"
    db = SessionLocal()
    try:
        sol = db.query(ProblemSolution).filter(ProblemSolution.problem_id == pid).one()
        assert sol.verification_status.value == "verified"
        assert sol.license == "MIT"
    finally:
        db.close()
