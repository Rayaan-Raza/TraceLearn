"""Apply the learner-state rules after each history-aware diagnosis.

The rules are in `docs/LEARNER_STATE_RULES.md`. In short:

Support path (the history-aware diagnosis names misconception M):
    review flag                         -> REQUIRES_TEACHER_REVIEW
    M was RESOLVED, strong evidence     -> RECURRED
    M was RESOLVED, weak evidence       -> REQUIRES_TEACHER_REVIEW
    M was RECURRED                      -> RECURRED
    observed support on >= N problems   -> PERSISTENT   (N = min_cross_problem_for_persistent)
    otherwise                           -> NEW

    A support event after IMPROVING is a regression: the cross-problem count
    never falls, so the state goes back to PERSISTENT.

Success path (every test passed, NO_MISCONCEPTION, no review flag):
    Only misconceptions that this problem's diagnostic tests probe are
    touched. Their confidence becomes
        clip(decay * C_prev - |related_success| * S, 0, 1)
    where S counts the passing attempts on probing problems since the last
    observed support for M, the current attempt included. Then
    PERSISTENT / RECURRED, confidence falls                  -> IMPROVING
    IMPROVING, S >= min_related_successes_for_resolved,
        on >= min_distinct_problems_for_resolved problems,
        confidence < resolved_confidence                    -> RESOLVED
    anything else keeps its state (NEW stays NEW, REQUIRES_TEACHER_REVIEW
    stays for the teacher).

Anything else (UNCERTAIN, a syntax error, a failing attempt with no
hypothesis, a pass on a problem that does not probe M) changes no state.

Every change appends a `learner_state_history` row with the rule that fired.
"""
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.db.models import (
    Diagnosis, EvidenceDirection, EvidenceItem, LearnerState, LearnerStateHistory, MisconceptionState, Submission,
)
from backend.app.diagnosis.confidence import load_weights
from backend.app.diagnosis.evidence_contract import OBSERVED_SOURCES
from backend.app.diagnosis.taxonomy import NO_MISCONCEPTION, SCORED_MISCONCEPTIONS
from backend.app.learner_model.history import HistoryProvider
from backend.app.learner_model.states import can_become_persistent

S = MisconceptionState
RECOVERING_FROM = (S.PERSISTENT, S.RECURRED)


