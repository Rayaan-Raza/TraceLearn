from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import Diagnosis, DiagnosisMode, EvidenceItem, Submission, UncertaintyLevel
from backend.app.diagnosis.confidence import fuse_diagnosis
from backend.app.diagnosis.evidence_contract import CURRENT_ONLY_SOURCES, records_from_items

class CurrentOnlyDiagnosisEngine:
    """Diagnosis using ONLY observed evidence of the current submission.

    No `sequence` and no `history` evidence: see `evidence_contract`.
    """

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
        # Mode A reads observed evidence of this attempt only. The allow-list
        # also removes `sequence` evidence (an earlier attempt on the same
        # problem), not just `history`. `history_allowed` is kept for the
        # contract test and is never honoured here.
        items = db.query(EvidenceItem).filter(
            EvidenceItem.submission_id == submission_id,
            EvidenceItem.source_type.in_(list(CURRENT_ONLY_SOURCES)),
        ).all()
        return records_from_items(items, CURRENT_ONLY_SOURCES)
