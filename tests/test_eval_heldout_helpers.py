"""Tests for the eval_heldout_rows helper functions added in fix/dataset-critique."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from eval_heldout_rows import concentration_warnings, problem_weighted_macro_f1

OTHER = "CPP_OTHER_ERROR"
LB = "CPP_LOOP_BOUNDARY"
OBO = "CPP_OFF_BY_ONE"


class TestProblemWeightedMacroF1:
    def test_equal_weight_regardless_of_row_count(self):
        # Problem A: 100 rows, perfect prediction. Problem B: 1 row, all wrong.
        # Row-weighted average would be ~1.0; problem-weighted should be ~0.5.
        truth = [LB] * 100 + [OBO]
        pred = [LB] * 100 + [LB]  # B misclassified
        problems = ["A"] * 100 + ["B"]
        score = problem_weighted_macro_f1(truth, pred, problems)
        # Problem A perfect (macro-F1 ~ 1.0 on {LB}), problem B all wrong (0.0).
        # Average ~ 0.5 (there is only one class per problem so macro == binary F1).
        assert 0.4 < score < 0.6

    def test_all_correct_gives_1(self):
        truth = [LB, OBO, OTHER]
        pred = [LB, OBO, OTHER]
        problems = ["A", "B", "C"]
        assert problem_weighted_macro_f1(truth, pred, problems) == pytest.approx(1.0, abs=0.01)

    def test_all_wrong_gives_0(self):
        truth = [LB, LB, LB]
        pred = [OBO, OBO, OBO]
        problems = ["A", "A", "A"]
        assert problem_weighted_macro_f1(truth, pred, problems) == pytest.approx(0.0, abs=0.01)

    def test_empty_returns_nan(self):
        import math
        result = problem_weighted_macro_f1([], [], [])
        assert math.isnan(result)

    def test_two_problems_one_correct(self):
        truth = [LB, LB, OBO, OBO]
        pred = [LB, LB, LB, LB]  # problem B all wrong
        problems = ["A", "A", "B", "B"]
        score = problem_weighted_macro_f1(truth, pred, problems)
        assert 0.3 < score < 0.7


class TestConcentrationWarnings:
    def test_no_warning_when_no_dominant_problem(self):
        # Ten problems of 10 rows each: every problem supplies 10 % (< 20 %).
        problems = [p for p in "ABCDEFGHIJ" for _ in range(10)]
        assert concentration_warnings(problems) == []

    def test_warning_when_one_problem_over_threshold(self):
        # 25 out of 100 = 25 % > 20 % threshold; the other 75 rows are spread over 15 problems (5 % each)
        problems = ["dominant"] * 25 + [f"other{i}" for i in range(15) for _ in range(5)]
        warnings = concentration_warnings(problems)
        assert len(warnings) == 1
        assert "dominant" in warnings[0]
        assert "25/100" in warnings[0]

    def test_empty_list_returns_empty(self):
        assert concentration_warnings([]) == []

    def test_single_problem_always_warns(self):
        # 10/10 = 100 % > threshold
        problems = ["solo"] * 10
        assert len(concentration_warnings(problems)) == 1

    def test_message_mentions_percent(self):
        problems = ["p39"] * 282 + ["other"] * 382
        warnings = concentration_warnings(problems)
        assert any("p39" in w and "%" in w for w in warnings)
