"""Synthetic research demo: reset and replay SYN* sequences.

Used by the CLI scripts directly and by /api/demo/* (teacher-only, and only
when ENABLE_DEMO_ENDPOINTS=true).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.db.models import (
    Diagnosis,
    EvidenceItem,
    HintEvent,
    LearnerState,
    LearnerStateHistory,
    Student,
    Submission,
    TeacherReview,
    TestResult,
)
from backend.app.db.seed import run_seed
from backend.app.services.submission_service import SubmissionService

DEMO_DIR = Path("data/demo_sequences")
SEQUENCE_NAME = re.compile(r"^SYN\d{3}$")
SYNTHETIC_NAMES = ("SYN001", "SYN002", "SYN003", "SYN004", "SYN005")

_service = SubmissionService()


def available_sequences() -> list[str]:
    return sorted(p.stem for p in DEMO_DIR.glob("SYN*.json") if SEQUENCE_NAME.match(p.stem))


def reset_synthetic(db: Session) -> dict:
    """Delete all data belonging to synthetic students. Real users are untouched."""
    run_seed(db)
    syn_ids = [s.id for s in db.query(Student).filter(Student.is_synthetic.is_(True)).all()]
    if syn_ids:
        sub_ids = [s.id for s in db.query(Submission.id).filter(Submission.student_id.in_(syn_ids)).all()]
        if sub_ids:
            for model in (TeacherReview, HintEvent, EvidenceItem, TestResult):
                db.query(model).filter(model.submission_id.in_(sub_ids)).delete(synchronize_session=False)
            db.query(Diagnosis).filter(Diagnosis.submission_id.in_(sub_ids)).delete(synchronize_session=False)
        db.query(LearnerStateHistory).filter(LearnerStateHistory.student_id.in_(syn_ids)).delete(synchronize_session=False)
        db.query(LearnerState).filter(LearnerState.student_id.in_(syn_ids)).delete(synchronize_session=False)
        db.query(HintEvent).filter(HintEvent.student_id.in_(syn_ids)).delete(synchronize_session=False)
        db.query(Submission).filter(Submission.student_id.in_(syn_ids)).delete(synchronize_session=False)
    for name in SYNTHETIC_NAMES:
        if not db.query(Student).filter(Student.display_name == name, Student.is_synthetic.is_(True)).first():
            db.add(Student(display_name=name, is_synthetic=True))
    db.commit()
    return {"status": "reset_complete"}


class SequenceAlreadyRun(Exception):
    """The synthetic student already has attempts; reset the demo first."""


def run_sequence(db: Session, name: str) -> dict:
    if not SEQUENCE_NAME.match(name):
        raise ValueError("Invalid sequence name")
    seq_path = DEMO_DIR / f"{name}.json"
    if not seq_path.is_file():
        raise FileNotFoundError(name)
    student = db.query(Student).filter(Student.display_name == name, Student.is_synthetic.is_(True)).first()
    if not student:
        student = Student(display_name=name, is_synthetic=True)
        db.add(student)
        db.commit()
        db.refresh(student)
    if db.query(Submission.id).filter(Submission.student_id == student.id).first():
        # A second replay would log the same attempt numbers again.
        raise SequenceAlreadyRun(name)
    payload = json.loads(seq_path.read_text(encoding="utf-8"))
    base = DEMO_DIR.resolve()
    results = []
    for attempt in payload.get("attempts", []):
        code_path = (DEMO_DIR / attempt["source_file"]).resolve()
        if base not in code_path.parents:
            raise ValueError("Sequence references a file outside the demo directory")
        code = code_path.read_text(encoding="utf-8")
        sub = _service.create_submission(
            db, student.id, attempt["problem_id"], code,
            attempt_number=attempt.get("attempt_number", 1),
            is_synthetic=True,
            ground_truth_label=attempt.get("ground_truth_misconception"),
            ground_truth_state=attempt.get("ground_truth_state"),
        )
        r = _service.run_and_analyze(db, sub.id)
        results.append({"submission_id": sub.id, "problem_id": attempt["problem_id"], **r})
    return {"student_id": name, "attempts_processed": len(results), "results": results}
