"""Problem bank API.

These endpoints serve the shared dataset problem bank. The bank is the set of
`problems` rows with `created_by_user_id IS NULL`. All endpoints require
sign-in. The strict rule for every response: public code never returns the
input, the expected output, or the name of a hidden or diagnostic test case,
and it never returns a reference solution.
"""
from typing import Annotated
import json

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user, require_student, require_teacher
from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import (
    Problem,
    ProblemProvenance,
    ProblemQualityCheck,
    ProblemSolution,
    ProblemTag,
    TestCase,
    TestType,
    User,
    UserRole,
    VerificationStatus,
)
from backend.app.schemas.bank import (
    BankProblemDetail,
    BankProblemSummary,
    BankProvenancePublic,
    BankQualityCheckPublic,
    BankRunRequest,
    BankRunResponse,
    BankSolutionCreate,
    BankTagCount,
)
from backend.app.security.rate_limit import limiter
from backend.app.services import bank_service
from backend.app.services.bank_service import BankRunError

router = APIRouter(prefix="/bank", tags=["bank"])

ProblemId = Annotated[str, Path(min_length=1, max_length=8, pattern=r"^[A-Za-z0-9_-]+$")]
SearchQuery = Annotated[str, Query(min_length=1, max_length=100)]


def _bank_query(db: Session):
    """Shared dataset problems only. Teacher custom problems are not in the bank."""
    return db.query(Problem).filter(Problem.created_by_user_id.is_(None))


def _tags_for(db: Session, problem_ids: list[str]) -> dict[str, list[str]]:
    if not problem_ids:
        return {}
    rows = db.query(ProblemTag).filter(ProblemTag.problem_id.in_(problem_ids)).all()
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r.problem_id, []).append(r.tag)
    return out


def _hidden_count(db: Session, problem_id: str) -> int:
    return (
        db.query(TestCase)
        .filter(
            TestCase.problem_id == problem_id,
            TestCase.test_type != TestType.VISIBLE,
        )
        .count()
    )


def _summary(db: Session, p: Problem, tags: dict[str, list[str]]) -> BankProblemSummary:
    return BankProblemSummary(
        id=p.id,
        title=p.title,
        topic=p.topic or "General",
        difficulty=p.difficulty or "Easy",
        language=p.language or "cpp",
        tags=tags.get(p.id, []),
        dataset_source=(p.provenance.dataset_source if p.provenance else ""),
        sample_count=sum(1 for tc in p.test_cases if tc.test_type == TestType.VISIBLE),
        hidden_count=sum(1 for tc in p.test_cases if tc.test_type != TestType.VISIBLE),
    )


@router.get("/problems", response_model=list[BankProblemSummary])
def list_bank_problems(
    q: SearchQuery | None = None,
    tag: str | None = Query(default=None, max_length=48),
    difficulty: str | None = Query(default=None, max_length=16),
    language: str | None = Query(default=None, max_length=16),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BankProblemSummary]:
    query = _bank_query(db)
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(Problem.title.like(pattern), Problem.description.like(pattern)))
    if difficulty:
        query = query.filter(Problem.difficulty == difficulty)
    if language:
        query = query.filter(Problem.language == language)
    if tag:
        query = query.join(ProblemTag, ProblemTag.problem_id == Problem.id).filter(
            ProblemTag.tag == tag.lower()
        )
    problems = query.order_by(Problem.id).offset(offset).limit(limit).all()
    tags = _tags_for(db, [p.id for p in problems])
    return [_summary(db, p, tags) for p in problems]


@router.get("/tags", response_model=list[BankTagCount])
def list_bank_tags(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BankTagCount]:
    rows = (
        db.query(ProblemTag.tag)
        .join(Problem, Problem.id == ProblemTag.problem_id)
        .filter(Problem.created_by_user_id.is_(None))
        .all()
    )
    counts: dict[str, int] = {}
    for (tag,) in rows:
        counts[tag] = counts.get(tag, 0) + 1
    return [BankTagCount(tag=t, problem_count=c) for t, c in sorted(counts.items())]


