from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.pipeline import AnalysisPipeline
from backend.app.db.models import DiagnosisMode, Student, Submission
from backend.app.diagnosis.current_only import CurrentOnlyDiagnosisEngine
from backend.app.diagnosis.history_aware import HistoryAwareDiagnosisEngine
from backend.app.execution.test_runner import run_submission_tests
from backend.app.hints.hint_policy import HintPolicy

class SubmissionService:
    def __init__(self) -> None:
        self.hint_policy = HintPolicy()
        self.current_engine = CurrentOnlyDiagnosisEngine()
        self.history_engine = HistoryAwareDiagnosisEngine()

    def create_submission(self, db: Session, student_id: int, problem_id: str, source_code: str, attempt_number: int = 1, is_synthetic: bool = False, ground_truth_label: str | None = None, ground_truth_state: str | None = None) -> Submission:
        prior_count = db.query(Submission).filter(Submission.student_id == student_id, Submission.problem_id == problem_id).count()
        sub = Submission(
            student_id=student_id,
            problem_id=problem_id,
            attempt_number=attempt_number or prior_count + 1,
            source_code=source_code,
            is_synthetic=is_synthetic,
            ground_truth_label=ground_truth_label,
            ground_truth_state=ground_truth_state,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return sub

    def execute(self, db: Session, submission_id: int) -> dict:
        sub = db.get(Submission, submission_id)
        if not sub:
            raise ValueError("Submission not found")
        result = run_submission_tests(db, sub)
        return {
            "submission_id": submission_id,
            "execution_status": result.execution_status,
            "runtime_ms": result.runtime_ms,
            "stderr": result.stderr,
            "test_results": [tr.__dict__ for tr in result.test_results],
        }

    def analyze(self, db: Session, submission_id: int) -> dict:
        sub = db.get(Submission, submission_id)
        if not sub:
            raise ValueError("Submission not found")
        pipeline = AnalysisPipeline()
        items = pipeline.analyze_submission(db, sub, include_history=True)
        return {"submission_id": submission_id, "evidence_count": len(items)}

    def diagnose(self, db: Session, submission_id: int) -> dict:
        sub = db.get(Submission, submission_id)
        if not sub:
            raise ValueError("Submission not found")
        current = self.current_engine.diagnose(db, sub)
        history = self.history_engine.diagnose(db, sub)
        hint = self.hint_policy.select_hint(db, sub, history)
        return {
            "submission_id": submission_id,
            "current_only": self._diag_dict(current),
            "history_aware": self._diag_dict(history),
            "hint": {"level": hint.hint_level, "text": hint.hint_text} if hint else None,
        }

    def run_and_analyze(self, db: Session, submission_id: int) -> dict:
        exec_result = self.execute(db, submission_id)
        analyze_result = self.analyze(db, submission_id)
        diag_result = self.diagnose(db, submission_id)
        return {**exec_result, **analyze_result, **diag_result}

    def _diag_dict(self, d) -> dict:
        return {
            "id": d.id,
            "mode": d.mode.value,
            "primary_misconception": d.primary_misconception,
            "primary_confidence": d.primary_confidence,
            "alternative_misconception": d.alternative_misconception,
            "alternative_confidence": d.alternative_confidence,
            "uncertainty_level": d.uncertainty_level.value,
            "requires_teacher_review": d.requires_teacher_review,
            "explanation": json.loads(d.explanation_json or "{}"),
        }

    def get_student_by_name(self, db: Session, display_name: str) -> Student | None:
        return db.query(Student).filter(Student.display_name == display_name).first()
