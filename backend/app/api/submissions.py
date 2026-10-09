from typing import Annotated
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from backend.app.auth.access import get_own_submission, get_problem_for, get_submission_for
from backend.app.auth.dependencies import get_current_user, require_student
from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import (
    Diagnosis,
    DiagnosisMode,
    EvidenceItem,
    HintEvent,
    Submission,
    TeacherReview,
    TestCase,
    TestResult,
    TestType,
    User,
    UserRole,
)
from backend.app.diagnosis.taxonomy import NO_MISCONCEPTION, UNCERTAIN
from backend.app.hints.templates import GENERIC_HINT, HINTS
from backend.app.schemas.evidence import EvidenceItemRead
from backend.app.schemas.submissions import (
    DiagnosisBrief,
    ExecutionResponse,
    HintRead,
    RunAndAnalyzeResponse,
    SubmissionCreate,
    SubmissionRead,
    TestResultRead,
)
from backend.app.schemas.teachers import TeacherReviewRead
from backend.app.security.rate_limit import limiter
from backend.app.services.submission_service import SubmissionService

router = APIRouter(prefix="/submissions", tags=["submissions"])
service = SubmissionService()

SubmissionId = Annotated[int, Path(ge=1, le=2**31 - 1)]


def _rate_limit_execution(user: User) -> None:
    limiter.hit(f"exec:{user.id}", settings.executions_per_minute, 60)


def _redact_tests(db: Session, user: User, rows: list[dict]) -> list[TestResultRead]:
    """Students never see inputs/outputs of hidden or diagnostic tests."""
    ids = [r["test_case_id"] for r in rows]
    cases = {tc.id: tc for tc in db.query(TestCase).filter(TestCase.id.in_(ids)).all()} if ids else {}
    out = []
    for r in rows:
        tc = cases.get(r["test_case_id"])
        test_type = tc.test_type.value if tc else None
        item = TestResultRead(
            test_case_id=r["test_case_id"],
            passed=r["passed"],
            test_type=test_type,
            name=tc.name if tc else None,
            actual_output_json=r.get("actual_output_json", r.get("actual_output")),
            expected_output_json=r.get("expected_output_json", r.get("expected_output")),
            error_type=r.get("error_type"),
            runtime_ms=r.get("runtime_ms"),
        )
        if user.role == UserRole.STUDENT and (tc is None or tc.test_type != TestType.VISIBLE):
            item.actual_output_json = None
            item.expected_output_json = None
            item.name = None
        out.append(item)
    return out


def _execution_failed(result: dict) -> None:
    if result.get("execution_status") == "system_error" and "sandbox" in (result.get("stderr") or "").lower():
        raise HTTPException(status_code=503, detail=result.get("stderr"))


@router.post("", response_model=SubmissionRead, status_code=status.HTTP_200_OK)
def create_submission(
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_student),
) -> Submission:
    if payload.student_id is not None and payload.student_id != user.student_id:
        raise HTTPException(status_code=403, detail="You can only submit as yourself")
    limiter.hit(f"submit:{user.id}", settings.executions_per_minute * 2, 60)
    get_problem_for(db, user, payload.problem_id)  # 404 if not visible to this student
    # attempt_number=0 -> computed server-side from prior attempts.
    return service.create_submission(db, user.student_id, payload.problem_id, payload.source_code, 0)


