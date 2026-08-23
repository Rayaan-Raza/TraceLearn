from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.database import SessionLocal, init_db
from backend.app.db.models import Problem, Student, TestCase as TestCaseModel
from backend.app.db.seed import SEED_EXPECTED_COUNTS, run_seed
from backend.app.schemas.diagnosis import DiagnosisContext


@pytest.fixture(scope="module")
def seeded_db() -> None:
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()


@pytest.fixture(scope="module")
def client(seeded_db: None) -> TestClient:
    from backend.app.main import app

    return TestClient(app)


def test_seed_counts(seeded_db: None) -> None:
    db = SessionLocal()
    try:
        assert db.query(Problem).count() == SEED_EXPECTED_COUNTS["problems"]
        assert db.query(TestCaseModel).count() == SEED_EXPECTED_COUNTS["test_cases"]
        assert db.query(Student).count() == SEED_EXPECTED_COUNTS["students"]
    finally:
        db.close()


def test_list_problems_returns_six(client: TestClient) -> None:
    response = client.get("/api/problems")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6
    ids = {row["id"] for row in data}
    assert ids == {f"P0{i}" for i in range(1, 7)}


def test_get_problem_detail(client: TestClient) -> None:
    response = client.get("/api/problems/P01")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "P01"
    assert body["function_name"] == "sum_first_n"
    assert any(tc["test_type"] == "visible" for tc in body["test_cases"])
    visible = next(tc for tc in body["test_cases"] if tc["test_type"] == "visible")
    assert visible["input_json"] == {"args": [5]}


def test_ground_truth_not_accessible_to_diagnosis() -> None:
    fields = set(DiagnosisContext.model_fields.keys())
    forbidden = {
        "ground_truth",
        "misconception_ids",
        "label",
        "labels",
        "expected_misconception",
        "true_misconception",
    }
    assert forbidden.isdisjoint(fields)

    diagnosis_module = importlib.import_module("backend.app.schemas.diagnosis")
    source_path = Path(diagnosis_module.__file__)
    text = source_path.read_text(encoding="utf-8")
    assert "evaluation.labels" not in text
    assert "ground_truth" not in text.lower()

    labels = importlib.import_module("backend.app.evaluation.labels")
    assert hasattr(labels, "GroundTruthRepository")
    repo_path = Path(labels.__file__)
    assert repo_path.name == "labels.py"


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}