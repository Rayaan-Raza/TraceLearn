from __future__ import annotations
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import Submission

RUNTIME_CODES = {
    "IndexError": "RUNTIME_INDEX_ERROR",
    "TypeError": "RUNTIME_TYPE_ERROR",
    "NameError": "RUNTIME_NAME_ERROR",
    "SyntaxError": "RUNTIME_SYNTAX_ERROR",
    "Timeout": "RUNTIME_TIMEOUT",
}

class RuntimeAnalyzer:
    def analyze(self, submission: Submission) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        status = submission.execution_status.value if submission.execution_status else None
        if status == "timeout":
            items.append(EvidenceRecord(
                source_type="execution", evidence_code="RUNTIME_TIMEOUT",
                direction="neutral", weight=0.0, description="execution timed out",
            ))
        elif status == "syntax_error":
            items.append(EvidenceRecord(
                source_type="execution", evidence_code="EXECUTION_SYNTAX_ERROR",
                direction="conflict", weight=0.0, description="syntax error prevents conceptual analysis",
            ))
        stderr = submission.stderr or ""
        for err, code in RUNTIME_CODES.items():
            if err in stderr:
                direction = "support" if err == "IndexError" else "neutral"
                mid = "M02_INDEX_VALUE" if err == "IndexError" else None
                items.append(EvidenceRecord(
                    source_type="execution", evidence_code=code, misconception_id=mid,
                    direction=direction, weight=0.0, description=f"runtime error: {err}",
                ))
        return items
