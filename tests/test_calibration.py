"""Tests for scripts/calibration.py (out-of-fold temperature + abstain threshold).

The point of the module is that the threshold stops being a coin flip on 45 rows,
so the tests pin: the selection rule, determinism, cluster-level resampling,
the "temperature only if it helps" rule, and the honest fallbacks.
"""
from __future__ import annotations

import numpy as np
import pytest

from scripts.calibration import (
    TARGET_PRECISION,
    bootstrap_threshold,
    calibrate_variant,
    expected_calibration_error,
    fit_temperature_if_it_helps,
    rescale,
    risk_coverage,
    select_threshold,
    stack,
)


def _confident_when_right(n=400, k=4, seed=0):
    """Synthetic OOF probs where confidence tracks correctness (a calibrated-ish model)."""
    rng = np.random.default_rng(seed)
    y = rng.integers(0, k, n)
    probs = np.full((n, k), 0.0)
    for i in range(n):
        right = rng.random() < 0.8
        top = y[i] if right else (y[i] + 1) % k
        conf = rng.uniform(0.6, 0.95) if right else rng.uniform(0.25, 0.55)
        probs[i] = (1 - conf) / (k - 1)
        probs[i, top] = conf
    return probs, y


def test_rescale_is_a_distribution_and_t1_is_identity():
    probs, _ = _confident_when_right(50)
    np.testing.assert_allclose(rescale(probs, 1.0), probs, atol=1e-9)
    scaled = rescale(probs, 2.0)
    np.testing.assert_allclose(scaled.sum(axis=1), 1.0, atol=1e-9)
    assert scaled.max(axis=1).mean() < probs.max(axis=1).mean()   # T > 1 softens


def test_ece_of_a_perfectly_calibrated_toy_is_small_and_of_an_overconfident_one_is_large():
    y = np.array([0] * 10)
    right = np.tile([0.9, 0.1], (9, 1))
    wrong = np.array([[0.1, 0.9]])
    assert expected_calibration_error(np.vstack([right, wrong]), y) < 0.01
    assert expected_calibration_error(np.tile([0.99, 0.01], (10, 1)), np.array([1] * 10)) > 0.9


def test_temperature_is_applied_only_when_it_lowers_ece():
    probs, y = _confident_when_right()
    fit = fit_temperature_if_it_helps(probs, y)
    assert fit["applied"] == (fit["ece_at_nll_optimal"] < fit["ece_raw"])
    if not fit["applied"]:
        assert fit["temperature"] == 1.0
    over = np.tile([0.97, 0.01, 0.01, 0.01], (200, 1))          # always wrong but very sure
    over_y = np.ones(200, dtype=int)
    softened = fit_temperature_if_it_helps(over, over_y)
    assert softened["applied"] and softened["temperature"] > 1.0


def test_select_threshold_returns_the_smallest_grid_value_reaching_the_target():
    probs, y = _confident_when_right(2000, seed=1)
    conf, correct = probs.max(axis=1), probs.argmax(axis=1) == y
    real = np.ones(len(y), dtype=bool)
    chosen = select_threshold(conf, correct, real, 0.9)
    t = chosen["threshold"]
    assert chosen["reached"] and t is not None
    assert correct[conf >= t].mean() >= 0.9
    lower = round(t - 0.01, 2)
    assert correct[conf >= lower].mean() < 0.9 or lower < 0.10


def test_threshold_never_exists_for_an_unreachable_target():
    conf = np.full(100, 0.5)
    correct = np.zeros(100, dtype=bool)
    assert select_threshold(conf, correct, np.ones(100, dtype=bool), 0.8)["threshold"] is None


def test_real_rows_decide_the_threshold_when_there_are_enough_and_all_rows_when_not():
    rng = np.random.default_rng(2)
    conf = rng.uniform(0.2, 0.95, 600)
    correct = rng.random(600) < conf                    # accurate roughly as confident
    few_real = np.zeros(600, dtype=bool)
    few_real[:10] = True
    assert select_threshold(conf, correct, few_real, 0.8)["population"].startswith("all_rows")
    many_real = np.zeros(600, dtype=bool)
    many_real[:200] = True
    assert select_threshold(conf, correct, many_real, 0.8)["population"] == "non_synthetic"


def test_risk_coverage_is_monotone_in_coverage():
    probs, y = _confident_when_right(500, seed=3)
    conf, correct = probs.max(axis=1), probs.argmax(axis=1) == y
    table = risk_coverage(conf, correct, np.ones(len(y), dtype=bool))
    coverage = [r["coverage_all"] for r in table]
    assert coverage == sorted(coverage, reverse=True)


def test_stack_repeats_labels_and_aligned_arrays():
    a, b = np.ones((3, 2)), np.zeros((3, 2))
    probs, y, extra = stack([a, b], np.array([0, 1, 0]), np.array([5, 6, 7]))
    assert probs.shape == (6, 2) and list(y) == [0, 1, 0, 0, 1, 0] and list(extra) == [5, 6, 7, 5, 6, 7]


def test_bootstrap_resamples_whole_clusters_and_is_seeded():
    probs, y = _confident_when_right(600, seed=4)
    cluster = np.repeat(np.arange(60), 10)
    real = np.ones(len(y), dtype=bool)
    a = bootstrap_threshold(probs, y, cluster, real, 0.8, seed=11, resamples=40)
    b = bootstrap_threshold(probs, y, cluster, real, 0.8, seed=11, resamples=40)
    assert a == b and len(a) > 0
    c = bootstrap_threshold(probs, y, cluster, real, 0.8, seed=12, resamples=40)
    assert a != c


def test_calibrate_variant_record_is_complete_and_honest():
    probs, y = _confident_when_right(480, seed=5)
    cluster = np.repeat(np.arange(48), 10)
    real = np.arange(len(y)) % 2 == 0
    rec = calibrate_variant([probs, probs], y, cluster, real, seed=7)
    assert rec["isotonic_used"] is False
    assert rec["target_precision"] == TARGET_PRECISION
    assert 0.0 < rec["threshold"] <= 1.0 and rec["temperature"] > 0
    assert rec["bootstrap"]["p05"] <= rec["bootstrap"]["p95"]
    assert rec["fitted_on"] == {"rows": 480, "repeats": 2, "clusters": 48, "non_synthetic_rows": 240}
    assert set(rec["sensitivity_threshold_by_target_precision"]) == {"0.7", "0.9"}
    assert "agreement with row labels" in rec["caveat"]
    again = calibrate_variant([probs, probs], y, cluster, real, seed=7)
    assert again == rec


def test_unreachable_target_falls_back_to_a_neutral_threshold_not_a_crash():
    n = 300
    probs = np.tile([0.5, 0.5], (n, 1))
    y = np.zeros(n, dtype=int)
    y[::2] = 1                                          # exactly half right at best
    rec = calibrate_variant([probs], y, np.repeat(np.arange(30), 10), np.ones(n, dtype=bool), seed=1)
    assert rec["target_reached_on_full_sample"] is False
    assert rec["threshold"] == pytest.approx(0.5)