@router.get("/problems/{problem_id}", response_model=BankProblemDetail)
def get_bank_problem(
    problem_id: ProblemId,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BankProblemDetail:
    problem = _bank_query(db).filter(Problem.id == problem_id).first()
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")

    # Public sample tests only. Hidden and diagnostic cases are counted but
    # their input, expected output and name stay on the server.
    samples = []
    for i, tc in enumerate(
        sorted(problem.test_cases, key=lambda t: t.id), start=1
    ):
        if tc.test_type != TestType.VISIBLE:
            continue
        samples.append(
            {
                "index": i,
                "test_type": tc.test_type.value,
                "input": (json.loads(tc.input_json or "{}") or {}).get("stdin"),
                "expected_output": json.loads(tc.expected_output_json or "null"),
                "time_limit_ms": tc.time_limit_ms,
                "memory_limit_mb": tc.memory_limit_mb,
            }
        )

    detail = BankProblemDetail(
        id=problem.id,
        title=problem.title,
        topic=problem.topic or "General",
        difficulty=problem.difficulty or "Easy",
        language=problem.language or "cpp",
        tags=[t.tag for t in problem.tags],
        dataset_source=(problem.provenance.dataset_source if problem.provenance else ""),
        sample_count=len(samples),
        hidden_count=_hidden_count(db, problem.id),
        description=problem.description,
        input_spec=problem.input_spec or "",
        output_spec=problem.output_spec or "",
        constraints=problem.constraints or "",
        starter_code=problem.starter_code or "",
        language_standard=problem.language_standard or "cpp17",
        sample_tests=samples,
    )

    if user.role == UserRole.TEACHER:
        prov = db.get(ProblemProvenance, problem.id)
        if prov is not None:
            detail.provenance = BankProvenancePublic(
                dataset_source=prov.dataset_source,
                source_problem_id=prov.source_problem_id,
                source_url=prov.source_url,
                source_license=prov.source_license,
                license_verified=prov.license_verified,
                provenance_ref=prov.provenance_ref,
            )
        detail.quality = [
            BankQualityCheckPublic(
                check_code=c.check_code, passed=c.passed, detail=c.detail
            )
            for c in db.query(ProblemQualityCheck)
            .filter(ProblemQualityCheck.problem_id == problem.id)
            .order_by(ProblemQualityCheck.check_code)
            .all()
        ]
    return detail


@router.post("/problems/{problem_id}/run", response_model=BankRunResponse)
def run_bank_problem(
    problem_id: ProblemId,
    payload: BankRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_student),
) -> BankRunResponse:
    """Compile and run student code against every bank test case.

    The run uses the execution queue. CPU, memory and wall-clock limits come
    from the test case first and from the server settings second. The response
    never holds the input or the expected output of a hidden test case.
    """
    limiter.hit(f"exec:{user.id}", settings.executions_per_minute, 60)
    problem = _bank_query(db).filter(Problem.id == problem_id).first()
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")
    cases = (
        db.query(TestCase)
        .filter(TestCase.problem_id == problem.id)
        .order_by(TestCase.id)
        .all()
    )
    if not cases:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Problem has no test cases")
    try:
        result = bank_service.run_bank_problem(problem.id, payload.source_code, cases)
    except BankRunError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if result["execution_status"] == "system_error":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result.get("stderr"))
    return BankRunResponse(**result)


@router.post("/problems/{problem_id}/solutions", status_code=status.HTTP_201_CREATED)
def attach_bank_solution(
    problem_id: ProblemId,
    payload: BankSolutionCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> dict:
    """Attach a reference solution and verify it against the public tests.

    Only a teacher can call this endpoint. The verification runs the solution
    in the sandbox. The response holds the verification status and the pass
    counts. It never holds the solution itself.
    """
    problem = _bank_query(db).filter(Problem.id == problem_id).first()
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")
    cases = (
        db.query(TestCase)
        .filter(TestCase.problem_id == problem.id, TestCase.test_type == TestType.VISIBLE)
        .order_by(TestCase.id)
        .all()
    )
    try:
        result = bank_service.run_bank_problem(problem.id, payload.source_code, cases)
    except BankRunError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if result["execution_status"] == "system_error":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result.get("stderr"))

    verified = result["total_count"] > 0 and result["passed_count"] == result["total_count"]
    solution = (
        db.query(ProblemSolution)
        .filter(ProblemSolution.problem_id == problem.id, ProblemSolution.language == "cpp")
        .one_or_none()
    )
    if solution is None:
        solution = ProblemSolution(problem_id=problem.id, language="cpp")
        db.add(solution)
    solution.source_code = payload.source_code
    solution.language_standard = problem.language_standard or "cpp17"
    solution.license = payload.license
    if verified:
        solution.verification_status = VerificationStatus.VERIFIED
        solution.verification_detail = (
            f"passed {result['passed_count']}/{result['total_count']} public tests"
        )
    else:
        solution.verification_status = VerificationStatus.FAILED
        solution.verification_detail = (
            f"passed {result['passed_count']}/{result['total_count']} public tests"
        )
    db.commit()
    return {
        "problem_id": problem.id,
        "verification_status": solution.verification_status.value,
        "detail": solution.verification_detail,
    }