@router.get("/{submission_id}", response_model=SubmissionRead)
def get_submission(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Submission:
    return get_submission_for(db, user, submission_id)


@router.post("/{submission_id}/execute", response_model=ExecutionResponse)
def execute_submission(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(require_student)) -> ExecutionResponse:
    sub = get_own_submission(db, user, submission_id)
    _rate_limit_execution(user)
    result = service.execute(db, sub.id)
    _execution_failed(result)
    tests = _redact_tests(db, user, result.pop("test_results", []))
    return ExecutionResponse(**result, test_results=tests)


@router.post("/{submission_id}/analyze")
def analyze_submission(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(require_student)) -> dict:
    sub = get_own_submission(db, user, submission_id)
    _rate_limit_execution(user)
    return service.analyze(db, sub.id)


@router.post("/{submission_id}/diagnose")
def diagnose_submission(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(require_student)) -> dict:
    sub = get_own_submission(db, user, submission_id)
    _rate_limit_execution(user)
    return service.diagnose(db, sub.id)


@router.post("/{submission_id}/run-and-analyze", response_model=RunAndAnalyzeResponse)
def run_and_analyze(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(require_student)) -> RunAndAnalyzeResponse:
    sub = get_own_submission(db, user, submission_id)
    _rate_limit_execution(user)
    result = service.run_and_analyze(db, sub.id)
    _execution_failed(result)
    return RunAndAnalyzeResponse(
        submission_id=result["submission_id"],
        execution_status=result["execution_status"],
        runtime_ms=result.get("runtime_ms"),
        stderr=(result.get("stderr") or "")[:8192],
        test_results=_redact_tests(db, user, result.get("test_results", [])),
        evidence_count=result.get("evidence_count", 0),
        current_only=DiagnosisBrief(**result["current_only"]) if result.get("current_only") else None,
        history_aware=DiagnosisBrief(**result["history_aware"]) if result.get("history_aware") else None,
        hint=result.get("hint"),
    )


@router.get("/{submission_id}/evidence", response_model=list[EvidenceItemRead])
def get_evidence(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[EvidenceItem]:
    sub = get_submission_for(db, user, submission_id)
    return db.query(EvidenceItem).filter(EvidenceItem.submission_id == sub.id).all()


@router.get("/{submission_id}/diagnoses", response_model=list[DiagnosisBrief])
def get_diagnoses(
    submission_id: SubmissionId,
    mode: Literal["current_only", "history_aware"] | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DiagnosisBrief]:
    sub = get_submission_for(db, user, submission_id)
    q = db.query(Diagnosis).filter(Diagnosis.submission_id == sub.id)
    if mode:
        q = q.filter(Diagnosis.mode == DiagnosisMode(mode))
    return [
        DiagnosisBrief(
            id=d.id, mode=d.mode.value, primary_misconception=d.primary_misconception,
            primary_confidence=d.primary_confidence, alternative_misconception=d.alternative_misconception,
            alternative_confidence=d.alternative_confidence, uncertainty_level=d.uncertainty_level.value,
            requires_teacher_review=d.requires_teacher_review,
            explanation=json.loads(d.explanation_json or "{}"),
        )
        for d in q.order_by(Diagnosis.id).all()
    ]


@router.get("/{submission_id}/test-results", response_model=list[TestResultRead])
def get_test_results(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[TestResultRead]:
    sub = get_submission_for(db, user, submission_id)
    rows = db.query(TestResult).filter(TestResult.submission_id == sub.id).order_by(TestResult.id).all()
    raw = [
        {
            "test_case_id": r.test_case_id, "passed": r.passed, "error_type": r.error_type,
            "runtime_ms": r.runtime_ms,
            "actual_output_json": json.loads(r.actual_output_json or "null"),
            "expected_output_json": json.loads(r.expected_output_json or "null"),
        }
        for r in rows
    ]
    return _redact_tests(db, user, raw)


@router.get("/{submission_id}/reviews", response_model=list[TeacherReviewRead])
def get_reviews(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[TeacherReview]:
    sub = get_submission_for(db, user, submission_id)
    return db.query(TeacherReview).filter(TeacherReview.submission_id == sub.id).order_by(TeacherReview.id).all()


def _hint_target(db: Session, sub: Submission) -> tuple[str, dict[int, str]]:
    diag = (
        db.query(Diagnosis)
        .filter(Diagnosis.submission_id == sub.id, Diagnosis.mode == DiagnosisMode.HISTORY_AWARE)
        .order_by(Diagnosis.id.desc())
        .first()
    )
    mid = diag.primary_misconception if diag else UNCERTAIN
    if diag is None or mid in (NO_MISCONCEPTION, UNCERTAIN) or diag.requires_teacher_review or mid not in HINTS:
        return "GENERIC", {1: GENERIC_HINT}
    return mid, HINTS[mid]


@router.get("/{submission_id}/hints", response_model=list[HintRead])
def list_hints(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[HintRead]:
    sub = get_submission_for(db, user, submission_id)
    _, levels = _hint_target(db, sub)
    events = db.query(HintEvent).filter(HintEvent.submission_id == sub.id).order_by(HintEvent.hint_level, HintEvent.id).all()
    seen: dict[int, HintEvent] = {}
    for e in events:
        seen.setdefault(e.hint_level, e)
    return [
        HintRead(level=e.hint_level, max_level=max(levels), text=e.hint_text, misconception_id=e.misconception_id)
        for e in seen.values()
    ]


@router.post("/{submission_id}/next-hint", response_model=HintRead)
def next_hint(submission_id: SubmissionId, db: Session = Depends(get_db), user: User = Depends(require_student)) -> HintRead:
    """Reveal the next template hint level (recorded as a hint event)."""
    sub = get_own_submission(db, user, submission_id)
    mid, levels = _hint_target(db, sub)
    max_level = max(levels)
    current = max((e.hint_level for e in db.query(HintEvent).filter(HintEvent.submission_id == sub.id).all()), default=0)
    level = min(current + 1, max_level)
    text = levels.get(level, GENERIC_HINT)
    if level > current:
        db.add(HintEvent(student_id=sub.student_id, submission_id=sub.id, misconception_id=mid, hint_level=level, hint_text=text))
        db.commit()
    return HintRead(level=level, max_level=max_level, text=text, misconception_id=mid)
