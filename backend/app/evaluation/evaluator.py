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
                state_pred.append(self._stored_state_after(s, label))
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

    def _stored_state_after(self, submission: Submission, label: str | None) -> str:
        """The learner state the system had stored right after this submission.

        Read from the append-only `learner_state_history`, so each labelled
        attempt is scored against the state at that point in the sequence,
        not against the final state of the student. When the label names a
        misconception, that misconception's state is used; otherwise the most
        recent transition of the student up to this submission.
        """
        from backend.app.db.models import LearnerStateHistory
        q = self.db.query(LearnerStateHistory).filter(
            LearnerStateHistory.student_id == submission.student_id,
            LearnerStateHistory.submission_id != None,  # noqa: E711
            LearnerStateHistory.submission_id <= submission.id,
        )
        if label and label not in ("NO_MISCONCEPTION", "UNCERTAIN"):
            q = q.filter(LearnerStateHistory.misconception_id == label)
        row = q.order_by(LearnerStateHistory.submission_id.desc(), LearnerStateHistory.id.desc()).first()
        return row.new_state.value if row else MisconceptionState.NEW.value

    def _diag(self, submission_id: int, mode: DiagnosisMode) -> Diagnosis | None:
        return (
            self.db.query(Diagnosis)
            .filter(Diagnosis.submission_id == submission_id, Diagnosis.mode == mode)
            .order_by(Diagnosis.id.desc())
            .first()
        )
