"""Tests for the repair_override() first-stage inference rule."""
import pytest

from backend.app.diagnosis.xgb_classifier import repair_override, rule_confidence


def _features(**kw) -> dict:
    """Build a minimal feature mapping with the given repair.{class}_fix_all values."""
    return {f"repair.{k.replace('_', '_')}_fix_all": float(v) for k, v in kw.items()}


class TestRepairOverride:
    def test_single_fix_all_returns_class(self):
        feats = {"repair.loop_boundary_fix_all": 1.0}
        assert repair_override(feats) == "CPP_LOOP_BOUNDARY"

    def test_multiple_fix_all_returns_none(self):
        feats = {
            "repair.loop_boundary_fix_all": 1.0,
            "repair.off_by_one_fix_all": 1.0,
        }
        assert repair_override(feats) is None

    def test_zero_fix_all_returns_none(self):
        feats = {
            "repair.loop_boundary_fix_all": 0.0,
            "repair.off_by_one_fix_all": 0.0,
        }
        assert repair_override(feats) is None

    def test_missing_feature_treated_as_non_fire(self):
        assert repair_override({}) is None

    def test_all_11_classes_covered(self):
        from backend.app.diagnosis.xgb_classifier import _REPAIR_FIX_ALL_FEATURES
        all_classes = {
            "CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS",
            "CPP_UNINITIALIZED_VAR", "CPP_INT_OVERFLOW", "CPP_MISSING_BASE_CASE",
            "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK",
        }
        assert set(_REPAIR_FIX_ALL_FEATURES.keys()) == all_classes

    @pytest.mark.parametrize("cls,feat", [
        ("CPP_OFF_BY_ONE", "repair.off_by_one_fix_all"),
        ("CPP_ARRAY_BOUNDS", "repair.array_bounds_fix_all"),
        ("CPP_INT_OVERFLOW", "repair.int_overflow_fix_all"),
        ("CPP_RANGE_CHECK", "repair.range_check_fix_all"),
        ("CPP_UNINITIALIZED_VAR", "repair.uninitialized_var_fix_all"),
        ("CPP_ASSIGN_VS_COMPARE", "repair.assign_vs_compare_fix_all"),
        ("CPP_WRONG_LOOP_DIR", "repair.wrong_loop_dir_fix_all"),
        ("CPP_MISSING_BASE_CASE", "repair.missing_base_case_fix_all"),
    ])
    def test_each_class_fires_when_its_feature_is_1(self, cls, feat):
        assert repair_override({feat: 1.0}) == cls

    def test_non_1_float_does_not_fire(self):
        assert repair_override({"repair.loop_boundary_fix_all": 0.5}) is None
        assert repair_override({"repair.loop_boundary_fix_all": 2.0}) is None


