from __future__ import annotations
import json
import yaml
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db.models import Diagnosis, EvidenceItem, LearnerState, LearnerStateHistory, MisconceptionState, Submission
from backend.app.diagnosis.taxonomy import SCORED_MISCONCEPTIONS, NO_MISCONCEPTION, UNCERTAIN
from backend.app.learner_model.history import HistoryProvider
from backend.app.learner_model.states import can_become_persistent

class LearnerStateUpdater:
    def __init__(self) -> None:
        self.history = HistoryProvider()

    def _min_cross(self) -> int:
        raw = yaml.safe_load(Path(settings.evidence_weights_path).read_text(encoding="utf-8"))
        return raw.get("learner_state", {}).get("min_cross_problem_for_persistent", 2)

    def update_from_diagnosis(self, db: Session, submission: Submission, diagnosis: Diagnosis) -> LearnerState | None:
        mid = diagnosis.primary_misconception
        if mid in (NO_MISCONCEPTION, UNCERTAIN):
            return None
        if mid not in SCORED_MISCONCEPTIONS:
            return None
        existing = (
            db.query(LearnerState)
            .filter(LearnerState.student_id == submission.student_id, LearnerState.misconception_id == mid)
            .first()
        )
        support = db.query(EvidenceItem).filter(
            EvidenceItem.submission_id == submission.id,
            EvidenceItem.misconception_id == mid,
            EvidenceItem.direction == "support",
        ).count()
        cross = self.history.count_cross_problem_support(db, submission, mid)
        recent_success = self.history.count_recent_related_successes(db, submission)
        old_state = existing.state if existing else MisconceptionState.NEW
        old_conf = existing.confidence if existing else 0.0
        new_conf = diagnosis.primary_confidence
        new_state = self._compute_state(existing, diagnosis, cross, recent_success, support)
        if existing:
            existing.state = new_state
            existing.confidence = new_conf
            existing.trigger_submission_id = submission.id
            existing.support_count += support
            existing.cross_problem_support_count = cross
            existing.recent_success_count = recent_success
            row = existing
        else:
            row = LearnerState(
                student_id=submission.student_id,
                misconception_id=mid,
                state=new_state,
                confidence=new_conf,
                trigger_submission_id=submission.id,
                support_count=support,
                cross_problem_support_count=cross,
                recent_success_count=recent_success,
            )
            db.add(row)
        if new_state != old_state or abs(new_conf - old_conf) > 0.01:
            db.add(LearnerStateHistory(
                student_id=submission.student_id,
                misconception_id=mid,
                old_state=old_state,
                new_state=new_state,
                old_confidence=old_conf,
                new_confidence=new_conf,
                submission_id=submission.id,
                reason_json=json.dumps({
                    "cross_problem_support": cross,
                    "recent_successes": recent_success,
                    "support_count": support,
                    "diagnosis_confidence": new_conf,
                }),
            ))
        db.commit()
        return row

    def _compute_state(self, existing, diagnosis, cross, recent_success, support) -> MisconceptionState:
        if diagnosis.requires_teacher_review:
            return MisconceptionState.REQUIRES_TEACHER_REVIEW
        if existing and existing.state == MisconceptionState.RESOLVED and diagnosis.primary_confidence >= 0.45:
            return MisconceptionState.RECURRED
        if existing and existing.state == MisconceptionState.PERSISTENT and recent_success >= 1 and diagnosis.primary_confidence < 0.5:
            return MisconceptionState.IMPROVING
        if existing and existing.state == MisconceptionState.PERSISTENT and recent_success >= 2 and diagnosis.primary_confidence < 0.25:
            return MisconceptionState.RESOLVED
        if can_become_persistent(cross, self._min_cross()):
            return MisconceptionState.PERSISTENT
        return MisconceptionState.NEW
