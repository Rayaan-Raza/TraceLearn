from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
    print("w", rel)

w("backend/app/diagnosis/current_only.py", '''
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import Diagnosis, DiagnosisMode, EvidenceItem, Submission, UncertaintyLevel
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
            q = q.filter(EvidenceItem.source_type != "history")
        records = []
        for item in q.all():
            if item.source_type.value == "history":
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
''')

w("backend/app/diagnosis/history_aware.py", '''
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import Diagnosis, DiagnosisMode, EvidenceItem, Submission, UncertaintyLevel
from backend.app.diagnosis.confidence import fuse_diagnosis
from backend.app.learner_model.updater import LearnerStateUpdater

class HistoryAwareDiagnosisEngine:
    def __init__(self) -> None:
        self.state_updater = LearnerStateUpdater()

    def diagnose(self, db: Session, submission: Submission) -> Diagnosis:
        records = []
        for item in db.query(EvidenceItem).filter(EvidenceItem.submission_id == submission.id).all():
            records.append(EvidenceRecord(
                source_type=item.source_type.value,
                evidence_code=item.evidence_code,
                misconception_id=item.misconception_id,
                direction=item.direction.value,
                weight=item.weight,
                description=item.description,
            ))
        result = fuse_diagnosis(records)
        diag = Diagnosis(
            submission_id=submission.id,
            mode=DiagnosisMode.HISTORY_AWARE,
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
        self.state_updater.update_from_diagnosis(db, submission, diag)
        return diag
''')

w("backend/app/diagnosis/__init__.py", '''from backend.app.diagnosis.current_only import CurrentOnlyDiagnosisEngine\nfrom backend.app.diagnosis.history_aware import HistoryAwareDiagnosisEngine\n''')

w("backend/app/learner_model/states.py", '''
from backend.app.db.models import MisconceptionState

INITIAL_STATE = MisconceptionState.NEW

def can_become_persistent(cross_problem_count: int, min_cross: int = 2) -> bool:
    return cross_problem_count >= min_cross
''')

w("backend/app/learner_model/history.py", '''
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.db.models import LearnerState, LearnerStateHistory, Problem, Submission, TestResult

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
            from backend.app.db.models import EvidenceItem
            evs = db.query(EvidenceItem).filter(
                EvidenceItem.submission_id == ps.id,
                EvidenceItem.misconception_id == misconception_id,
                EvidenceItem.direction == "support",
            ).count()
            if evs:
                problems.add(ps.problem_id)
        if misconception_id:
            from backend.app.analysis.static_analyzer import StaticAnalyzer
            cur_evs = db.query(EvidenceItem).filter(
                EvidenceItem.submission_id == current.id,
                EvidenceItem.misconception_id == misconception_id,
                EvidenceItem.direction == "support",
            ).count()
            if cur_evs:
                problems.add(current.problem_id)
        return len(problems)
''')

w("backend/app/learner_model/updater.py", '''
from __future__ import annotations
import json
import yaml
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db.models import Diagnosis, EvidenceItem, LearnerState, LearnerStateHistory, MisconceptionState, Submission
from backend.app.diagnosis.taxonomy import ALL_MISCONCEPTIONS, NO_MISCONCEPTION, UNCERTAIN
from backend.app.learner_model.history import HistoryProvider
from backend.app.learner_model.states import can_become_persistent

class LearnerStateUpdater:
    def __init__(self) -> None:
        self.history = HistoryProvider()

    def _min_cross(self) -> int:
        raw = yaml.safe_load(Path(settings.evidence_weights_path).read_text(encoding="utf-8"))
        return raw.get("learner_state", {}).get("min_cross_problem_for_persistent", 2)

    def update_from_diagnosis(self, db: Session, submission: Submission, diagnosis: Diagnosis) -> LearnerState | None:
        mid = diagnosis.primary_misconception
        if mid in (NO_MISCONCEPTION, UNCERTAIN):
            return None
        if mid not in ALL_MISCONCEPTIONS:
            return None
        existing = (
            db.query(LearnerState)
            .filter(LearnerState.student_id == submission.student_id, LearnerState.misconception_id == mid)
            .first()
        )
        support = db.query(EvidenceItem).filter(
            EvidenceItem.submission_id == submission.id,
            EvidenceItem.misconception_id == mid,
            EvidenceItem.direction == "support",
        ).count()
        cross = self.history.count_cross_problem_support(db, submission, mid)
        recent_success = self.history.count_recent_related_successes(db, submission)
        old_state = existing.state if existing else MisconceptionState.NEW
        old_conf = existing.confidence if existing else 0.0
        new_conf = diagnosis.primary_confidence
        new_state = self._compute_state(existing, diagnosis, cross, recent_success, support)
        if existing:
            existing.state = new_state
            existing.confidence = new_conf
            existing.trigger_submission_id = submission.id
            existing.support_count += support
            existing.cross_problem_support_count = cross
            existing.recent_success_count = recent_success
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
                recent_success_count=recent_success,
            )
            db.add(row)
        if new_state != old_state or abs(new_conf - old_conf) > 0.01:
            db.add(LearnerStateHistory(
                student_id=submission.student_id,
                misconception_id=mid,
                old_state=old_state,
                new_state=new_state,
                old_confidence=old_conf,
                new_confidence=new_conf,
                submission_id=submission.id,
                reason_json=json.dumps({
                    "cross_problem_support": cross,
                    "recent_successes": recent_success,
                    "support_count": support,
                    "diagnosis_confidence": new_conf,
                }),
            ))
        db.commit()
        return row

    def _compute_state(self, existing, diagnosis, cross, recent_success, support) -> MisconceptionState:
        if diagnosis.requires_teacher_review:
            return MisconceptionState.REQUIRES_TEACHER_REVIEW
        if existing and existing.state == MisconceptionState.RESOLVED and diagnosis.primary_confidence >= 0.45:
            return MisconceptionState.RECURRED
        if existing and existing.state == MisconceptionState.PERSISTENT and recent_success >= 1 and diagnosis.primary_confidence < 0.5:
            return MisconceptionState.IMPROVING
        if existing and existing.state == MisconceptionState.PERSISTENT and recent_success >= 2 and diagnosis.primary_confidence < 0.25:
            return MisconceptionState.RESOLVED
        if can_become_persistent(cross, self._min_cross()):
            return MisconceptionState.PERSISTENT
        return MisconceptionState.NEW
''')

w("backend/app/learner_model/__init__.py", '''from backend.app.learner_model.history import HistoryProvider\n''')

w("backend/app/hints/templates.py", '''
HINTS = {
    "M01_LOOP_BOUNDARY": {
        1: "Check which values your loop boundary actually includes.",
        2: "Compare the number of iterations with the number of items you intend to process.",
        3: "Review the upper bound supplied to range(). Remember that Python excludes the upper bound.",
    },
    "M02_INDEX_VALUE": {
        1: "Think about whether you need a position or the value stored at that position.",
        2: "When looping, decide if the loop variable is an index or an element value.",
        3: "Use the loop variable directly when you mean the element, not nums[variable] unless variable is an index.",
    },
    "M03_MISSING_RETURN": {
        1: "Make sure your function sends a result back to the caller.",
        2: "Printing shows output but does not return a value to the caller.",
        3: "Use return with the computed result on every code path that should produce an answer.",
    },
}
GENERIC_HINT = "Re-read the problem and trace through a small example by hand."
''')

w("backend/app/hints/hint_policy.py", '''
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
''')

print("part4 done")