class TestNarrowRepairOverride:
    """Second-set repairs: only the few precise edits may name a class."""

    @staticmethod
    def _record(**classes) -> dict:
        return {"cf_narrow": {"classes": {f"CPP_{k}": v for k, v in classes.items()}}}

    def test_single_narrow_fix_returns_class(self):
        from backend.app.diagnosis.xgb_classifier import narrow_repair_override
        rec = self._record(RANGE_CHECK={"fix_all": 1, "ops": ["chained_compare_split_all"]},
                           OFF_BY_ONE={"fix_all": 0, "ops": ["output_-1_added"]})
        assert narrow_repair_override(rec) == "CPP_RANGE_CHECK"

    def test_an_edit_outside_the_narrow_list_is_ignored(self):
        from backend.app.diagnosis.xgb_classifier import narrow_repair_override
        rec = self._record(RANGE_CHECK={"fix_all": 1, "ops": ["if_any_cmp_>_to_>="]})
        assert narrow_repair_override(rec) is None

    def test_two_classes_fixing_everything_returns_none(self):
        from backend.app.diagnosis.xgb_classifier import narrow_repair_override
        rec = self._record(ARRAY_BOUNDS={"fix_all": 1, "ops": ["enlarge_every_array"]},
                           OFF_BY_ONE={"fix_all": 1, "ops": ["output_+1_added"]})
        assert narrow_repair_override(rec) is None

    @pytest.mark.parametrize("record", [None, {}, {"cf_narrow": None}, {"cf_narrow": {"classes": {}}},
                                        {"cf_narrow": {"classes": {"CPP_STALE_EXIT": {"fix_all": 1, "ops": []}}}}])
    def test_missing_or_empty_evidence_returns_none(self, record):
        from backend.app.diagnosis.xgb_classifier import narrow_repair_override
        assert narrow_repair_override(record) is None

    def test_first_set_proof_wins_in_predict_source(self, monkeypatch):
        from backend.app.analysis import model_runner
        feats = {"repair.loop_boundary_fix_all": 1.0}
        monkeypatch.setattr(model_runner, "code_features", lambda *a, **k: feats)
        rec = self._record(RANGE_CHECK={"fix_all": 1, "ops": ["chained_compare_split_all"]})
        pred = model_runner.predict_source("int main(){}", "cpp", None, rec)
        assert pred.top_label == "CPP_LOOP_BOUNDARY" and not pred.abstained

    def test_narrow_fix_names_the_class_when_no_first_set_proof(self, monkeypatch):
        from backend.app.analysis import model_runner
        monkeypatch.setattr(model_runner, "code_features", lambda *a, **k: {})
        rec = self._record(RANGE_CHECK={"fix_all": 1, "ops": ["chained_compare_split_all"]})
        pred = model_runner.predict_source("int main(){}", "cpp", None, rec)
        assert pred.top_label == "CPP_RANGE_CHECK" and not pred.abstained
        # A rule reports its measured precision, never certainty (Gate 2).
        assert pred.decision_source == "narrow_repair"
        assert pred.top_probability == rule_confidence("narrow_repair") < 1.0


class TestDecide:
    """Per-class bars lift a misconception out of the OTHER_ERROR majority, and nothing else."""

    CLASSES = ["CPP_INT_OVERFLOW", "CPP_LOOP_BOUNDARY", "CPP_OTHER_ERROR"]

    def _decide(self, probs, bars=None, threshold=0.44):
        from backend.app.diagnosis.xgb_classifier import decide
        idx, abstained = decide(probs, self.CLASSES, threshold, bars)
        return self.CLASSES[idx], abstained

    def test_without_bars_it_is_the_old_rule(self):
        assert self._decide([0.2, 0.1, 0.7]) == ("CPP_OTHER_ERROR", False)
        assert self._decide([0.4, 0.3, 0.3]) == ("CPP_INT_OVERFLOW", True)
        assert self._decide([0.5, 0.2, 0.3]) == ("CPP_INT_OVERFLOW", False)

    def test_a_class_clearing_its_bar_beats_other_error(self):
        assert self._decide([0.2, 0.1, 0.7], {"CPP_INT_OVERFLOW": 0.15}) == ("CPP_INT_OVERFLOW", False)

    def test_below_its_bar_other_error_stays(self):
        assert self._decide([0.1, 0.1, 0.8], {"CPP_INT_OVERFLOW": 0.15}) == ("CPP_OTHER_ERROR", False)

    def test_the_most_probable_cleared_class_is_chosen(self):
        bars = {"CPP_INT_OVERFLOW": 0.15, "CPP_LOOP_BOUNDARY": 0.15}
        assert self._decide([0.2, 0.3, 0.5], bars) == ("CPP_LOOP_BOUNDARY", False)

    def test_a_confident_named_top_class_is_not_displaced(self):
        assert self._decide([0.3, 0.6, 0.1], {"CPP_INT_OVERFLOW": 0.15}) == ("CPP_LOOP_BOUNDARY", False)

    def test_a_bar_replaces_the_global_threshold_for_its_class(self):
        assert self._decide([0.4, 0.3, 0.3], {"CPP_INT_OVERFLOW": 0.15}) == ("CPP_INT_OVERFLOW", False)
        assert self._decide([0.5, 0.2, 0.3], {"CPP_INT_OVERFLOW": 0.6}) == ("CPP_INT_OVERFLOW", True)


