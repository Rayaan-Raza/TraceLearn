from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import Diagnosis, TeacherReview, TeacherReviewAction
from backend.app.schemas.teachers import TeacherReviewCreate, TeacherReviewRead

router = APIRouter(prefix="/diagnoses", tags=["teachers"])

@router.post("/{diagnosis_id}/teacher-review", response_model=TeacherReviewRead)
def teacher_review(diagnosis_id: int, payload: TeacherReviewCreate, db: Session = Depends(get_db)) -> TeacherReview:
    diag = db.get(Diagnosis, diagnosis_id)
    if not diag:
        raise HTTPException(404, "Diagnosis not found")
    try:
        action = TeacherReviewAction(payload.action)
    except ValueError:
        raise HTTPException(400, "Invalid action")
    review = TeacherReview(
        submission_id=diag.submission_id,
        diagnosis_id=diag.id,
        action=action,
        corrected_misconception=payload.corrected_misconception,
        comment=payload.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
