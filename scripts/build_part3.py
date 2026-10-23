from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
    print("w", rel)

w("backend/app/analysis/test_analyzer.py", '''
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
        return items
''')

w("backend/app/analysis/runtime_analyzer.py", '''
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
''')

w("backend/app/analysis/diff_analyzer.py", '''
from __future__ import annotations
import difflib
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import Submission
from backend.app.learner_model.history import HistoryProvider

class DiffAnalyzer:
    def __init__(self, history: HistoryProvider) -> None:
        self.history = history

    def analyze(self, db: Session, submission: Submission) -> list[EvidenceRecord]:
        prior = self.history.get_prior_same_problem_submission(db, submission)
        if prior is None:
            return [EvidenceRecord(
                source_type="sequence", evidence_code="SEQUENCE_FIRST_ATTEMPT",
                direction="neutral", weight=0.0, description="first attempt on this problem",
            )]
        items: list[EvidenceRecord] = []
        if prior.source_code.strip() != submission.source_code.strip():
            items.append(EvidenceRecord(
                source_type="sequence", evidence_code="SEQUENCE_CODE_CHANGED",
                direction="neutral", weight=0.0, description="code changed from previous attempt",
            ))
            diff = list(difflib.unified_diff(prior.source_code.splitlines(), submission.source_code.splitlines(), lineterm=""))
            if diff:
                items[-1].details = {"diff_lines": len(diff)}
        else:
            items.append(EvidenceRecord(
                source_type="sequence", evidence_code="SEQUENCE_SAME_CODE",
                direction="neutral", weight=0.0, description="same code as previous attempt",
            ))
        return items
''')

w("backend/app/analysis/pipeline.py", '''
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.diff_analyzer import DiffAnalyzer
from backend.app.analysis.runtime_analyzer import RuntimeAnalyzer
from backend.app.analysis.static_analyzer import StaticAnalyzer
from backend.app.analysis.test_analyzer import TestAnalyzer
from backend.app.db.models import EvidenceDirection, EvidenceItem, EvidenceSourceType, Problem, Submission
from backend.app.diagnosis.confidence import apply_evidence_weights
from backend.app.learner_model.history import HistoryProvider

class AnalysisPipeline:
    def __init__(self, history: HistoryProvider | None = None) -> None:
        self.history = history or HistoryProvider()
        self.static = StaticAnalyzer()
        self.test = TestAnalyzer()
        self.runtime = RuntimeAnalyzer()
        self.diff = DiffAnalyzer(self.history)

    def analyze_submission(self, db: Session, submission: Submission, include_history: bool = True) -> list[EvidenceItem]:
        db.query(EvidenceItem).filter(EvidenceItem.submission_id == submission.id).delete()
        problem = db.get(Problem, submission.problem_id)
        records = []
        records.extend(self.static.analyze(submission.source_code, problem.function_name if problem else ""))
        records.extend(self.test.analyze(db, submission.id))
        records.extend(self.runtime.analyze(submission))
        records.extend(self.diff.analyze(db, submission))
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
''')

w("backend/app/analysis/history_analyzer.py", '''
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import EvidenceItem, Submission
from backend.app.diagnosis.taxonomy import M01_LOOP_BOUNDARY, M02_INDEX_VALUE, M03_MISSING_RETURN
from backend.app.learner_model.history import HistoryProvider

class HistoryAnalyzer:
    def __init__(self, history: HistoryProvider) -> None:
        self.history = history

    def analyze(self, db: Session, submission: Submission) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        prior_subs = self.history.get_prior_submissions(db, submission)
        misconception_problems: dict[str, set[str]] = {}
        for ps in prior_subs:
            evs = db.query(EvidenceItem).filter(
                EvidenceItem.submission_id == ps.id,
                EvidenceItem.direction == "support",
            ).all()
            for ev in evs:
                if ev.misconception_id:
                    misconception_problems.setdefault(ev.misconception_id, set()).add(ps.problem_id)
        for mid, problems in misconception_problems.items():
            if submission.problem_id not in problems and len(problems) >= 1:
                items.append(EvidenceRecord(
                    source_type="history", evidence_code=f"PREVIOUS_RELATED_{mid[:3]}",
                    misconception_id=mid, direction="support", weight=0.0,
                    description=f"same {mid} evidence on related problem(s): {sorted(problems)}",
                    details={"problems": sorted(problems)},
                ))
            if len(problems) >= 1:
                items.append(EvidenceRecord(
                    source_type="history", evidence_code="CROSS_PROBLEM_RECURRENCE",
                    misconception_id=mid, direction="support", weight=0.0,
                    description=f"cross-problem recurrence for {mid}",
                ))
        related_success = self.history.count_recent_related_successes(db, submission)
        if related_success:
            items.append(EvidenceRecord(
                source_type="history", evidence_code="RELATED_SUCCESS_AFTER_MISCONCEPTION",
                direction="conflict", weight=0.0,
                description=f"{related_success} recent related success(es)",
                details={"count": related_success},
            ))
        state = self.history.get_learner_state(db, submission.student_id, M01_LOOP_BOUNDARY, submission)
        if state:
            items.append(EvidenceRecord(
                source_type="history", evidence_code="PREVIOUS_LEARNER_STATE",
                misconception_id=state.misconception_id, direction="neutral", weight=0.0,
                description=f"prior state {state.state.value} for {state.misconception_id}",
            ))
        return items
''')

