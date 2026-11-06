"""Pure-logic tests for the real-data evaluation and baseline scripts.

Execution, g++ and the raw corpus are not needed here: those parts run on the
dataset machine (`scripts/eval_real_data.py`). What must never silently break
is the statistics and the plumbing around them.
"""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from scripts.eval_baselines import columns_for, folds
from scripts.eval_real_data import (
    bootstrap_ci,
    consecutive_failed_pairs,
    expected_chance_agreement,
    flatten_blocks,
    paired_difference_ci,
    render_markdown,
)


def test_flatten_blocks_returns_only_requested_names_with_none_for_gaps():
    normalized = {"static": {"loc": 12, "flag": True}, "warnings": {"total": float("nan")}}
    out = flatten_blocks(normalized, ["static.loc", "static.flag", "warnings.total", "tests.total", "static.nope"])
    assert out == {"static.loc": 12, "static.flag": 1.0, "warnings.total": None, "tests.total": None, "static.nope": None}


def test_bootstrap_ci_brackets_the_point_estimate_and_is_seeded():
    by_problem = {f"p{i}": [1.0, 1.0, 0.0] for i in range(12)}
    a = bootstrap_ci(by_problem, random.Random(1))
    b = bootstrap_ci(by_problem, random.Random(1))
    assert a == b
    point, lo, hi = a
    assert point == pytest.approx(2 / 3)
    assert lo <= point <= hi


def test_bootstrap_resamples_problems_not_rows():
    # one problem all-fail, one all-pass: row-level resampling would give a
    # narrow interval, problem-level resampling must allow 0.0 and 1.0.
    by_problem = {"a": [0.0] * 50, "b": [1.0] * 50}
    _, lo, hi = bootstrap_ci(by_problem, random.Random(3))
    assert lo == 0.0 and hi == 1.0


def test_bootstrap_of_nothing_is_nan():
    assert all(math.isnan(x) for x in bootstrap_ci({}, random.Random(0)))


def test_paired_difference_detects_a_clear_gap():
    a = {f"p{i}": [1.0, 1.0] for i in range(10)}
    b = {f"p{i}": [0.0, 0.0] for i in range(10)}
    point, lo, hi = paired_difference_ci(a, b, random.Random(0))
    assert point == 1.0 and lo == 1.0 and hi == 1.0


def test_paired_difference_of_equal_arms_straddles_zero():
    rng = random.Random(5)
    a = {f"p{i}": [float(rng.random() < 0.5) for _ in range(6)] for i in range(15)}
    point, lo, hi = paired_difference_ci(a, a, random.Random(0))
    assert point == 0.0 and lo == 0.0 and hi == 0.0


def test_chance_agreement():
    assert expected_chance_agreement(["a", "a", "b", "b"]) == pytest.approx(0.5)
    assert expected_chance_agreement(["a"] * 4) == 1.0
    assert math.isnan(expected_chance_agreement([]))


def _row(user, problem, attempt, branch):
    return {"user_hash": user, "problem_id": problem, "attempt_number": attempt, "branch": branch}


def test_consecutive_failed_pairs_requires_adjacent_failing_attempts_of_one_student_and_problem():
    rows = [
        _row("u1", "p1", 1, "failing"), _row("u1", "p1", 2, "failing"), _row("u1", "p1", 3, "all_pass"),
        _row("u1", "p1", 5, "failing"),            # gap in attempt numbers: not adjacent to 3
        _row("u2", "p1", 1, "failing"),            # different student
        _row("u1", "p2", 1, "failing"), _row("u1", "p2", 2, "compile_error"),
    ]
    pairs = consecutive_failed_pairs(rows)
    assert [(a["attempt_number"], b["attempt_number"]) for a, b in pairs] == [(1, 2)]


def test_columns_for_selects_by_block_prefix():
    names = ["static.loc", "warnings.total", "semantics.loop_lt", "runtime.duration_s"]
    assert columns_for(names, ("static", "warnings")) == [0, 1]
    assert columns_for(names, ("runtime",)) == [3]


def test_folds_never_split_a_cluster_across_train_and_validation():
    y = np.array([0, 1] * 30)
    cluster = np.array([f"c{i // 3}" for i in range(60)])
    seen = 0
    for _rep, tr, va in folds(y, cluster, seed=1, repeats=2):
        assert not set(cluster[tr]) & set(cluster[va])
        seen += 1
    assert seen == 6


def test_report_renders_without_repairs_and_states_its_limits():
    report = {
        "pool": "dev_gold", "purpose": "DEVELOPMENT run", "at": "2026-11-06T00:00:00+00:00",
        "n_submissions": 3, "n_problems": 1, "n_users": 2, "router": {"failing": 3},
        "accepted_routed_to_model": 0, "accepted_total": 0,
        "models": {"best": {"sha256_16": "abc", "threshold": 0.3}},
        "variants": {"best": {"n_failing": 3, "abstain_rate": 0.0, "other_error_rate": 0.0,
                              "mean_missing_features": 0.0, "mean_top_probability": 0.5,
                              "per_problem": {"p1": {"CPP_ARRAY_BOUNDS": 3}}, "class_histogram": {"CPP_ARRAY_BOUNDS": 3},
                              "t2_evaluated": 3, "t2_coverage_of_failing": 1.0}},
    }
    text = render_markdown(report)
    assert "not accuracy" in text
    assert "DEVELOPMENT run" in text