class TestEvidenceRules:
    """MISSING_BASE_CASE and WRONG_LOOP_DIR: rules, because real data cannot train or test them."""

    def test_infinite_recursion_warning_names_missing_base_case(self):
        from backend.app.diagnosis.xgb_classifier import evidence_rule_override
        assert evidence_rule_override({"warnings.infinite_recursion": 1.0}) == "CPP_MISSING_BASE_CASE"

    def test_base_case_repair_needs_recursion_and_a_crash_or_timeout(self):
        from backend.app.diagnosis.xgb_classifier import evidence_rule_override
        base = {"repair.missing_base_case_fix_all": 1.0, "semantics.recursion": 1.0}
        assert evidence_rule_override(base) is None
        assert evidence_rule_override({**base, "evidence.ff_crash": 1.0}) == "CPP_MISSING_BASE_CASE"
        assert evidence_rule_override({**base, "evidence.ff_timeout": 1.0}) == "CPP_MISSING_BASE_CASE"
        assert evidence_rule_override({"repair.missing_base_case_fix_all": 1.0, "evidence.ff_crash": 1.0}) is None

    def test_loop_direction_repair_wins_a_tie(self):
        from backend.app.diagnosis.xgb_classifier import evidence_rule_override, rule_override
        feats = {"repair.wrong_loop_dir_fix_all": 1.0, "repair.loop_boundary_fix_all": 1.0}
        assert evidence_rule_override(feats) == "CPP_WRONG_LOOP_DIR"
        assert rule_override(feats) == "CPP_WRONG_LOOP_DIR"

    def test_missing_or_unknown_evidence_names_nothing(self):
        from backend.app.diagnosis.xgb_classifier import evidence_rule_override
        for feats in ({}, {"warnings.infinite_recursion": None}, {"warnings.infinite_recursion": 0.0},
                      {"repair.wrong_loop_dir_fix_all": 0.0}, {"semantics.recursion": 1.0, "evidence.ff_crash": 1.0}):
            assert evidence_rule_override(feats) is None

    def test_a_lone_base_case_repair_is_left_to_the_model(self):
        from backend.app.diagnosis.xgb_classifier import rule_override
        assert rule_override({"repair.missing_base_case_fix_all": 1.0}) is None
        # another class's unique repair is still a proof
        assert rule_override({"repair.loop_boundary_fix_all": 1.0}) == "CPP_LOOP_BOUNDARY"

    def test_stage_order_rules_then_repair_then_narrow(self):
        from backend.app.diagnosis.xgb_classifier import rule_override
        narrow = {"cf_narrow": {"classes": {"CPP_RANGE_CHECK": {"fix_all": 1, "ops": ["chained_compare_split_all"]}}}}
        assert rule_override({}, narrow) == "CPP_RANGE_CHECK"
        assert rule_override({"repair.off_by_one_fix_all": 1.0}, narrow) == "CPP_OFF_BY_ONE"
        assert rule_override({"warnings.infinite_recursion": 1.0, "repair.off_by_one_fix_all": 1.0}, narrow) == "CPP_MISSING_BASE_CASE"


class TestDownwardLoopGuard:
    REC = {"cf_narrow": {"classes": {"CPP_WRONG_LOOP_DIR": {"fix_all": 1, "ops": ["for_run_downward"]}}}}

    def test_needs_a_reversed_output(self):
        from backend.app.diagnosis.xgb_classifier import rule_override
        assert rule_override({}, self.REC) is None
        assert rule_override({"evidence.reversed_tokens": 0.0}, self.REC) is None
        assert rule_override({"evidence.reversed_tokens": 1.0}, self.REC) == "CPP_WRONG_LOOP_DIR"
        assert rule_override({"evidence.reversed_lines": 1.0}, self.REC) == "CPP_WRONG_LOOP_DIR"

    def test_without_it_another_narrow_repair_still_counts(self):
        from backend.app.diagnosis.xgb_classifier import rule_override
        rec = {"cf_narrow": {"classes": {**self.REC["cf_narrow"]["classes"],
                                         "CPP_RANGE_CHECK": {"fix_all": 1, "ops": ["chained_compare_split_all"]}}}}
        assert rule_override({}, rec) == "CPP_RANGE_CHECK"
        assert rule_override({"evidence.reversed_tokens": 1.0}, rec) is None   # two narrow repairs: a tie
