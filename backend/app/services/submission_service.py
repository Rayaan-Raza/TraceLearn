from __future__ import annotations
import json
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.analysis.model_features import InferenceFeatureBuilder
from backend.app.analysis.model_evidence import model_evidence
from backend.app.analysis.pipeline import AnalysisPipeline
from backend.app.config import settings
from backend.app.db.models import DiagnosisMode, EvidenceDirection, EvidenceItem, EvidenceSourceType, Student, Submission
from backend.app.diagnosis.current_only import CurrentOnlyDiagnosisEngine
from backend.app.diagnosis.history_aware import HistoryAwareDiagnosisEngine
from backend.app.diagnosis.xgb_classifier import ModelClassifier, ModelContractError, ModelPrediction
from backend.app.execution.runner import SubmissionExecutionResult
from backend.app.execution.test_runner import run_submission_tests
from backend.app.hints.hint_policy import HintPolicy

_COMPILE_FAIL_STATUSES = {"syntax_error", "compile_error"}
_PASS_STATUSES = {"passed", "all_passed"}


def _should_skip_model(exec_res: SubmissionExecutionResult) -> bool:
    status = exec_res.execution_status
    if status in _COMPILE_FAIL_STATUSES:
        return True
    results = exec_res.test_results
    if results and all(r.passed for r in results):
        return True
    if results and all(r.error_type == "Timeout" for r in results if not r.passed):
        non_timeout_fail = any(not r.passed and r.error_type != "Timeout" for r in results)
        if not non_timeout_fail:
            return True
    return False


class SubmissionService:
    def __init__(self) -> None:
        self.hint_policy = HintPolicy()
        self.current_engine = CurrentOnlyDiagnosisEngine()
        self.history_engine = HistoryAwareDiagnosisEngine()
        self._classifier: ModelClassifier | None = None
        self._feature_builder = InferenceFeatureBuilder()

    def _get_classifier(self) -> ModelClassifier | None:
        if settings.model_diagnosis == "off":
            return None
        if self._classifier is None:
            try:
                self._classifier = ModelClassifier.load(settings.model_variant, settings.model_dir)
            except (ModelContractError, FileNotFoundError, OSError):
                return None
        return self._classifier

    def _run_model(self, db: Session, sub: Submission, exec_res: SubmissionExecutionResult) -> ModelPrediction | None:
        clf = self._get_classifier()
        if clf is None:
            return None
        try:
            features = self._feature_builder.build(
                source=sub.source_code,
                compile_stderr=exec_res.stderr or "",
                test_results=exec_res.test_results or [],
            )
            prediction = clf.predict(features)
        except Exception:
            return None
        if settings.model_diagnosis == "on":
            rec = model_evidence(prediction)
            item = EvidenceItem(
                submission_id=sub.id,
                source_type=EvidenceSourceType.MODEL,
                evidence_code=rec.evidence_code,
                misconception_id=rec.misconception_id,
                direction=EvidenceDirection(rec.direction),
                weight=rec.weight,
                description=rec.description,
                details_json=json.dumps(rec.details),
            )
            db.add(item)
            db.commit()
        return prediction

    def create_submission(self, db: Session, student_id: int, problem_id: str, source_code: str, attempt_number: int = 0, is_synthetic: bool = False, ground_truth_label: str | None = None, ground_truth_state: str | None = None) -> Submission:
        # The unique (student, problem, attempt) constraint rejects a number
        # that a concurrent request took first; then read the new maximum.
        for _ in range(5):
            if attempt_number:
                number = attempt_number
            else:
                last = (
                    db.query(func.max(Submission.attempt_number))
                    .filter(Submission.student_id == student_id, Submission.problem_id == problem_id)
                    .scalar()
                )
                number = (last or 0) + 1
            sub = Submission(
                student_id=student_id,
                problem_id=problem_id,
                attempt_number=number,
                source_code=source_code,
                is_synthetic=is_synthetic,
                ground_truth_label=ground_truth_label,
                ground_truth_state=ground_truth_state,
            )
            db.add(sub)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                if attempt_number:
                    raise
                continue
            db.refresh(sub)
            return sub
        raise RuntimeError("Could not allocate an attempt number")

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
        sub = db.get(Submission, submission_id)
        if not sub:
            raise ValueError("Submission not found")

        exec_res = run_submission_tests(db, sub)

        pipeline = AnalysisPipeline()
        items = pipeline.analyze_submission(db, sub, include_history=True)

        prediction: ModelPrediction | None = None
        if settings.model_diagnosis != "off" and not _should_skip_model(exec_res):
            prediction = self._run_model(db, sub, exec_res)

        current = self.current_engine.diagnose(db, sub)
        history = self.history_engine.diagnose(db, sub)
        hint = self.hint_policy.select_hint(db, sub, history)

        return {
            "submission_id": submission_id,
            "execution_status": exec_res.execution_status,
            "runtime_ms": exec_res.runtime_ms,
            "stderr": exec_res.stderr,
            "test_results": [tr.__dict__ for tr in exec_res.test_results],
            "evidence_count": len(items),
            "current_only": self._diag_dict(current),
            "history_aware": self._diag_dict(history),
            "hint": {"level": hint.hint_level, "text": hint.hint_text} if hint else None,
            "model_prediction": prediction.as_dict() if prediction else None,
        }

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
