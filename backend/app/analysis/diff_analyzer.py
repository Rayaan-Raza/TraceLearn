from __future__ import annotations
import difflib
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import Submission
from backend.app.learner_model.history import HistoryProvider

class DiffAnalyzer:
    def __init__(self, history: HistoryProvider) -> None:
        self.history = history

    def analyze(self, db: Session, submission: Submission) -> list[EvidenceRecord]:
        prior = self.history.get_prior_same_problem_submission(db, submission)
        if prior is None:
            return [EvidenceRecord(
                source_type="sequence", evidence_code="SEQUENCE_FIRST_ATTEMPT",
                direction="neutral", weight=0.0, description="first attempt on this problem",
            )]
        items: list[EvidenceRecord] = []
        if prior.source_code.strip() != submission.source_code.strip():
            items.append(EvidenceRecord(
                source_type="sequence", evidence_code="SEQUENCE_CODE_CHANGED",
                direction="neutral", weight=0.0, description="code changed from previous attempt",
            ))
            diff = list(difflib.unified_diff(prior.source_code.splitlines(), submission.source_code.splitlines(), lineterm=""))
            if diff:
                items[-1].details = {"diff_lines": len(diff)}
        else:
            items.append(EvidenceRecord(
                source_type="sequence", evidence_code="SEQUENCE_SAME_CODE",
                direction="neutral", weight=0.0, description="same code as previous attempt",
            ))
        return items
