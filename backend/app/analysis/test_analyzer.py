from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import TestCase, TestResult, TestType
from backend.app.diagnosis.taxonomy import M01_LOOP_BOUNDARY, M02_INDEX_VALUE, M03_MISSING_RETURN

TAG_TO_MIS = {
    "upper_boundary": M01_LOOP_BOUNDARY,
    "empty_list": M02_INDEX_VALUE,
    "return_value": M03_MISSING_RETURN,
    "index_vs_value": M02_INDEX_VALUE,
}

class TestAnalyzer:
    def analyze(self, db: Session, submission_id: int) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        rows = (
            db.query(TestResult, TestCase)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .filter(TestResult.submission_id == submission_id)
            .all()
        )
        for tr, tc in rows:
            if tr.passed:
                continue
            code = f"TEST_{tc.test_type.value.upper()}_FAIL"
            if tc.test_type == TestType.DIAGNOSTIC and tc.diagnostic_tag:
                code = f"DIAGNOSTIC_{tc.diagnostic_tag.upper()}_FAIL"
                mid = TAG_TO_MIS.get(tc.diagnostic_tag)
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

        by_tag: dict[str, list[bool]] = {}
        for tr, tc in rows:
            if tc.test_type == TestType.DIAGNOSTIC and tc.diagnostic_tag:
                by_tag.setdefault(tc.diagnostic_tag, []).append(tr.passed)
        for tag, passes in by_tag.items():
            if any(passes) and not all(passes):
                mid = TAG_TO_MIS.get(tag)
                items.append(EvidenceRecord(
                    source_type="test", evidence_code="DIAGNOSTIC_CONFLICTING_OUTCOMES",
                    misconception_id=mid, direction="conflict", weight=0.0,
                    description=f"diagnostic tests disagree for tag {tag}",
                    details={"tag": tag},
                ))
        return items
