"""Pure-logic tests for the shift, review-queue and weak-OTHER tooling."""
from __future__ import annotations

import numpy as np

from scripts.build_other_review_queue import sample_queue
from scripts.eval_shift import adversarial_auc, single_feature_separation, verdict


def _index(n_problems=4, per=20):
    rows = []
    for p in range(n_problems):
        for i in range(per):
            rows.append({"submission_id": f"s{p}-{i}", "problem_id": f"p{p}", "problem_cluster": f"c{p}",
                         "split_pool": "train" if p < 3 else "test", "decision": "no_fire" if i % 4 else "weak_rule"})
    return rows


def test_queue_uses_only_train_no_fire_rows_and_caps_each_problem():
    picked = sample_queue(_index(), per_problem=5)
    assert {r["problem_id"] for r in picked} == {"p0", "p1", "p2"}          # p3 is a test cluster
    assert all(r["decision"] == "no_fire" and r["split_pool"] == "train" for r in picked)
    assert max(sum(1 for r in picked if r["problem_id"] == f"p{p}") for p in range(3)) == 5


def test_queue_is_deterministic_for_a_seed_and_differs_across_seeds():
    a = [r["submission_id"] for r in sample_queue(_index(), 5, seed=1)]
    b = [r["submission_id"] for r in sample_queue(_index(), 5, seed=1)]
    c = [r["submission_id"] for r in sample_queue(_index(), 5, seed=2)]
    assert a == b and a != c


def test_adversarial_auc_is_high_for_different_populations_and_near_half_for_identical_ones():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, (120, 5))
    far = rng.normal(4, 1, (120, 5))
    same = rng.normal(0, 1, (120, 5))
    groups_a, groups_far = np.repeat(np.arange(12), 10), np.repeat(np.arange(100, 112), 10)
    assert adversarial_auc(a, far, groups_a, groups_far)["auc"] > 0.95
    assert adversarial_auc(a, same, groups_a, groups_far)["auc"] < 0.7


def test_single_feature_separation_ranks_the_shifted_column_first():
    rng = np.random.default_rng(1)
    a = rng.normal(0, 1, (80, 3))
    b = rng.normal(0, 1, (80, 3))
    b[:, 1] += 3.0
    top = single_feature_separation(a, b, ["x", "shifted", "z"])
    assert top[0]["feature"] == "shifted" and top[0]["distance"] > 0.4


def test_shift_gate_thresholds():
    assert verdict(0.7) == "pass" and verdict(0.8) == "warn" and verdict(0.9) == "FAIL"
