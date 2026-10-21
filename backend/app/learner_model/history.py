from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.db.models import (
    EvidenceDirection, EvidenceItem, LearnerState, LearnerStateHistory, Problem, Submission, TestCase,
    TestResult, TestType,
)
from backend.app.diagnosis.cpp_mapping import code_for_diagnostic_tag
from backend.app.diagnosis.evidence_contract import OBSERVED_SOURCES


@dataclass
class SupportEvent:
    """Observed support for one misconception on one earlier submission."""
    submission_id: int
    problem_id: str
    age: int  # attempt distance to the current submission; 0 = the attempt just before it


@dataclass
class RelatedSuccessSummary:
    """Fully passing attempts on problems that probe one misconception.

    Only attempts after the most recent observed support for the
    misconception count, so a success that came before the student ever
    showed the misconception is not evidence of recovery from it.
    """
    count: int = 0
    problems: set[str] = field(default_factory=set)
    submission_ids: list[int] = field(default_factory=list)
    latest_age: int | None = None  # age of the most recent counted success


class HistoryProvider:
    """Strict temporal causality: only data strictly before current submission.

    "Before" means a smaller submission id from the same student, and, when
    timestamps exist, a submission time no later than the current one. Methods
    that also look at the current submission say so in their name or docstring;
    no method reads a later submission.

    Age is an attempt distance, not wall-clock time: the number of the
    student's submissions between the evidence and the current one. Demo and
    experiment replays submit many attempts in the same second, so time-based
    age would be zero for all of them.
    """

    # --- submissions -----------------------------------------------------

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
        q = db.query(Submission).filter(
            Submission.student_id == current.student_id,
            Submission.problem_id == current.problem_id,
            Submission.id < current.id,
        )
        if current.submitted_at:
            q = q.filter(Submission.submitted_at <= current.submitted_at)
        return q.order_by(Submission.id.desc()).first()

    @staticmethod
    def age_of(prior: list[Submission], index: int) -> int:
        """Attempt distance of `prior[index]` to the submission after `prior[-1]`."""
        return len(prior) - 1 - index

    # --- learner state ---------------------------------------------------

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

    def get_prior_states(self, db: Session, current: Submission) -> dict[str, LearnerStateHistory]:
        """The latest stored state transition per misconception before `current`.

        Read from the append-only `learner_state_history`, never from the
        mutable `learner_states` row, which may already hold the result of a
        later submission when an older one is re-analysed.
        """
        rows = (
            db.query(LearnerStateHistory)
            .filter(
                LearnerStateHistory.student_id == current.student_id,
                LearnerStateHistory.submission_id != None,  # noqa: E711
                LearnerStateHistory.submission_id < current.id,
            )
            .order_by(LearnerStateHistory.submission_id.asc(), LearnerStateHistory.id.asc())
            .all()
        )
        latest: dict[str, LearnerStateHistory] = {}
        for row in rows:
            latest[row.misconception_id] = row
        return latest

    def get_learner_state(self, db: Session, student_id: int, misconception_id: str, current: Submission) -> LearnerState | None:
        """Deprecated: reads the live row. Use `get_prior_states` for history evidence."""
        prior_ids = [s.id for s in self.get_prior_submissions(db, current)]
        if not prior_ids:
            return None
        return (
            db.query(LearnerState)
            .filter(LearnerState.student_id == student_id, LearnerState.misconception_id == misconception_id)
            .first()
        )

    # --- what a problem probes, and what an attempt showed ----------------

    def problem_probes(self, db: Session, problem_id: str, misconception_id: str) -> bool:
        """True when the problem has a diagnostic test that targets the misconception.

        A pass on such a problem means the student passed a test written to
        catch this misconception. A pass on any other problem says nothing
        about it, however many concept tags the two problems share.
        """
        problem = db.get(Problem, problem_id)
        if problem is None:
            return False
        tags = (
            db.query(TestCase.diagnostic_tag)
            .filter(TestCase.problem_id == problem_id, TestCase.test_type == TestType.DIAGNOSTIC)
            .all()
        )
        return any(code_for_diagnostic_tag(problem.language, t) == misconception_id for (t,) in tags)

    @staticmethod
    def passed_all_tests(db: Session, submission_id: int) -> bool:
        results = db.query(TestResult.passed).filter(TestResult.submission_id == submission_id).all()
        return bool(results) and all(p for (p,) in results)

    @staticmethod
    def has_observed_support(db: Session, submission_id: int, misconception_id: str | None = None) -> bool:
        q = db.query(EvidenceItem).filter(
            EvidenceItem.submission_id == submission_id,
            EvidenceItem.direction == EvidenceDirection.SUPPORT,
            EvidenceItem.source_type.in_(list(OBSERVED_SOURCES)),
        )
        if misconception_id is not None:
            q = q.filter(EvidenceItem.misconception_id == misconception_id)
        return q.first() is not None

    def observed_support_by_misconception(self, db: Session, current: Submission) -> dict[str, list[SupportEvent]]:
        """Observed support on earlier submissions, per misconception, oldest first."""
        prior = self.get_prior_submissions(db, current)
        out: dict[str, list[SupportEvent]] = {}
        for index, ps in enumerate(prior):
            rows = db.query(EvidenceItem.misconception_id).filter(
                EvidenceItem.submission_id == ps.id,
                EvidenceItem.direction == EvidenceDirection.SUPPORT,
                EvidenceItem.source_type.in_(list(OBSERVED_SOURCES)),
                EvidenceItem.misconception_id != None,  # noqa: E711
            ).distinct().all()
            for (mid,) in rows:
                out.setdefault(mid, []).append(SupportEvent(ps.id, ps.problem_id, self.age_of(prior, index)))
        return out

    # --- recovery --------------------------------------------------------

    def related_successes_since_support(
        self, db: Session, current: Submission, misconception_id: str, include_current: bool,
    ) -> RelatedSuccessSummary:
        """Count fully passing attempts on problems that probe the misconception.

        The scan walks back from the newest attempt and stops at the most recent
        attempt with observed support for the misconception. `include_current`
        adds the current submission; the learner model uses it after the
        current attempt has run (it is not future data), the history evidence of
        the current attempt does not.
        """
        prior = self.get_prior_submissions(db, current)
        chain: list[tuple[Submission, int | None]] = [(ps, self.age_of(prior, i)) for i, ps in enumerate(prior)]
        if include_current:
            chain.append((current, None))
        summary = RelatedSuccessSummary()
        probes: dict[str, bool] = {}
        for sub, age in reversed(chain):
            if self.has_observed_support(db, sub.id, misconception_id):
                break
            if sub.problem_id not in probes:
                probes[sub.problem_id] = self.problem_probes(db, sub.problem_id, misconception_id)
            if probes[sub.problem_id] and self.passed_all_tests(db, sub.id):
                summary.count += 1
                summary.problems.add(sub.problem_id)
                summary.submission_ids.append(sub.id)
                if summary.latest_age is None and age is not None:
                    summary.latest_age = age
        return summary

    def count_recent_related_successes(self, db: Session, current: Submission, limit: int = 3) -> int:
        """Deprecated: counts passes on any problem that shares a concept tag.

        Kept for callers outside the learner model. The learner model and the
        history evidence use `related_successes_since_support`, which is tied to
        one misconception.
        """
        problem = db.get(Problem, current.problem_id)
        if not problem:
            return 0
        tags = json.loads(problem.concept_tags or "[]")
        related_ids = [p.id for p in db.query(Problem).all() if set(json.loads(p.concept_tags or "[]")) & set(tags)]
        count = 0
        for ps in reversed(self.get_prior_submissions(db, current)):
            if ps.problem_id not in related_ids:
                continue
            if self.passed_all_tests(db, ps.id):
                count += 1
            if count >= limit:
                break
        return count

    # --- recurrence ------------------------------------------------------

    def count_cross_problem_support(self, db: Session, current: Submission, misconception_id: str) -> int:
        """Distinct problems with observed support, earlier attempts plus the current one.

        Only observed evidence counts. History records attached to a later
        attempt restate earlier evidence; counting them would credit the later
        attempt's problem with a misconception the student did not show there.
        """
        problems: set[str] = set()
        for ps in self.get_prior_submissions(db, current):
            if ps.problem_id == current.problem_id:
                continue
            if self.has_observed_support(db, ps.id, misconception_id):
                problems.add(ps.problem_id)
        if problems and self.has_observed_support(db, current.id, misconception_id):
            problems.add(current.problem_id)
        return len(problems)
