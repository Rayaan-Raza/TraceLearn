from __future__ import annotations
from sqlalchemy.orm import Session, joinedload
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import Problem, TestCase, TestResult, TestType
from backend.app.diagnosis.cpp_mapping import code_for_diagnostic_tag

class TestAnalyzer:
    def analyze(self, db: Session, submission_id: int) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        rows = (
            db.query(TestResult, TestCase)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .options(joinedload(TestResult.test_case).joinedload(TestCase.problem))
            .filter(TestResult.submission_id == submission_id)
            .all()
        )
        for tr, tc in rows:
            if tr.passed:
                continue
            code = f"TEST_{tc.test_type.value.upper()}_FAIL"
            if tc.test_type == TestType.DIAGNOSTIC and tc.diagnostic_tag:
                code = f"DIAGNOSTIC_{tc.diagnostic_tag.upper()}_FAIL"
                # The tag alone is ambiguous: both banks hold `upper_boundary`
                # under a different target, so the problem language decides.
                mid = code_for_diagnostic_tag(_language_of(tc), tc.diagnostic_tag)
                if mid:
                    items.append(EvidenceRecord(
                        source_type="test", evidence_code=code, misconception_id=mid,
                        direction="support", weight=0.0,
                        description=f"diagnostic test failed: {tc.diagnostic_tag}",
                        details={"test_case_id": tc.id},
                    ))
            else:
                items.append(EvidenceRecord(
                    source_type="test", evidence_code=code, direction="neutral", weight=0.0,
                    description=f"{tc.test_type.value} test failed: {tc.name}",
                    details={"test_case_id": tc.id},
                ))

        by_tag: dict[tuple[str | None, str], list[bool]] = {}
        for tr, tc in rows:
            if tc.test_type == TestType.DIAGNOSTIC and tc.diagnostic_tag:
                by_tag.setdefault((_language_of(tc), tc.diagnostic_tag), []).append(tr.passed)
        for (language, tag), passes in by_tag.items():
            if any(passes) and not all(passes):
                mid = code_for_diagnostic_tag(language, tag)
                items.append(EvidenceRecord(
                    source_type="test", evidence_code="DIAGNOSTIC_CONFLICTING_OUTCOMES",
                    misconception_id=mid, direction="conflict", weight=0.0,
                    description=f"diagnostic tests disagree for tag {tag}",
                    details={"tag": tag},
                ))
        if rows and all(tr.passed for tr, _ in rows):
            # Positive evidence that the program is correct. Without it the
            # fusion step cannot tell "every test passed" from "nothing ran".
            items.append(EvidenceRecord(
                source_type="test", evidence_code="TEST_ALL_PASSED",
                direction="neutral", weight=0.0,
                description=f"all {len(rows)} tests passed",
            ))
        return items


def _language_of(tc: TestCase) -> str | None:
    problem: Problem | None = tc.problem
    return problem.language if problem else None
