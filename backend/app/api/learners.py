import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import Diagnosis, DiagnosisMode, LearnerState, LearnerStateHistory, Student, Submission
from backend.app.schemas.learners import LearnerProfile, LearnerStateRead, TimelineEntry

router = APIRouter(prefix="/students", tags=["learners"])

@router.get("/{student_id}/timeline", response_model=list[TimelineEntry])
def get_timeline(student_id: int, db: Session = Depends(get_db)) -> list[TimelineEntry]:
    if not db.get(Student, student_id):
        raise HTTPException(404, "Student not found")
    subs = db.query(Submission).filter(Submission.student_id == student_id).order_by(Submission.submitted_at, Submission.id).all()
    entries = []
    for s in subs:
        diag = db.query(Diagnosis).filter(Diagnosis.submission_id == s.id, Diagnosis.mode == DiagnosisMode.HISTORY_AWARE).order_by(Diagnosis.id.desc()).first()
        transitions = [
            {"misconception_id": h.misconception_id, "old_state": h.old_state.value, "new_state": h.new_state.value, "timestamp": h.timestamp.isoformat()}
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
def get_profile(student_id: int, db: Session = Depends(get_db)) -> LearnerProfile:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    states = db.query(LearnerState).filter(LearnerState.student_id == student_id).all()
    return LearnerProfile(
        student_id=student_id,
        display_name=student.display_name,
        learner_states=[LearnerStateRead.model_validate(s) for s in states],
    )
