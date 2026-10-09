from typing import Annotated
from fastapi import APIRouter, Depends, Path
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.app.auth.access import get_student_for
from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.db.models import (
    Diagnosis,
    DiagnosisMode,
    LearnerState,
    LearnerStateHistory,
    Problem,
    Submission,
    TestResult,
    User,
)
from backend.app.schemas.learners import LearnerProfile, LearnerStateRead, TimelineEntry
from backend.app.schemas.submissions import SubmissionSummary

router = APIRouter(prefix="/students", tags=["learners"])

StudentId = Annotated[int, Path(ge=1, le=2**31 - 1)]


def _latest_history_diag(db: Session, submission_id: int) -> Diagnosis | None:
    return (
        db.query(Diagnosis)
        .filter(Diagnosis.submission_id == submission_id, Diagnosis.mode == DiagnosisMode.HISTORY_AWARE)
        .order_by(Diagnosis.id.desc())
        .first()
    )


def summarize_submissions(db: Session, subs: list[Submission]) -> list[SubmissionSummary]:
    if not subs:
        return []
    ids = [s.id for s in subs]
    titles = {p.id: p.title for p in db.query(Problem).filter(Problem.id.in_({s.problem_id for s in subs})).all()}
    counts: dict[int, tuple[int, int]] = {}
    for sid, total, passed in (
        db.query(TestResult.submission_id, func.count(TestResult.id), func.sum(case((TestResult.passed.is_(True), 1), else_=0)))
        .filter(TestResult.submission_id.in_(ids))
        .group_by(TestResult.submission_id)
        .all()
    ):
        counts[sid] = (int(total or 0), int(passed or 0))
    out = []
    for s in subs:
        total, passed = counts.get(s.id, (0, 0))
        diag = _latest_history_diag(db, s.id)
        out.append(SubmissionSummary(
            id=s.id, student_id=s.student_id, problem_id=s.problem_id,
            problem_title=titles.get(s.problem_id, s.problem_id), attempt_number=s.attempt_number,
            submitted_at=s.submitted_at,
            execution_status=s.execution_status.value if s.execution_status else None,
            passed=total > 0 and passed == total, tests_passed=passed, tests_total=total,
            primary_misconception=diag.primary_misconception if diag else None,
            primary_confidence=diag.primary_confidence if diag else None,
            requires_teacher_review=bool(diag.requires_teacher_review) if diag else False,
        ))
    return out


@router.get("/{student_id}/submissions", response_model=list[SubmissionSummary])
def list_student_submissions(student_id: StudentId, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[SubmissionSummary]:
    student = get_student_for(db, user, student_id)
    subs = (
        db.query(Submission)
        .filter(Submission.student_id == student.id)
        .order_by(Submission.submitted_at.desc(), Submission.id.desc())
        .limit(500)
        .all()
    )
    return summarize_submissions(db, subs)


@router.get("/{student_id}/timeline", response_model=list[TimelineEntry])
def get_timeline(student_id: StudentId, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[TimelineEntry]:
    student = get_student_for(db, user, student_id)
    subs = db.query(Submission).filter(Submission.student_id == student.id).order_by(Submission.submitted_at, Submission.id).all()
    entries = []
    for s in subs:
        diag = _latest_history_diag(db, s.id)
        transitions = [
            {
                "misconception_id": h.misconception_id, "old_state": h.old_state.value, "new_state": h.new_state.value,
                "old_confidence": h.old_confidence, "new_confidence": h.new_confidence,
                "timestamp": h.timestamp.isoformat(),
            }
            for h in db.query(LearnerStateHistory).filter(LearnerStateHistory.submission_id == s.id).all()
        ]
        entries.append(TimelineEntry(
            submission_id=s.id, problem_id=s.problem_id, attempt_number=s.attempt_number,
            submitted_at=s.submitted_at,
            execution_status=s.execution_status.value if s.execution_status else None,
            primary_diagnosis=diag.primary_misconception if diag else None,
            state_transitions=transitions,
        ))
    return entries


@router.get("/{student_id}/learner-profile", response_model=LearnerProfile)
def get_profile(student_id: StudentId, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> LearnerProfile:
    student = get_student_for(db, user, student_id)
    states = db.query(LearnerState).filter(LearnerState.student_id == student.id).all()
    return LearnerProfile(
        student_id=student.id,
        display_name=student.display_name,
        is_synthetic=student.is_synthetic,
        learner_states=[LearnerStateRead.model_validate(s) for s in states],
    )
