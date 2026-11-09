"""Pure-logic tests for the blind-test scorer (metrics must be right before they are believed)."""
from __future__ import annotations

import math

import pytest

from scripts.eval_blind_test import ABSTAIN, OTHER, bootstrap_macro_f1, macro_f1, model_prediction, summarize, wilson

RC, OB = "CPP_RANGE_CHECK", "CPP_OFF_BY_ONE"


def test_wilson_interval_brackets_the_rate_and_handles_empty():
    lo, hi = wilson(5, 20)
    assert lo < 0.25 < hi and 0 <= lo and hi <= 1
    assert all(math.isnan(x) for x in wilson(0, 0))
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == 1.0


def test_macro_f1_counts_abstention_as_a_miss():
    truth = [OTHER, OTHER, RC, RC]
    assert macro_f1(truth, [OTHER, OTHER, RC, RC]) == 1.0
    assert macro_f1(truth, [OTHER, OTHER, ABSTAIN, ABSTAIN]) == pytest.approx(0.5)   # OTHER f1 1.0, RC 0


def test_false_alarm_and_precision_definitions():
    truth = [OTHER, OTHER, OTHER, OTHER, RC, RC, OB]
    pred = [OTHER, RC, OB, ABSTAIN, RC, OTHER, OB]
    s = summarize(truth, pred)
    assert (s["false_alarm_rate"]["k"], s["false_alarm_rate"]["n"]) == (2, 4)          # RC and OB on OTHER items
    assert (s["precision_when_flagged"]["k"], s["precision_when_flagged"]["n"]) == (2, 4)  # RC, OB, RC, OB flagged; RC and OB right
    assert (s["misconception_recall"]["k"], s["misconception_recall"]["n"]) == (2, 3)
    assert s["abstain_rate"]["k"] == 1
    assert s["per_class"][RC] == {"support": 2, "predicted": 2, "correct": 1, "precision": 0.5, "recall": 0.5}


def test_always_other_baseline_has_no_false_alarms_and_no_recall():
    truth = [OTHER, RC, OB, OTHER]
    s = summarize(truth, [OTHER] * 4)
    assert s["false_alarm_rate"]["k"] == 0 and s["misconception_recall"]["k"] == 0
    assert s["precision_when_flagged"]["value"] is None


def test_model_prediction_maps_abstention():
    assert model_prediction(RC, True) == ABSTAIN and model_prediction(RC, False) == RC


def test_bootstrap_resamples_problems_and_is_seeded():
    truth = [OTHER, RC] * 10
    pred = [OTHER, RC] * 10
    groups = [f"p{i // 2}" for i in range(20)]
    a = bootstrap_macro_f1(truth, pred, groups)
    assert a == bootstrap_macro_f1(truth, pred, groups) == [1.0, 1.0]
