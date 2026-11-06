from __future__ import annotations
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import Submission
from backend.app.learner_model.history import HistoryProvider


class HistoryAnalyzer:
    """Build `history` evidence for the current submission.

    Rules (see `diagnosis/evidence_contract.py`):

    1. Only earlier submissions are read (`HistoryProvider`). The current
       attempt contributes nothing here; its own evidence comes from the
       observed analyzers.
    2. Only **observed** support on earlier attempts counts. History records
       stored on earlier attempts are not read back as new observations.
    3. Every record carries `details["age"]`, the attempt distance from the
       most recent earlier attempt it rests on (0 = the attempt just before
       the current one). `apply_evidence_weights` decays the weight by
       `decay_factor ** age`.
    4. Recurrence and recovery are per misconception. A success counts for a
       misconception only on a problem whose diagnostic tests probe it, and
       only after the latest observed support for it.
    """

    def __init__(self, history: HistoryProvider) -> None:
        self.history = history

    def analyze(self, db: Session, submission: Submission) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        support = self.history.observed_support_by_misconception(db, submission)
        for mid, events in support.items():
            other = [e for e in events if e.problem_id != submission.problem_id]
            if other:
                latest = other[-1]
                problems = sorted({e.problem_id for e in other})
                details = {
                    "problems": problems,
                    "source_submission_ids": [e.submission_id for e in other],
                    "latest_submission_id": latest.submission_id,
                    "age": latest.age,
                }
                items.append(EvidenceRecord(
                    source_type="history", evidence_code=f"PREVIOUS_RELATED_{mid[:3]}",
                    misconception_id=mid, direction="support", weight=0.0,
                    description=f"same {mid} evidence on related problem(s): {problems}",
                    details=dict(details),
                ))
                # Recurrence needs another problem. Earlier attempts on the
                # same problem are sequence evidence, not cross-problem
                # recurrence (learner-state rule 2).
                items.append(EvidenceRecord(
                    source_type="history", evidence_code="CROSS_PROBLEM_RECURRENCE",
                    misconception_id=mid, direction="support", weight=0.0,
                    description=f"cross-problem recurrence for {mid} ({len(problems)} earlier problem(s), age {latest.age})",
                    details=dict(details),
                ))
            successes = self.history.related_successes_since_support(db, submission, mid, include_current=False)
            if successes.count:
                items.append(EvidenceRecord(
                    source_type="history", evidence_code="RELATED_SUCCESS_AFTER_MISCONCEPTION",
                    misconception_id=mid, direction="conflict", weight=0.0,
                    description=f"{successes.count} related success(es) for {mid} since its last evidence",
                    details={
                        "count": successes.count,
                        "problems": sorted(successes.problems),
                        "source_submission_ids": successes.submission_ids,
                        "age": successes.latest_age or 0,
                    },
                ))
        ids = [p.id for p in self.history.get_prior_submissions(db, submission)]
        for mid, row in self.history.get_prior_states(db, submission).items():
            age = len(ids) - 1 - ids.index(row.submission_id) if row.submission_id in ids else 0
            items.append(EvidenceRecord(
                source_type="history", evidence_code="PREVIOUS_LEARNER_STATE",
                misconception_id=mid, direction="neutral", weight=0.0,
                description=f"prior state {row.new_state.value} for {mid}",
                details={"state": row.new_state.value, "confidence": row.new_confidence,
                         "source_submission_id": row.submission_id, "age": age},
            ))
        return items
