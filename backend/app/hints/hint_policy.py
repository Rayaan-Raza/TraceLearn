from __future__ import annotations
from sqlalchemy.orm import Session
from backend.app.db.models import Diagnosis, HintEvent, Submission
from backend.app.diagnosis.taxonomy import NO_MISCONCEPTION, UNCERTAIN
from backend.app.hints.templates import GENERIC_HINT, HINTS

class HintPolicy:
    def select_hint(self, db: Session, submission: Submission, diagnosis: Diagnosis) -> HintEvent | None:
        mid = diagnosis.primary_misconception
        if mid in (NO_MISCONCEPTION, UNCERTAIN) or diagnosis.requires_teacher_review:
            text = GENERIC_HINT
            level = 1
            mid = mid if mid not in (NO_MISCONCEPTION, UNCERTAIN) else "GENERIC"
        else:
            if diagnosis.primary_confidence >= 0.65:
                level = 3
            elif diagnosis.primary_confidence >= 0.45:
                level = 2
            else:
                level = 1
            text = HINTS.get(mid, {}).get(level, GENERIC_HINT)
        event = HintEvent(
            student_id=submission.student_id,
            submission_id=submission.id,
            misconception_id=mid,
            hint_level=level,
            hint_text=text,
        )
        db.add(event)
        db.commit()
        return event
