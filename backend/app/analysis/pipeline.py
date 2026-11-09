from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.cpp_static import CppStaticAnalyzer
from backend.app.analysis.diff_analyzer import DiffAnalyzer
from backend.app.analysis.model_runner import model_records
from backend.app.analysis.runtime_analyzer import RuntimeAnalyzer
from backend.app.analysis.static_analyzer import StaticAnalyzer
from backend.app.analysis.test_analyzer import TestAnalyzer
from backend.app.db.models import EvidenceDirection, EvidenceItem, EvidenceSourceType, Problem, Submission
from backend.app.diagnosis.confidence import apply_evidence_weights
from backend.app.learner_model.history import HistoryProvider


def _is_cpp(source_code: str) -> bool:
    return "#include" in source_code or "int main" in source_code


class AnalysisPipeline:
    def __init__(self, history: HistoryProvider | None = None) -> None:
        self.history = history or HistoryProvider()
        self.static = StaticAnalyzer()
        self.cpp_static = CppStaticAnalyzer()
        self.test = TestAnalyzer()
        self.runtime = RuntimeAnalyzer()
        self.diff = DiffAnalyzer(self.history)

    @staticmethod
    def _run_record(db: Session, submission: Submission):
        """With model_run_records=on, the failing submission's run record; otherwise None."""
        from backend.app.config import settings
        from backend.app.db.models import ExecutionStatus

        if settings.model_run_records != "on" or settings.model_diagnosis == "off":
            return None
        if submission.execution_status in (None, ExecutionStatus.SUCCESS, ExecutionStatus.SYNTAX_ERROR, ExecutionStatus.SYSTEM_ERROR):
            return None
        from backend.app.analysis.run_record import build_run_record, tests_for_problem

        return build_run_record(submission.source_code, tests_for_problem(db, submission.problem_id))

    @staticmethod
    def model_applies(submission: Submission) -> bool:
        """The classifier describes bugs in failing C++: not passing code, not compile or system errors."""
        from backend.app.db.models import ExecutionStatus

        return _is_cpp(submission.source_code) and submission.execution_status not in (
            None, ExecutionStatus.SUCCESS, ExecutionStatus.SYNTAX_ERROR, ExecutionStatus.SYSTEM_ERROR)

    def analyze_submission(self, db: Session, submission: Submission, include_history: bool = True,
                           defer_model: bool = False) -> list[EvidenceItem]:
        db.query(EvidenceItem).filter(EvidenceItem.submission_id == submission.id).delete()
        problem = db.get(Problem, submission.problem_id)
        fn_name = problem.function_name if problem else ""
        records = []
        if _is_cpp(submission.source_code):
            records.extend(self.cpp_static.analyze(submission.source_code, fn_name))
        else:
            records.extend(self.static.analyze(submission.source_code, fn_name))
        records.extend(self.test.analyze(db, submission.id))
        records.extend(self.runtime.analyze(submission))
        records.extend(self.diff.analyze(db, submission))
        if self.model_applies(submission) and not defer_model:   # trained on failing C/C++ only
            records.extend(model_records(submission.source_code, "cpp", run_record=self._run_record(db, submission)))
        if include_history:
            from backend.app.analysis.history_analyzer import HistoryAnalyzer
            records.extend(HistoryAnalyzer(self.history).analyze(db, submission))
        weighted = apply_evidence_weights(records)
        items: list[EvidenceItem] = []
        for rec in weighted:
            item = EvidenceItem(
                submission_id=submission.id,
                source_type=EvidenceSourceType(rec.source_type),
                evidence_code=rec.evidence_code,
                misconception_id=rec.misconception_id,
                direction=EvidenceDirection(rec.direction),
                weight=rec.weight,
                description=rec.description,
                details_json=json.dumps(rec.details),
            )
            db.add(item)
            items.append(item)
        db.commit()
        return items
