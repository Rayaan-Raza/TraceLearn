from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import EvidenceItem, Submission
from backend.app.diagnosis.taxonomy import M01_LOOP_BOUNDARY, M02_INDEX_VALUE, M03_MISSING_RETURN
from backend.app.learner_model.history import HistoryProvider

class HistoryAnalyzer:
    def __init__(self, history: HistoryProvider) -> None:
        self.history = history

    def analyze(self, db: Session, submission: Submission) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        prior_subs = self.history.get_prior_submissions(db, submission)
        misconception_problems: dict[str, set[str]] = {}
        for ps in prior_subs:
            evs = db.query(EvidenceItem).filter(
                EvidenceItem.submission_id == ps.id,
                EvidenceItem.direction == "support",
            ).all()
            for ev in evs:
                if ev.misconception_id:
                    misconception_problems.setdefault(ev.misconception_id, set()).add(ps.problem_id)
        for mid, problems in misconception_problems.items():
            if submission.problem_id not in problems and len(problems) >= 1:
                items.append(EvidenceRecord(
                    source_type="history", evidence_code=f"PREVIOUS_RELATED_{mid[:3]}",
                    misconception_id=mid, direction="support", weight=0.0,
                    description=f"same {mid} evidence on related problem(s): {sorted(problems)}",
                    details={"problems": sorted(problems)},
                ))
            if len(problems) >= 1:
                items.append(EvidenceRecord(
                    source_type="history", evidence_code="CROSS_PROBLEM_RECURRENCE",
                    misconception_id=mid, direction="support", weight=0.0,
                    description=f"cross-problem recurrence for {mid}",
                ))
        related_success = self.history.count_recent_related_successes(db, submission)
        if related_success:
            items.append(EvidenceRecord(
                source_type="history", evidence_code="RELATED_SUCCESS_AFTER_MISCONCEPTION",
                direction="conflict", weight=0.0,
                description=f"{related_success} recent related success(es)",
                details={"count": related_success},
            ))
        state = self.history.get_learner_state(db, submission.student_id, M01_LOOP_BOUNDARY, submission)
        if state:
            items.append(EvidenceRecord(
                source_type="history", evidence_code="PREVIOUS_LEARNER_STATE",
                misconception_id=state.misconception_id, direction="neutral", weight=0.0,
                description=f"prior state {state.state.value} for {state.misconception_id}",
            ))
        return items