w("backend/app/analysis/__init__.py", '''from backend.app.analysis.pipeline import AnalysisPipeline\n''')

# diagnosis
w("backend/app/diagnosis/taxonomy.py", '''
M01_LOOP_BOUNDARY = "M01_LOOP_BOUNDARY"
M02_INDEX_VALUE = "M02_INDEX_VALUE"
M03_MISSING_RETURN = "M03_MISSING_RETURN"
NO_MISCONCEPTION = "NO_MISCONCEPTION"
UNCERTAIN = "UNCERTAIN"
ALL_MISCONCEPTIONS = [M01_LOOP_BOUNDARY, M02_INDEX_VALUE, M03_MISSING_RETURN]
ALL_LABELS = ALL_MISCONCEPTIONS + [NO_MISCONCEPTION, UNCERTAIN]
''')

w("backend/app/diagnosis/rules.py", '''
from __future__ import annotations
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.diagnosis.taxonomy import ALL_MISCONCEPTIONS, NO_MISCONCEPTION, UNCERTAIN

CODE_TO_MISCONCEPTION: dict[str, str] = {}

def register(code: str, mid: str) -> None:
    CODE_TO_MISCONCEPTION[code] = mid

for mid in ALL_MISCONCEPTIONS:
    register(f"STATIC_{mid.split('_')[0]}_", mid)

STATIC_MAP = {
    "STATIC_RANGE_N_PLUS_ONE": "M01_LOOP_BOUNDARY",
    "STATIC_ITER_VALUE_USED_AS_INDEX": "M02_INDEX_VALUE",
    "STATIC_NO_RETURN": "M03_MISSING_RETURN",
    "STATIC_PRINT_INSTEAD_OF_RETURN": "M03_MISSING_RETURN",
}

def map_evidence(rec: EvidenceRecord) -> str | None:
    if rec.misconception_id:
        return rec.misconception_id
    return STATIC_MAP.get(rec.evidence_code)

def aggregate_scores(records: list[EvidenceRecord]) -> dict[str, float]:
    scores = {m: 0.0 for m in ALL_MISCONCEPTIONS}
    for rec in records:
        mid = map_evidence(rec)
        if mid and mid in scores:
            if rec.direction == "support":
                scores[mid] += rec.weight
            elif rec.direction == "conflict":
                scores[mid] -= rec.weight * 0.5
    return scores
''')

