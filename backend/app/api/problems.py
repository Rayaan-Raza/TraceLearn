import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import Problem, TestCase, TestType
from backend.app.schemas.problems import ProblemDetail, ProblemSummary, TestCasePublic

router = APIRouter(prefix="/problems", tags=["problems"])


def _json_list(raw: str) -> list[str]:
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except json.JSONDecodeError:
        return []


def _json_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@router.get("", response_model=list[ProblemSummary])
def list_problems(db: Session = Depends(get_db)) -> list[ProblemSummary]:
    rows = db.query(Problem).order_by(Problem.id).all()
    return [
        ProblemSummary(
            id=p.id,
            title=p.title,
            function_name=p.function_name,
            concept_tags=_json_list(p.concept_tags),
        )
        for p in rows
    ]


@router.get("/{problem_id}", response_model=ProblemDetail)
def get_problem(problem_id: str, db: Session = Depends(get_db)) -> ProblemDetail:
    problem = db.get(Problem, problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    cases = (
        db.query(TestCase)
        .filter(TestCase.problem_id == problem_id)
        .order_by(TestCase.id)
        .all()
    )
    public_cases: list[TestCasePublic] = []
    for tc in cases:
        input_json: Any | None = _json_value(tc.input_json)
        if tc.test_type != TestType.VISIBLE:
            input_json = None
        public_cases.append(
            TestCasePublic(
                id=tc.id,
                name=tc.name,
                test_type=tc.test_type.value,
                input_json=input_json,
            )
        )

    return ProblemDetail(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        function_name=problem.function_name,
        concept_tags=_json_list(problem.concept_tags),
        description=problem.description,
        prerequisite_tags=_json_list(problem.prerequisite_tags),
        starter_code=problem.starter_code,
        test_cases=public_cases,
    )