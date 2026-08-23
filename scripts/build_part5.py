from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
    print("w", rel)

# Fix confidence.py import issue
w("backend/app/diagnosis/confidence.py", open(ROOT / "backend/app/diagnosis/confidence.py", encoding="utf-8").read().replace(
    "from backend.app.diagnosis.taxonomy import ALL_MISCONCEPTIONS, NO_MISCONCEPTION, UNCERTAIN, UncertaintyLevel",
    "from backend.app.diagnosis.taxonomy import ALL_MISCONCEPTIONS, NO_MISCONCEPTION, UNCERTAIN"
))

w("backend/app/evaluation/metrics.py", '''
from __future__ import annotations
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

def compute_classification_metrics(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict:
    if not y_true:
        return {"accuracy": 0.0, "macro_precision": 0.0, "macro_recall": 0.0, "macro_f1": 0.0, "confusion_matrix": []}
    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
    macro_p = precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    macro_r = recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    macro_f1 = f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    return {
        "accuracy": accuracy,
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "confusion_matrix": cm.tolist(),
        "labels": labels,
    }
''')

w("backend/app/evaluation/comparison.py", '''
from __future__ import annotations
from backend.app.diagnosis.taxonomy import ALL_LABELS
from backend.app.evaluation.metrics import compute_classification_metrics

def compare_modes(current_preds: list[str], history_preds: list[str], labels: list[str]) -> dict:
    changed = sum(1 for a, b in zip(current_preds, history_preds) if a != b)
    return {
        "history_changed_predictions": changed,
        "current_only_metrics": compute_classification_metrics(labels, current_preds, ALL_LABELS),
        "history_aware_metrics": compute_classification_metrics(labels, history_preds, ALL_LABELS),
    }
''')

w("backend/app/evaluation/evaluator.py", '''
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.db.models import Diagnosis, DiagnosisMode, MisconceptionState, Submission
from backend.app.diagnosis.taxonomy import ALL_LABELS
from backend.app.evaluation.comparison import compare_modes
from backend.app.evaluation.labels import GroundTruthRepository
from backend.app.evaluation.metrics import compute_classification_metrics

class ExperimentEvaluator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gt = GroundTruthRepository()

    def collect_predictions(self) -> dict:
        subs = self.db.query(Submission).filter(Submission.is_synthetic == True).order_by(Submission.id).all()  # noqa: E712
        y_true, cur_preds, hist_preds = [], [], []
        state_true, state_pred = [], []
        for s in subs:
            label = s.ground_truth_label or (self.gt.get_misconceptions(s.id)[0] if self.gt.has_label(str(s.id)) else None)
            if not label:
                continue
            cur = self._diag(s.id, DiagnosisMode.CURRENT_ONLY)
            hist = self._diag(s.id, DiagnosisMode.HISTORY_AWARE)
            y_true.append(label)
            cur_preds.append(cur.primary_misconception if cur else "UNCERTAIN")
            hist_preds.append(hist.primary_misconception if hist else "UNCERTAIN")
            if s.ground_truth_state:
                state_true.append(s.ground_truth_state)
                from backend.app.db.models import LearnerState
                ls = self.db.query(LearnerState).filter(LearnerState.student_id == s.student_id).first()
                state_pred.append(ls.state.value if ls else "NEW")
        comparison = compare_modes(cur_preds, hist_preds, y_true)
        history_changed_correctly = sum(
            1 for t, c, h in zip(y_true, cur_preds, hist_preds)
            if c != h and h == t
        )
        false_persistent_current = sum(1 for t, c in zip(y_true, cur_preds) if c != t and "PERSISTENT" in c)
        false_persistent_history = sum(1 for t, h in zip(y_true, hist_preds) if h != t and "PERSISTENT" in h)
        return {
            **comparison,
            "misconception_labels": y_true,
            "current_only_predictions": cur_preds,
            "history_aware_predictions": hist_preds,
            "history_changed_correctly": history_changed_correctly,
            "false_persistent_current_only": false_persistent_current,
            "false_persistent_history_aware": false_persistent_history,
            "persistent_cases_detected_current_only": sum(1 for t, c in zip(y_true, cur_preds) if t != "NO_MISCONCEPTION" and c == t),
            "persistent_cases_detected_history_aware": sum(1 for t, h in zip(y_true, hist_preds) if t != "NO_MISCONCEPTION" and h == t),
            "learner_state_accuracy": (
                sum(1 for a, b in zip(state_true, state_pred) if a == b) / len(state_true) if state_true else None
            ),
            "current_only_metrics": compute_classification_metrics(y_true, cur_preds, ALL_LABELS),
            "history_aware_metrics": compute_classification_metrics(y_true, hist_preds, ALL_LABELS),
        }

    def _diag(self, submission_id: int, mode: DiagnosisMode) -> Diagnosis | None:
        return (
            self.db.query(Diagnosis)
            .filter(Diagnosis.submission_id == submission_id, Diagnosis.mode == mode)
            .order_by(Diagnosis.id.desc())
            .first()
        )
''')

