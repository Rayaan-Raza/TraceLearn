from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.db.models import Diagnosis, DiagnosisMode, EvidenceItem, Submission, UncertaintyLevel
from backend.app.diagnosis.confidence import fuse_diagnosis
from backend.app.diagnosis.evidence_contract import HISTORY_AWARE_SOURCES, records_from_items
from backend.app.learner_model.updater import LearnerStateUpdater

class HistoryAwareDiagnosisEngine:
    def __init__(self) -> None:
        self.state_updater = LearnerStateUpdater()

    def diagnose(self, db: Session, submission: Submission) -> Diagnosis:
        # `records_from_items` restores `details`, so the attempt age of each
        # history record reaches the decay in `apply_evidence_weights`.
        items = db.query(EvidenceItem).filter(EvidenceItem.submission_id == submission.id).all()
        records = records_from_items(items, HISTORY_AWARE_SOURCES)
        result = fuse_diagnosis(records)
        diag = Diagnosis(
            submission_id=submission.id,
            mode=DiagnosisMode.HISTORY_AWARE,
            primary_misconception=result["primary"],
            primary_confidence=result["primary_confidence"],
            alternative_misconception=result.get("alternative"),
            alternative_confidence=result.get("alternative_confidence"),
            uncertainty_level=UncertaintyLevel(result["uncertainty"]),
            requires_teacher_review=result["requires_review"],
            explanation_json=json.dumps(result["explanation"]),
        )
        db.add(diag)
        db.commit()
        db.refresh(diag)
        self.state_updater.update_from_diagnosis(db, submission, diag)
        return diag