w("backend/app/diagnosis/confidence.py", '''
from __future__ import annotations
import yaml
from pathlib import Path
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.config import settings
from backend.app.diagnosis.rules import aggregate_scores
from backend.app.diagnosis.taxonomy import ALL_MISCONCEPTIONS, NO_MISCONCEPTION, UNCERTAIN, UncertaintyLevel

_weights_cache: dict | None = None

def load_weights() -> dict:
    global _weights_cache
    if _weights_cache is None:
        path = Path(settings.evidence_weights_path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        _weights_cache = raw
    return _weights_cache

def apply_evidence_weights(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    cfg = load_weights()
    w = cfg.get("weights", {})
    mapping = {
        "STATIC_RANGE_N_PLUS_ONE": w.get("static_strong", 0.30),
        "STATIC_ITER_VALUE_USED_AS_INDEX": w.get("static_strong", 0.30),
        "STATIC_NO_RETURN": w.get("static_strong", 0.30),
        "STATIC_PRINT_INSTEAD_OF_RETURN": w.get("static_strong", 0.30),
        "DIAGNOSTIC_UPPER_BOUNDARY_FAIL": w.get("diagnostic_match", 0.35),
        "DIAGNOSTIC_EMPTY_LIST_FAIL": w.get("diagnostic_match", 0.35),
        "DIAGNOSTIC_RETURN_VALUE_FAIL": w.get("diagnostic_match", 0.35),
        "DIAGNOSTIC_INDEX_VS_VALUE_FAIL": w.get("diagnostic_match", 0.35),
        "RUNTIME_INDEX_ERROR": w.get("runtime_support", 0.15),
        "TEST_HIDDEN_FAIL": w.get("general_test_pattern", 0.10),
        "TEST_VISIBLE_FAIL": w.get("general_test_pattern", 0.10),
        "SEQUENCE_CODE_CHANGED": w.get("previous_same_problem", 0.10),
        "CROSS_PROBLEM_RECURRENCE": w.get("cross_problem_recurrence", 0.20),
        "RELATED_SUCCESS_AFTER_MISCONCEPTION": w.get("related_success", -0.20),
        "EXECUTION_SYNTAX_ERROR": w.get("conflicting_diagnostic", -0.20),
    }
    decay = cfg.get("history", {}).get("decay_factor", 0.80)
    out: list[EvidenceRecord] = []
    for rec in records:
        base = mapping.get(rec.evidence_code, 0.05 if rec.direction == "support" else 0.0)
        if rec.source_type == "history" and base:
            age = rec.details.get("age", 0)
            base *= decay ** age
        nr = EvidenceRecord(
            source_type=rec.source_type, evidence_code=rec.evidence_code,
            direction=rec.direction, weight=base if rec.direction != "neutral" else 0.0,
            description=rec.description, misconception_id=rec.misconception_id, details=rec.details,
        )
        out.append(nr)
    return out

def clamp(v: float) -> float:
    return max(0.0, min(1.0, v))

def fuse_diagnosis(records: list[EvidenceRecord]) -> dict:
    cfg = load_weights()
    thresholds = cfg.get("thresholds", {})
    review_conf = thresholds.get("review_confidence", 0.35)
    margin = thresholds.get("hypothesis_margin", 0.10)
    weighted = apply_evidence_weights(records)
    scores = aggregate_scores(weighted)
    if any(r.evidence_code == "EXECUTION_SYNTAX_ERROR" for r in weighted):
        return {
            "primary": NO_MISCONCEPTION, "primary_confidence": 0.1,
            "alternative": None, "alternative_confidence": None,
            "uncertainty": "high", "requires_review": True,
            "explanation": {"scores": scores, "supporting": [], "conflicting": [r.__dict__ for r in weighted if r.direction=="conflict"]},
        }
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary, pscore = ranked[0]
    alt, ascore = ranked[1] if len(ranked) > 1 else (None, 0.0)
    pconf = clamp(pscore)
    aconf = clamp(ascore) if alt else None
    if pconf < 0.05:
        primary, pconf = NO_MISCONCEPTION, 0.2
    if pconf < review_conf or (alt and abs(pconf - (aconf or 0)) < margin):
        uncertainty = "high"
        requires = True
        if pconf < review_conf:
            primary = UNCERTAIN
    elif pconf < 0.55:
        uncertainty = "medium"
        requires = False
    else:
        uncertainty = "low"
        requires = False
    supporting = [r for r in weighted if r.direction == "support" and r.weight]
    conflicting = [r for r in weighted if r.direction == "conflict" and r.weight]
    return {
        "primary": primary, "primary_confidence": pconf,
        "alternative": alt if alt and ascore > 0.05 else None,
        "alternative_confidence": aconf,
        "uncertainty": uncertainty, "requires_review": requires,
        "explanation": {"scores": scores, "supporting": [r.__dict__ for r in supporting], "conflicting": [r.__dict__ for r in conflicting]},
    }
''')

print("part3 done")