class LearnerStateUpdater:
    def __init__(self) -> None:
        self.history = HistoryProvider()

    # --- configuration ---------------------------------------------------

    def _cfg(self) -> dict:
        cfg = load_weights()
        ls = cfg.get("learner_state", {}) or {}
        w = cfg.get("weights", {}) or {}
        return {
            "min_cross": ls.get("min_cross_problem_for_persistent", 2),
            "min_successes": ls.get("min_related_successes_for_resolved", 2),
            "min_distinct": ls.get("min_distinct_problems_for_resolved", 2),
            "resolved_conf": ls.get("resolved_confidence", 0.25),
            "recurred_conf": ls.get("recurred_confidence", 0.45),
            "success_step": abs(w.get("related_success", -0.20)),
            "decay": (cfg.get("history", {}) or {}).get("decay_factor", 0.80),
        }

    def _min_cross(self) -> int:
        return self._cfg()["min_cross"]

    # --- entry point -----------------------------------------------------

    def update_from_diagnosis(self, db: Session, submission: Submission, diagnosis: Diagnosis) -> list[LearnerState]:
        """Update the stored learner states after a history-aware diagnosis.

        Returns the rows that this submission changed or created.
        """
        mid = diagnosis.primary_misconception
        if mid in SCORED_MISCONCEPTIONS:
            row = self._apply_support(db, submission, diagnosis, mid)
            return [row] if row is not None else []
        if self._is_verified_success(db, submission, diagnosis):
            return self._apply_success(db, submission)
        # UNCERTAIN, a syntax error, or anything else that is neither a named
        # misconception nor a verified pass: no state moves on this attempt.
        return []

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _is_verified_success(db: Session, submission: Submission, diagnosis: Diagnosis) -> bool:
        if diagnosis.primary_misconception != NO_MISCONCEPTION or diagnosis.requires_teacher_review:
            return False
        return HistoryProvider.passed_all_tests(db, submission.id)

    @staticmethod
    def _is_stale(existing: LearnerState | None, submission: Submission) -> bool:
        """True when the stored row already reflects this or a later submission.

        Re-running an older submission must not overwrite the result of a
        newer one, and re-running the same submission must not count it twice.
        """
        return bool(existing and existing.trigger_submission_id and existing.trigger_submission_id >= submission.id)

    def _settled_state(self, db: Session, student_id: int, mid: str, submission_id: int) -> MisconceptionState | None:
        """The latest stored state for M before this submission that is not a review flag."""
        row = (
            db.query(LearnerStateHistory)
            .filter(
                LearnerStateHistory.student_id == student_id,
                LearnerStateHistory.misconception_id == mid,
                LearnerStateHistory.new_state != S.REQUIRES_TEACHER_REVIEW,
                (LearnerStateHistory.submission_id == None) | (LearnerStateHistory.submission_id < submission_id),  # noqa: E711
            )
            .order_by(LearnerStateHistory.id.desc())
            .first()
        )
        return row.new_state if row else None

    @staticmethod
    def _observed_support(db: Session, submission_id: int, mid: str) -> int:
        return db.query(EvidenceItem).filter(
            EvidenceItem.submission_id == submission_id,
            EvidenceItem.misconception_id == mid,
            EvidenceItem.direction == EvidenceDirection.SUPPORT,
            EvidenceItem.source_type.in_(list(OBSERVED_SOURCES)),
        ).count()

    @staticmethod
    def _record(db: Session, submission: Submission, mid: str, old_state: MisconceptionState,
                new_state: MisconceptionState, old_conf: float, new_conf: float, reason: dict) -> None:
        if new_state == old_state and abs(new_conf - old_conf) <= 0.01:
            return
        db.add(LearnerStateHistory(
            student_id=submission.student_id,
            misconception_id=mid,
            old_state=old_state,
            new_state=new_state,
            old_confidence=old_conf,
            new_confidence=new_conf,
            submission_id=submission.id,
            reason_json=json.dumps(reason),
        ))

    # --- support path ----------------------------------------------------

    def _apply_support(self, db: Session, submission: Submission, diagnosis: Diagnosis, mid: str) -> LearnerState | None:
        cfg = self._cfg()
        existing = (
            db.query(LearnerState)
            .filter(LearnerState.student_id == submission.student_id, LearnerState.misconception_id == mid)
            .first()
        )
        if self._is_stale(existing, submission):
            return None
        support = self._observed_support(db, submission.id, mid)
        cross = self.history.count_cross_problem_support(db, submission, mid)
        old_state = existing.state if existing else S.NEW
        old_conf = existing.confidence if existing else 0.0
        new_conf = diagnosis.primary_confidence
        previous = old_state
        if existing and old_state == S.REQUIRES_TEACHER_REVIEW:
            previous = self._settled_state(db, submission.student_id, mid, submission.id) or old_state
        new_state, rule = self._state_after_support(previous if existing else None, diagnosis, cross, cfg)
        if existing:
            existing.state = new_state
            existing.confidence = new_conf
            existing.trigger_submission_id = submission.id
            existing.support_count += support
            existing.cross_problem_support_count = cross
            existing.recent_success_count = 0
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
                recent_success_count=0,
            )
            db.add(row)
        self._record(db, submission, mid, old_state, new_state, old_conf, new_conf, {
            "path": "support",
            "rule": rule,
            "previous_state": previous.value if existing else None,
            "cross_problem_support": cross,
            "support_count": support,
            "recent_successes": 0,
            "diagnosis_confidence": new_conf,
            "requires_teacher_review": bool(diagnosis.requires_teacher_review),
        })
        db.commit()
        return row

    @staticmethod
    def _state_after_support(previous: MisconceptionState | None, diagnosis: Diagnosis, cross: int, cfg: dict) -> tuple[MisconceptionState, str]:
        if diagnosis.requires_teacher_review:
            return S.REQUIRES_TEACHER_REVIEW, "review_flag"
        if previous == S.RESOLVED:
            if diagnosis.primary_confidence >= cfg["recurred_conf"]:
                return S.RECURRED, "strong_evidence_after_resolved"
            return S.REQUIRES_TEACHER_REVIEW, "weak_evidence_after_resolved"
        if previous == S.RECURRED:
            return S.RECURRED, "support_while_recurred"
        if can_become_persistent(cross, cfg["min_cross"]):
            if previous == S.IMPROVING:
                return S.PERSISTENT, "regression_after_improving"
            return S.PERSISTENT, "cross_problem_recurrence"
        return S.NEW, "isolated_or_same_problem"

    # --- success path ----------------------------------------------------

    def _apply_success(self, db: Session, submission: Submission) -> list[LearnerState]:
        cfg = self._cfg()
        rows = db.query(LearnerState).filter(LearnerState.student_id == submission.student_id).all()
        changed: list[LearnerState] = []
        for row in rows:
            if self._is_stale(row, submission):
                continue
            if not self.history.problem_probes(db, submission.problem_id, row.misconception_id):
                # A pass on a problem that does not test this misconception is
                # not evidence about it.
                continue
            summary = self.history.related_successes_since_support(db, submission, row.misconception_id, include_current=True)
            if summary.count == 0:
                continue
            old_state, old_conf = row.state, row.confidence
            new_conf = max(0.0, min(1.0, cfg["decay"] * old_conf - cfg["success_step"] * summary.count))
            new_state, rule = self._state_after_success(old_state, old_conf, new_conf, summary, cfg)
            row.state = new_state
            row.confidence = new_conf
            row.trigger_submission_id = submission.id
            row.recent_success_count = summary.count
            self._record(db, submission, row.misconception_id, old_state, new_state, old_conf, new_conf, {
                "path": "related_success",
                "rule": rule,
                "recent_successes": summary.count,
                "success_problems": sorted(summary.problems),
                "success_submission_ids": summary.submission_ids,
                "decay_factor": cfg["decay"],
                "success_step": cfg["success_step"],
            })
            changed.append(row)
        db.commit()
        return changed

    @staticmethod
    def _state_after_success(old_state: MisconceptionState, old_conf: float, new_conf: float, summary, cfg: dict) -> tuple[MisconceptionState, str]:
        if old_state in RECOVERING_FROM and new_conf < old_conf:
            return S.IMPROVING, "related_success_after_persistent"
        if (
            old_state == S.IMPROVING
            and summary.count >= cfg["min_successes"]
            and len(summary.problems) >= cfg["min_distinct"]
            and new_conf < cfg["resolved_conf"]
        ):
            return S.RESOLVED, "sustained_related_success"
        if old_state == S.REQUIRES_TEACHER_REVIEW:
            return old_state, "success_does_not_clear_review"
        return old_state, "related_success_confidence_only"
