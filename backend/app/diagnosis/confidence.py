from __future__ import annotations
import yaml
from pathlib import Path
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.config import settings
from backend.app.diagnosis.cpp_mapping import TAG_TO_CODE
from backend.app.diagnosis.rules import aggregate_scores
from backend.app.diagnosis.taxonomy import ALL_MISCONCEPTIONS, NO_MISCONCEPTION, UNCERTAIN

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
        "DIAGNOSTIC_CONFLICTING_OUTCOMES": w.get("conflicting_diagnostic", -0.20),
    }
    # The C++ static codes carry the same meaning as the Python strong
    # patterns, so they take the same named weight. They are listed here
    # rather than in the frozen YAML: the freeze protects the *values*, and
    # an unmapped code silently fell back to 0.05, which is why no C++ attempt
    # ever cleared the review threshold.
    for code in (
        "CPP_ASSIGN_IN_CONDITION", "CPP_LOOP_LE_BOUND", "CPP_ARRAY_AT_SIZE",
        "CPP_UNINIT_VAR", "CPP_INT_OVERFLOW_RISK", "CPP_MISSING_BASE_CASE",
        "CPP_GCC_UNINIT", "CPP_GCC_ASSIGN", "CPP_GCC_BOUNDS", "CPP_GCC_OVERFLOW",
    ):
        mapping[code] = w.get("static_strong", 0.30)
    # One entry per diagnostic tag of both banks. The tag tables live in
    # `cpp_mapping`, so a new bank tag picks up a weight without a change
    # here.
    for tags in TAG_TO_CODE.values():
        for tag in tags:
            mapping[f"DIAGNOSTIC_{tag.upper()}_FAIL"] = w.get("diagnostic_match", 0.35)
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
    conflict_diag = any(r.evidence_code == "DIAGNOSTIC_CONFLICTING_OUTCOMES" for r in weighted)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary, pscore = ranked[0]
    alt, ascore = ranked[1] if len(ranked) > 1 else (None, 0.0)
    pconf = clamp(pscore)
    aconf = clamp(ascore) if alt else None
    if any(r.evidence_code == "TEST_ALL_PASSED" for r in weighted):
        # Every test passed, including the diagnostic tests that target each
        # misconception. A code pattern or an earlier attempt alone cannot
        # outweigh that, so this is a confident "no misconception", not an
        # uncertain case for review. History still matters on failing attempts.
        return {
            "primary": NO_MISCONCEPTION,
            "primary_confidence": thresholds.get("no_misconception_confidence", 0.80),
            "alternative": None, "alternative_confidence": None,
            "uncertainty": "low", "requires_review": False,
            "explanation": {"scores": scores, "supporting": [], "conflicting": []},
        }
    if pconf < 0.05:
        primary, pconf = NO_MISCONCEPTION, 0.2
    conflict = any(r.direction == "conflict" and r.weight for r in weighted)
    if pconf < review_conf or (alt and abs(pconf - (aconf or 0)) < margin) or conflict:
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
    if conflict_diag:
        uncertainty = "high"
        requires = True
    supporting = [r for r in weighted if r.direction == "support" and r.weight]
    conflicting = [r for r in weighted if r.direction == "conflict" and r.weight]
    return {
        "primary": primary, "primary_confidence": pconf,
        "alternative": alt if alt and ascore > 0.05 else None,
        "alternative_confidence": aconf,
        "uncertainty": uncertainty, "requires_review": requires,
        "explanation": {"scores": scores, "supporting": [r.__dict__ for r in supporting], "conflicting": [r.__dict__ for r in conflicting]},
    }
