from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.db.models import EvidenceItem, LearnerState, LearnerStateHistory, Problem, Submission, TestResult

class HistoryProvider:
    """Strict temporal causality: only data strictly before current submission."""

    def get_prior_submissions(self, db: Session, current: Submission) -> list[Submission]:
        q = (
            db.query(Submission)
            .filter(Submission.student_id == current.student_id)
            .filter(Submission.id < current.id)
            .order_by(Submission.submitted_at.asc(), Submission.id.asc())
        )
        if current.submitted_at:
            q = q.filter(Submission.submitted_at <= current.submitted_at)
        return q.all()

    def get_prior_same_problem_submission(self, db: Session, current: Submission) -> Submission | None:
        return (
            db.query(Submission)
            .filter(
                Submission.student_id == current.student_id,
                Submission.problem_id == current.problem_id,
                Submission.id < current.id,
            )
            .order_by(Submission.id.desc())
            .first()
        )

    def get_state_history_before(self, db: Session, student_id: int, as_of: datetime, submission_id: int) -> list[LearnerStateHistory]:
        return (
            db.query(LearnerStateHistory)
            .filter(
                LearnerStateHistory.student_id == student_id,
                LearnerStateHistory.timestamp <= as_of,
            )
            .filter(
                (LearnerStateHistory.submission_id == None) | (LearnerStateHistory.submission_id < submission_id)  # noqa: E711
            )
            .order_by(LearnerStateHistory.timestamp.asc())
            .all()
        )

    def get_learner_state(self, db: Session, student_id: int, misconception_id: str, current: Submission) -> LearnerState | None:
        prior_ids = [s.id for s in self.get_prior_submissions(db, current)]
        if not prior_ids:
            return None
        return (
            db.query(LearnerState)
            .filter(LearnerState.student_id == student_id, LearnerState.misconception_id == misconception_id)
            .first()
        )

    def count_recent_related_successes(self, db: Session, current: Submission, limit: int = 3) -> int:
        problem = db.get(Problem, current.problem_id)
        if not problem:
            return 0
        tags = json.loads(problem.concept_tags or "[]")
        related_ids = [p.id for p in db.query(Problem).all() if set(json.loads(p.concept_tags or "[]")) & set(tags)]
        count = 0
        for ps in reversed(self.get_prior_submissions(db, current)):
            if ps.problem_id not in related_ids:
                continue
            results = db.query(TestResult).filter(TestResult.submission_id == ps.id).all()
            if results and all(r.passed for r in results):
                count += 1
            if count >= limit:
                break
        return count

    def count_cross_problem_support(self, db: Session, current: Submission, misconception_id: str) -> int:
        problems: set[str] = set()
        for ps in self.get_prior_submissions(db, current):
            if ps.problem_id == current.problem_id:
                continue
            evs = db.query(EvidenceItem).filter(
                EvidenceItem.submission_id == ps.id,
                EvidenceItem.misconception_id == misconception_id,
                EvidenceItem.direction == "support",
            ).count()
            if evs:
                problems.add(ps.problem_id)
        cur_evs = db.query(EvidenceItem).filter(
            EvidenceItem.submission_id == current.id,
            EvidenceItem.misconception_id == misconception_id,
            EvidenceItem.direction == "support",
        ).count()
        if cur_evs and problems:
            problems.add(current.problem_id)
        return len(problems)
