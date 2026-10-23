from collections import Counter

import pytest

pytest.importorskip("sklearn")

from cluster_codestream_problems import assign_pools, cluster_statements  # noqa: E402


def test_identical_statements_share_a_cluster():
    ids = ["p1", "p2", "p3"]
    texts = ["sum the numbers from one to n and print it",
             "sum the numbers from one to n and print it",
             "reverse a string of characters and print the result"]
    assign, pairs = cluster_statements(ids, texts)
    assert assign["p1"] == assign["p2"] != assign["p3"]
    assert len(pairs) == 1


def test_pool_split_is_seeded_and_respects_counts():
    fail = {f"c{i:02d}": 10 + i for i in range(40)}
    cfam = {k: v + 5 for k, v in fail.items()}
    a, notes, nt, nd = assign_pools(fail, cfam, seed=7, n_test=15, n_dev=5)
    b, *_ = assign_pools(fail, cfam, seed=7, n_test=15, n_dev=5)
    assert a == b
    c = Counter(a.values())
    assert c["test"] == 15 and c["dev_gold"] == 5 and c["train"] == 20
    assert notes == []


def test_fallback_below_36_clusters():
    fail = {f"c{i:02d}": 5 for i in range(27)}
    pools, notes, nt, nd = assign_pools(fail, dict(fail), seed=1, n_test=15, n_dev=5)
    c = Counter(pools.values())
    assert (nt, nd) == (12, 4) and c["test"] == 12 and c["dev_gold"] == 4
    assert notes and "fallback" in notes[0]


def test_clusters_without_failing_rows_go_to_train():
    fail = {f"c{i:02d}": 5 for i in range(20)} | {"empty": 0}
    cfam = dict(fail) | {"empty": 0}
    pools, *_ = assign_pools(fail, cfam, seed=3, n_test=12, n_dev=4)
    assert pools["empty"] == "train"
