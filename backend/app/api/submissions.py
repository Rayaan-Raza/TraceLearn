import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import Diagnosis, EvidenceItem, Submission, TestResult
from backend.app.schemas.evidence import EvidenceItemRead
from backend.app.schemas.submissions import (
    DiagnosisBrief, ExecutionResponse, RunAndAnalyzeResponse, SubmissionCreate, SubmissionRead, TestResultRead,
)
from backend.app.services.submission_service import SubmissionService

router = APIRouter(prefix="/submissions", tags=["submissions"])
service = SubmissionService()

@router.post("", response_model=SubmissionRead)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db)) -> Submission:
    return service.create_submission(db, payload.student_id, payload.problem_id, payload.source_code, payload.attempt_number)

@router.get("/{submission_id}", response_model=SubmissionRead)
def get_submission(submission_id: int, db: Session = Depends(get_db)) -> Submission:
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(404, "Submission not found")
    return sub

@router.post("/{submission_id}/execute", response_model=ExecutionResponse)
def execute_submission(submission_id: int, db: Session = Depends(get_db)) -> ExecutionResponse:
    try:
        result = service.execute(db, submission_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return ExecutionResponse(**result)

@router.post("/{submission_id}/analyze")
def analyze_submission(submission_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return service.analyze(db, submission_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{submission_id}/diagnose")
def diagnose_submission(submission_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return service.diagnose(db, submission_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{submission_id}/run-and-analyze", response_model=RunAndAnalyzeResponse)
def run_and_analyze(submission_id: int, db: Session = Depends(get_db)) -> RunAndAnalyzeResponse:
    try:
        result = service.run_and_analyze(db, submission_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return RunAndAnalyzeResponse(
        submission_id=result["submission_id"],
        execution_status=result["execution_status"],
        runtime_ms=result.get("runtime_ms"),
        stderr=result.get("stderr", ""),
        test_results=[TestResultRead(**tr) for tr in result.get("test_results", [])],
        evidence_count=result.get("evidence_count", 0),
        current_only=DiagnosisBrief(**result["current_only"]) if result.get("current_only") else None,
        history_aware=DiagnosisBrief(**result["history_aware"]) if result.get("history_aware") else None,
        hint=result.get("hint"),
    )

@router.get("/{submission_id}/evidence", response_model=list[EvidenceItemRead])
def get_evidence(submission_id: int, db: Session = Depends(get_db)) -> list[EvidenceItem]:
    if not db.get(Submission, submission_id):
        raise HTTPException(404, "Submission not found")
    return db.query(EvidenceItem).filter(EvidenceItem.submission_id == submission_id).all()

@router.get("/{submission_id}/diagnoses", response_model=list[DiagnosisBrief])
def get_diagnoses(submission_id: int, mode: str | None = None, db: Session = Depends(get_db)) -> list[DiagnosisBrief]:
    if not db.get(Submission, submission_id):
        raise HTTPException(404, "Submission not found")
    q = db.query(Diagnosis).filter(Diagnosis.submission_id == submission_id)
    if mode:
        q = q.filter(Diagnosis.mode == mode)
    rows = q.all()
    out = []
    for d in rows:
        out.append(DiagnosisBrief(
            id=d.id, mode=d.mode.value, primary_misconception=d.primary_misconception,
            primary_confidence=d.primary_confidence, alternative_misconception=d.alternative_misconception,
            alternative_confidence=d.alternative_confidence, uncertainty_level=d.uncertainty_level.value,
            requires_teacher_review=d.requires_teacher_review,
            explanation=json.loads(d.explanation_json or "{}"),
        ))
    return out

@router.get("/{submission_id}/test-results")
def get_test_results(submission_id: int, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(TestResult).filter(TestResult.submission_id == submission_id).all()
    return [{"test_case_id": r.test_case_id, "passed": r.passed, "error_type": r.error_type} for r in rows]
