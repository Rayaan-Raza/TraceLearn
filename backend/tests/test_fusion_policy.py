"""The fusion policy (`model_fusion`), history gating and when the model runs (docs/6-nov.md section 19)."""
from __future__ import annotations

import pytest

from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.config import settings
from backend.app.diagnosis import confidence
from backend.app.diagnosis.confidence import fuse_diagnosis, gate_longitudinal
from backend.app.diagnosis.taxonomy import NO_MISCONCEPTION, UNCERTAIN

DIAG = "DIAGNOSTIC_INCLUSIVE_UPPER_BOUND_FAIL"


def rec(source, code, mid=None, direction="support", weight=0.0, **details):
    return EvidenceRecord(source_type=source, evidence_code=code, direction=direction, weight=weight,
                          description=code, misconception_id=mid, details=details)


def model_says(mid, p=0.8):
    return rec("model", "MODEL_PREDICTION", mid, weight=round(p * 0.4, 4), top_probability=p)


def model_other(p=0.7):
    return rec("model", "MODEL_OTHER_ERROR", None, direction="neutral", top_probability=p)


def history(mid, age=0):
    return rec("history", "CROSS_PROBLEM_RECURRENCE", mid, age=age)


@pytest.fixture
def policy(monkeypatch):
    def set_(fusion="points", gate=True):
        monkeypatch.setattr(settings, "model_fusion", fusion)
        monkeypatch.setattr(settings, "history_needs_observed_support", gate)
    return set_


def test_history_alone_no_longer_names_a_misconception(policy):
    policy(gate=True)
    records = [rec("test", "TEST_HIDDEN_FAIL"), history("CPP_LOOP_BOUNDARY"), history("CPP_STALE_EXIT")]
    assert fuse_diagnosis(records)["primary"] in (NO_MISCONCEPTION, UNCERTAIN)


def test_history_still_strengthens_what_this_attempt_shows(policy):
    policy(gate=True)
    own = [rec("test", DIAG, "CPP_LOOP_BOUNDARY")]
    with_history = fuse_diagnosis(own + [history("CPP_LOOP_BOUNDARY")])
    alone = fuse_diagnosis(own)
    assert with_history["primary"] == "CPP_LOOP_BOUNDARY"
    assert with_history["primary_confidence"] > alone["primary_confidence"]


def test_gate_off_restores_the_old_behaviour(policy):
    policy(gate=False)
    records = [rec("test", "TEST_HIDDEN_FAIL"), history("CPP_LOOP_BOUNDARY"), history("CPP_LOOP_BOUNDARY", age=1)]
    assert len(gate_longitudinal(records)) == 1  # the gate itself still drops them
    assert fuse_diagnosis(records)["explanation"]["scores"].get("CPP_LOOP_BOUNDARY", 0) > 0
    policy(gate=True)
    assert fuse_diagnosis(records)["explanation"]["scores"].get("CPP_LOOP_BOUNDARY", 0) == 0


def test_model_other_does_not_open_the_gate():
    records = [model_other(), history("CPP_LOOP_BOUNDARY")]
    assert [r.evidence_code for r in gate_longitudinal(records)] == ["MODEL_OTHER_ERROR"]


def test_points_policy_keeps_the_rules_vote(policy):
    policy("points")
    records = [rec("static", "CPP_ARRAY_AT_SIZE", "CPP_ARRAY_BOUNDS"), rec("test", DIAG, "CPP_ARRAY_BOUNDS"),
               model_says("CPP_OFF_BY_ONE", 0.6)]
    assert fuse_diagnosis(records)["primary"] == "CPP_ARRAY_BOUNDS"


def test_model_first_named_class_decides(policy):
    policy("model_first")
    records = [rec("static", "CPP_ARRAY_AT_SIZE", "CPP_ARRAY_BOUNDS"), rec("test", DIAG, "CPP_ARRAY_BOUNDS"),
               model_says("CPP_OFF_BY_ONE", 0.6)]
    out = fuse_diagnosis(records)
    assert out["primary"] == "CPP_OFF_BY_ONE"
    assert out["primary_confidence"] == pytest.approx(0.6)
    assert out["alternative"] == "CPP_ARRAY_BOUNDS"
    assert out["requires_review"] is False
    assert out["explanation"]["policy"] == "model_first"


def test_model_first_other_error_overrules_modelled_rules(policy):
    policy("model_first")
    records = [rec("test", DIAG, "CPP_LOOP_BOUNDARY"), model_other()]
    out = fuse_diagnosis(records)
    assert out["primary"] == UNCERTAIN and out["requires_review"] is True


def test_model_first_other_error_keeps_rule_only_misconceptions(policy):
    policy("model_first")
    records = [rec("static", "STATIC_NO_RETURN", "M03_MISSING_RETURN"),
               rec("test", "DIAGNOSTIC_RETURN_VALUE_FAIL", "M03_MISSING_RETURN"), model_other()]
    assert fuse_diagnosis(records)["primary"] == "M03_MISSING_RETURN"


def test_model_first_abstention_falls_back_to_points(policy):
    policy("model_first")
    abstained = rec("model", "MODEL_ABSTAINED", None, direction="neutral", top_probability=0.3)
    records = [rec("static", "CPP_ARRAY_AT_SIZE", "CPP_ARRAY_BOUNDS"), rec("test", DIAG, "CPP_ARRAY_BOUNDS"), abstained]
    assert fuse_diagnosis(records)["primary"] == "CPP_ARRAY_BOUNDS"


def test_model_first_never_overrides_all_tests_passed(policy):
    policy("model_first")
    records = [rec("test", "TEST_ALL_PASSED", direction="neutral"), model_says("CPP_OFF_BY_ONE", 0.9)]
    assert fuse_diagnosis(records)["primary"] == NO_MISCONCEPTION


def test_rule_only_set_matches_the_model_mapping():
    from backend.app.diagnosis.cpp_mapping import MODEL_LABEL_TO_BACKEND

    assert not set(MODEL_LABEL_TO_BACKEND.values()) & confidence.RULE_ONLY_MISCONCEPTIONS


def test_model_only_applies_to_failing_cpp():
    from backend.app.analysis.pipeline import AnalysisPipeline
    from backend.app.db.models import ExecutionStatus, Submission

    cpp = "#include <iostream>\nint main() { return 0; }\n"
    for status, expected in ((ExecutionStatus.SUCCESS, False), (ExecutionStatus.SYNTAX_ERROR, False),
                             (ExecutionStatus.SYSTEM_ERROR, False), (None, False),
                             (ExecutionStatus.WRONG_ANSWER, True), (ExecutionStatus.RUNTIME_ERROR, True)):
        assert AnalysisPipeline.model_applies(Submission(source_code=cpp, execution_status=status)) is expected
    assert AnalysisPipeline.model_applies(
        Submission(source_code="def f():\n    return 1\n", execution_status=ExecutionStatus.WRONG_ANSWER)) is False