w("backend/app/services/submission_service.py", '''
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
''')

# schemas
w("backend/app/schemas/submissions.py", '''
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class SubmissionCreate(BaseModel):
    student_id: int
    problem_id: str
    source_code: str
    attempt_number: int = 1

class SubmissionRead(BaseModel):
    id: int
    student_id: int
    problem_id: str
    attempt_number: int
    source_code: str
    submitted_at: datetime
    execution_status: str | None = None
    runtime_ms: float | None = None
    model_config = {"from_attributes": True}

class TestResultRead(BaseModel):
    test_case_id: str
    passed: bool
    actual_output_json: Any = None
    expected_output_json: Any = None
    error_type: str | None = None
    runtime_ms: float | None = None

class ExecutionResponse(BaseModel):
    submission_id: int
    execution_status: str
    runtime_ms: float | None = None
    stderr: str = ""
    test_results: list[TestResultRead] = Field(default_factory=list)

class DiagnosisBrief(BaseModel):
    id: int
    mode: str
    primary_misconception: str
    primary_confidence: float
    alternative_misconception: str | None = None
    alternative_confidence: float | None = None
    uncertainty_level: str
    requires_teacher_review: bool
    explanation: dict = Field(default_factory=dict)

class RunAndAnalyzeResponse(BaseModel):
    submission_id: int
    execution_status: str
    runtime_ms: float | None = None
    stderr: str = ""
    test_results: list[TestResultRead] = Field(default_factory=list)
    evidence_count: int = 0
    current_only: DiagnosisBrief | None = None
    history_aware: DiagnosisBrief | None = None
    hint: dict | None = None
''')

w("backend/app/schemas/evidence.py", '''
from pydantic import BaseModel

class EvidenceItemRead(BaseModel):
    id: int
    submission_id: int
    source_type: str
    evidence_code: str
    misconception_id: str | None = None
    direction: str
    weight: float
    description: str
    details_json: str = "{}"
    model_config = {"from_attributes": True}
''')

w("backend/app/schemas/learners.py", '''
from datetime import datetime
from pydantic import BaseModel, Field

class LearnerStateRead(BaseModel):
    id: int
    student_id: int
    misconception_id: str
    state: str
    confidence: float
    updated_at: datetime
    support_count: int = 0
    cross_problem_support_count: int = 0
    recent_success_count: int = 0
    model_config = {"from_attributes": True}

class TimelineEntry(BaseModel):
    submission_id: int
    problem_id: str
    attempt_number: int
    submitted_at: datetime
    execution_status: str | None = None
    primary_diagnosis: str | None = None
    state_transitions: list[dict] = Field(default_factory=list)

class LearnerProfile(BaseModel):
    student_id: int
    display_name: str
    learner_states: list[LearnerStateRead] = Field(default_factory=list)
''')

w("backend/app/schemas/teachers.py", '''
from datetime import datetime
from pydantic import BaseModel

class TeacherReviewCreate(BaseModel):
    action: str
    corrected_misconception: str | None = None
    comment: str | None = None

class TeacherReviewRead(BaseModel):
    id: int
    submission_id: int
    diagnosis_id: int | None
    action: str
    corrected_misconception: str | None = None
    comment: str | None = None
    reviewed_at: datetime
    model_config = {"from_attributes": True}
''')

print("part5 done")
