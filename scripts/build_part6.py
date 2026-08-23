from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
    print("w", rel)

w("backend/app/api/submissions.py", '''
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
''')

w("backend/app/api/students.py", '''
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import Student
from pydantic import BaseModel

router = APIRouter(prefix="/students", tags=["students"])

class StudentRead(BaseModel):
    id: int
    display_name: str
    is_synthetic: bool
    model_config = {"from_attributes": True}

@router.get("", response_model=list[StudentRead])
def list_students(db: Session = Depends(get_db)) -> list[Student]:
    return db.query(Student).order_by(Student.id).all()
''')

w("backend/app/api/learners.py", '''
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
''')

w("backend/app/api/teachers.py", '''
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
''')

w("backend/app/api/evaluation.py", '''
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.evaluation.evaluator import ExperimentEvaluator

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

@router.get("/comparison")
def evaluation_comparison(db: Session = Depends(get_db)) -> dict:
    return ExperimentEvaluator(db).collect_predictions()
''')

w("backend/app/api/demo.py", '''
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.database import get_db, init_db
from backend.app.db.models import Student, Submission
from backend.app.db.seed import run_seed
from backend.app.services.submission_service import SubmissionService

router = APIRouter(prefix="/demo", tags=["demo"])
service = SubmissionService()
DEMO_DIR = Path("data/demo_sequences")

@router.post("/reset")
def reset_demo(db: Session = Depends(get_db)) -> dict:
    from backend.app.db.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    init_db()
    run_seed(db)
    for name in ("SYN001", "SYN002", "SYN003", "SYN004", "SYN005"):
        if not db.query(Student).filter(Student.display_name == name).first():
            db.add(Student(display_name=name, is_synthetic=True))
    db.commit()
    return {"status": "reset_complete"}

@router.post("/run-sequence/{student_id}")
def run_sequence(student_id: str, db: Session = Depends(get_db)) -> dict:
    seq_path = DEMO_DIR / f"{student_id}.json"
    if not seq_path.is_file():
        raise HTTPException(404, f"Sequence {student_id} not found")
    student = db.query(Student).filter(Student.display_name == student_id).first()
    if not student:
        student = Student(display_name=student_id, is_synthetic=True)
        db.add(student)
        db.commit()
        db.refresh(student)
    payload = json.loads(seq_path.read_text(encoding="utf-8"))
    results = []
    for attempt in payload.get("attempts", []):
        code_path = DEMO_DIR / attempt["source_file"]
        code = code_path.read_text(encoding="utf-8")
        sub = service.create_submission(
            db, student.id, attempt["problem_id"], code,
            attempt_number=attempt.get("attempt_number", 1),
            is_synthetic=True,
            ground_truth_label=attempt.get("ground_truth_misconception"),
            ground_truth_state=attempt.get("ground_truth_state"),
        )
        r = service.run_and_analyze(db, sub.id)
        results.append({"submission_id": sub.id, "problem_id": attempt["problem_id"], **r})
    return {"student_id": student_id, "attempts_processed": len(results), "results": results}
''')

w("backend/app/main.py", '''
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.demo import router as demo_router
from backend.app.api.evaluation import router as evaluation_router
from backend.app.api.learners import router as learners_router
from backend.app.api.problems import router as problems_router
from backend.app.api.students import router as students_router
from backend.app.api.submissions import router as submissions_router
from backend.app.api.teachers import router as teachers_router
from backend.app.config import settings
from backend.app.db.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="TraceLearn POC", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(problems_router, prefix="/api")
app.include_router(students_router, prefix="/api")
app.include_router(submissions_router, prefix="/api")
app.include_router(learners_router, prefix="/api")
app.include_router(teachers_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")
app.include_router(demo_router, prefix="/api")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
''')

# init files
for pkg in ["execution", "analysis", "diagnosis", "learner_model", "hints", "evaluation", "services", "api"]:
    w(f"backend/app/{pkg}/__init__.py", "")

print("part6 api done")
