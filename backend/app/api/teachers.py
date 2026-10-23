from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from backend.app.auth.access import get_diagnosis_for_teacher
from backend.app.auth.dependencies import require_teacher
from backend.app.db.database import get_db
from backend.app.db.models import TeacherReview, TeacherReviewAction, User
from backend.app.schemas.teachers import TeacherReviewCreate, TeacherReviewRead

router = APIRouter(prefix="/diagnoses", tags=["teachers"])


@router.post("/{diagnosis_id}/teacher-review", response_model=TeacherReviewRead)
def teacher_review(
    payload: TeacherReviewCreate,
    diagnosis_id: int = Path(ge=1, le=2**31 - 1),
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> TeacherReview:
    diag = get_diagnosis_for_teacher(db, teacher, diagnosis_id)
    # The system diagnosis row is never modified; the review is stored alongside it.
    review = TeacherReview(
        submission_id=diag.submission_id,
        diagnosis_id=diag.id,
        action=TeacherReviewAction(payload.action),
        corrected_misconception=payload.corrected_misconception,
        comment=payload.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
