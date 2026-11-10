"""Tests for the repair_override() first-stage inference rule."""
import pytest

from backend.app.diagnosis.xgb_classifier import repair_override


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
