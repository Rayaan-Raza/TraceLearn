from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy.orm import Session
from backend.app.db.models import Diagnosis, HintEvent, ProblemHint, Submission
from backend.app.diagnosis.cpp_mapping import hint_misconception_ids
from backend.app.diagnosis.taxonomy import NO_MISCONCEPTION, UNCERTAIN
from backend.app.hints.templates import GENERIC_HINT, HINTS

if TYPE_CHECKING:
    from backend.app.diagnosis.xgb_classifier import ModelPrediction

_HIGH_CONFIDENCE = 0.75


def hint_levels(db: Session, submission: Submission, diagnosis: Diagnosis | None) -> tuple[str, dict[int, str]]:
    """Return the hint target and its texts by level for a diagnosis.

    An uncertain diagnosis, or one that needs teacher review, gets one generic
    hint. Otherwise a problem-specific hint in `problem_hints` overrides the
    template hint. The bank stores its C++ hints under the bank code
    (`CPP-M05`) while a diagnosis holds the backend code (`CPP_RANGE_CHECK`),
    so the query accepts every spelling the mapping table knows.
    """
    mid = diagnosis.primary_misconception if diagnosis else UNCERTAIN
    if diagnosis is None or mid in (NO_MISCONCEPTION, UNCERTAIN) or diagnosis.requires_teacher_review:
        return "GENERIC", {1: GENERIC_HINT}
    rows = (
        db.query(ProblemHint)
        .filter(
            ProblemHint.problem_id == submission.problem_id,
            ProblemHint.misconception_id.in_(hint_misconception_ids(mid)),
        )
        .order_by(ProblemHint.level)
        .all()
    )
    if rows:
        return mid, {r.level: r.text for r in rows}
    return mid, HINTS.get(mid, {1: GENERIC_HINT})


class HintPolicy:
    def select_hint(
        self,
        db: Session,
        submission: Submission,
        diagnosis: Diagnosis,
        model_prediction: "ModelPrediction | None" = None,
    ) -> HintEvent | None:
        # A submission with no misconception needs no hint.
        if diagnosis.primary_misconception == NO_MISCONCEPTION and not diagnosis.requires_teacher_review:
            return None
        mid, levels = hint_levels(db, submission, diagnosis)
        # High-confidence model prediction (not abstained, not OTHER_ERROR) →
        # skip to level 2 when it exists, so the student gets a more specific
        # hint immediately.
        level = min(levels)
        if (
            model_prediction is not None
            and not model_prediction.abstained
            and model_prediction.top_label != "CPP_OTHER_ERROR"
            and model_prediction.top_probability >= _HIGH_CONFIDENCE
            and 2 in levels
        ):
            level = 2
        event = HintEvent(
            student_id=submission.student_id,
            submission_id=submission.id,
            misconception_id=mid,
            hint_level=level,
            hint_text=levels[level],
        )
        db.add(event)
        db.commit()
        return event
