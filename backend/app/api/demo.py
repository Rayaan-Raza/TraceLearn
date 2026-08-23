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
