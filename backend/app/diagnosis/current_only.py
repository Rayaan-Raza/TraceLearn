from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import Diagnosis, DiagnosisMode, EvidenceItem, EvidenceSourceType, Submission, UncertaintyLevel
from backend.app.diagnosis.confidence import fuse_diagnosis

class CurrentOnlyDiagnosisEngine:
    """Diagnosis using ONLY current submission evidence — no history access."""

    def diagnose(self, db: Session, submission: Submission) -> Diagnosis:
        records = self._records_from_db(db, submission.id, history_allowed=False)
        result = fuse_diagnosis(records)
        diag = Diagnosis(
            submission_id=submission.id,
            mode=DiagnosisMode.CURRENT_ONLY,
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
        return diag

    def _records_from_db(self, db: Session, submission_id: int, history_allowed: bool) -> list[EvidenceRecord]:
        q = db.query(EvidenceItem).filter(EvidenceItem.submission_id == submission_id)
        if not history_allowed:
            q = q.filter(EvidenceItem.source_type != EvidenceSourceType.HISTORY)
        records = []
        for item in q.all():
            if item.source_type == EvidenceSourceType.HISTORY:
                continue
            records.append(EvidenceRecord(
                source_type=item.source_type.value,
                evidence_code=item.evidence_code,
                misconception_id=item.misconception_id,
                direction=item.direction.value,
                weight=item.weight,
                description=item.description,
            ))
        return records
