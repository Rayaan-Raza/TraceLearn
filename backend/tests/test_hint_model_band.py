"""A15: HintPolicy model confidence band → starting hint level tests.

High-confidence prediction (≥0.75, not abstained, not CPP_OTHER_ERROR) with a
level-2 hint available → start at level 2.
All other cases → start at level 1 (unchanged behaviour).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.app.hints.hint_policy import HintPolicy


def _pred(top_label="CPP_LOOP_BOUNDARY", top_prob=0.80, abstained=False):
    return SimpleNamespace(
        top_label=top_label,
        top_probability=top_prob,
        abstained=abstained,
    )


def _diag(mid="CPP_LOOP_BOUNDARY", no_misc=False, needs_review=False):
    d = MagicMock()
    from backend.app.diagnosis.taxonomy import NO_MISCONCEPTION
    d.primary_misconception = NO_MISCONCEPTION if no_misc else mid
    d.requires_teacher_review = needs_review
    return d


def _hint_levels_with_two(mid, levels):
    return (mid, levels)


class TestHintModelBand:
    def _select(self, pred, diag_mid="CPP_LOOP_BOUNDARY", levels=None):
        if levels is None:
            levels = {1: "generic hint", 2: "specific hint"}
        policy = HintPolicy()
        db = MagicMock()
        sub = MagicMock()
        sub.student_id = 1
        sub.id = 1
        sub.problem_id = "p1"
        diag = _diag(mid=diag_mid)

        with patch("backend.app.hints.hint_policy.hint_levels", return_value=(diag_mid, levels)):
            return policy.select_hint(db, sub, diag, pred)

    def test_high_confidence_uses_level_2(self):
        event = self._select(_pred(top_prob=0.80))
        assert event.hint_level == 2

    def test_exactly_at_threshold_uses_level_2(self):
        event = self._select(_pred(top_prob=0.75))
        assert event.hint_level == 2

    def test_below_threshold_uses_level_1(self):
        event = self._select(_pred(top_prob=0.74))
        assert event.hint_level == 1

    def test_abstained_uses_level_1(self):
        event = self._select(_pred(top_prob=0.90, abstained=True))
        assert event.hint_level == 1

    def test_other_error_uses_level_1(self):
        event = self._select(_pred(top_label="CPP_OTHER_ERROR", top_prob=0.90))
        assert event.hint_level == 1

    def test_no_prediction_uses_level_1(self):
        event = self._select(None)
        assert event.hint_level == 1

    def test_no_level_2_available_uses_level_1(self):
        event = self._select(_pred(top_prob=0.90), levels={1: "hint one"})
        assert event.hint_level == 1

    def test_level_text_is_correct_for_level_2(self):
        event = self._select(_pred(top_prob=0.80))
        assert event.hint_text == "specific hint"

    def test_no_misconception_returns_none(self):
        from backend.app.diagnosis.taxonomy import NO_MISCONCEPTION
        policy = HintPolicy()
        db = MagicMock()
        sub = MagicMock()
        diag = _diag(no_misc=True)
        result = policy.select_hint(db, sub, diag, _pred(top_prob=0.90))
        assert result is None
