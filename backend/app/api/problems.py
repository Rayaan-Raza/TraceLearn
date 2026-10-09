from typing import Annotated
import json
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.auth.access import get_problem_for
from backend.app.auth.dependencies import get_current_user, require_teacher
from backend.app.db.database import get_db
from backend.app.db.models import (
    Assignment,
    AssignmentStudent,
    Problem,
    TestCase,
    TestType,
    User,
    UserRole,
)
from backend.app.schemas.problems import ProblemCreate, ProblemDetail, ProblemSummary, TestCasePublic

router = APIRouter(prefix="/problems", tags=["problems"])

ProblemId = Annotated[str, Path(min_length=1, max_length=8, pattern=r"^[A-Za-z0-9_-]+$")]


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


def _summary(p: Problem) -> ProblemSummary:
    return ProblemSummary(
        id=p.id,
        title=p.title,
        function_name=p.function_name,
        concept_tags=_json_list(p.concept_tags),
        language=p.language or "python",
        topic=p.topic or "",
        difficulty=p.difficulty or "Easy",
        source="dataset" if p.created_by_user_id is None else "custom",
    )


def _detail(db: Session, problem: Problem) -> ProblemDetail:
    cases = db.query(TestCase).filter(TestCase.problem_id == problem.id).order_by(TestCase.id).all()
    public_cases: list[TestCasePublic] = []
    for tc in cases:
        visible = tc.test_type == TestType.VISIBLE
        public_cases.append(
            TestCasePublic(
                id=tc.id,
                name=tc.name,
                test_type=tc.test_type.value,
                input_json=_json_value(tc.input_json) if visible else None,
                expected_output=_json_value(tc.expected_output_json) if visible else None,
            )
        )
    s = _summary(problem)
    return ProblemDetail(
        **s.model_dump(),
        slug=problem.slug,
        description=problem.description,
        prerequisite_tags=_json_list(problem.prerequisite_tags),
        starter_code=problem.starter_code,
        test_cases=public_cases,
    )


@router.get("", response_model=list[ProblemSummary])
def list_problems(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ProblemSummary]:
    q = db.query(Problem)
    if user.role == UserRole.TEACHER:
        q = q.filter(or_(Problem.created_by_user_id.is_(None), Problem.created_by_user_id == user.id))
    else:
        assigned = (
            db.query(Assignment.problem_id)
            .join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id)
            .filter(AssignmentStudent.student_id == user.student_id)
        )
        q = q.filter(or_(Problem.created_by_user_id.is_(None), Problem.id.in_(assigned)))
    return [_summary(p) for p in q.order_by(Problem.id).all()]


@router.get("/{problem_id}", response_model=ProblemDetail)
def get_problem(problem_id: ProblemId, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ProblemDetail:
    return _detail(db, get_problem_for(db, user, problem_id))


@router.post("", response_model=ProblemDetail, status_code=status.HTTP_201_CREATED)
def create_problem(payload: ProblemCreate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> ProblemDetail:
    # Ids are random so custom problems cannot be enumerated or guessed.
    for _ in range(10):
        pid = "C" + secrets.token_hex(3)  # 7 chars, fits String(8)
        if db.get(Problem, pid) is None:
            break
    starter = payload.starter_code or "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
    problem = Problem(
        id=pid,
        slug=pid.lower(),
        title=payload.title,
        description=payload.description,
        function_name="main",
        concept_tags=json.dumps(payload.concept_tags or [payload.topic.lower()]),
        prerequisite_tags="[]",
        starter_code=starter,
        language="cpp",
        topic=payload.topic,
        difficulty=payload.difficulty,
        created_by_user_id=teacher.id,
    )
    db.add(problem)
    for i, tc in enumerate(payload.test_cases, start=1):
        stdin = tc.input if tc.input.endswith("\n") or not tc.input else tc.input + "\n"
        db.add(TestCase(
            id=f"{pid}-{i}",
            problem_id=pid,
            test_type=TestType.VISIBLE if tc.visible else TestType.HIDDEN,
            name=f"Case {i}",
            input_json=json.dumps({"stdin": stdin}),
            expected_output_json=json.dumps(tc.expected.strip()),
        ))
    db.commit()
    db.refresh(problem)
    return _detail(db, problem)
