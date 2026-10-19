"""Problem clustering + cluster split tests (master plan §13.4, R-I4).

Task 6 delivers the Week-0 dependency that unblocks Eman's train-side
reverse-mutation mining: cluster CodeStream problems by TF-IDF statement
cosine > 0.8, then split whole clusters into train-side / dev-gold / test-side.

Binding rules (§13.4):
- clusters, not raw problems, since TF-IDF clustering shrinks the count;
- split budget: train >=21, dev-gold 5, test 15 (needs >=41 clusters);
- fallback when clustering yields <36 total: dev-gold 4, test 12 (gold spans
  >=10), the 150 floor protected first;
- clusters split only as a unit — a test-side cluster's problems (and any
  mutant seeded from them) never reach training;
- clustering is deterministic (same statements -> same clusters + split).

The connected-components step is tested directly via clusters_from_similarity
with a hand-built matrix (including an A~B, B~C, A!~C chain that must form one
cluster — single-linkage, the leakage-safe grouping). TF-IDF is tested via
cluster_problems on controlled statements.
"""

from __future__ import annotations

from pathlib import Path

from scripts.cluster_problems import (
    assign_splits,
    cluster_problems,
    clusters_from_similarity,
    split_budget,
)

_IDENTICAL = (
    "In this problem you are given a string of alphabets and spaces. "
    "To preserve privacy you must cipher the string by shifting every "
    "letter forward by one position while leaving spaces untouched. "
    "Output the transformed string on a single line. The input may "
    "contain upper and lower case letters. Read the whole line including "
    "trailing spaces. Print exactly the ciphered text. "
)

_A = _IDENTICAL + "aaa1"
_B = _IDENTICAL + "aaa2"  # near-identical to _A -> cosine > 0.8
_DIFFERENT = (
    "Given an undirected graph with n vertices and m edges, determine "
    "whether it contains a cycle. The first line holds n and m. Each of "
    "the next m lines describes an edge between two vertices numbered "
    "from one. Output YES if a cycle exists, otherwise NO. The graph may "
    "be disconnected. Use union find or depth first search to detect the "
    "back edge efficiently. "
)


# ------------------------------------------- connected components (pure)


def test_identical_rows_form_one_cluster():
    ids = ["p1", "p2", "p3"]
    sim = [
        [1.0, 1.0, 0.0],
        [1.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    out = clusters_from_similarity(ids, sim, threshold=0.8)
    assert out["p1"] == out["p2"]
    assert out["p1"] != out["p3"]


def test_transitive_chain_forms_one_cluster():
    # p1~p2 (>0.8), p2~p3 (>0.8), but p1!p3 (<0.8) — single-linkage must
    # still group all three so a near-duplicate family never straddles splits.
    ids = ["p1", "p2", "p3"]
    sim = [
        [1.0, 0.9, 0.1],
        [0.9, 1.0, 0.9],
        [0.1, 0.9, 1.0],
    ]
    out = clusters_from_similarity(ids, sim, threshold=0.8)
    assert out["p1"] == out["p2"] == out["p3"]


def test_threshold_is_strictly_greater_than():
    # cosine exactly == threshold is NOT a link (plan says "> 0.8").
    ids = ["p1", "p2"]
    sim = [[1.0, 0.8], [0.8, 1.0]]
    out = clusters_from_similarity(ids, sim, threshold=0.8)
    assert out["p1"] != out["p2"]


def test_diagonal_only_matrix_yields_all_singletons():
    ids = ["p1", "p2", "p3"]
    sim = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    out = clusters_from_similarity(ids, sim, threshold=0.8)
    assert len(set(out.values())) == 3


def test_cluster_ids_are_clu_prefixed_and_deterministic():
    ids = ["p2", "p1"]
    sim = [[1.0, 1.0], [1.0, 1.0]]
    out1 = clusters_from_similarity(ids, sim, threshold=0.8)
    out2 = clusters_from_similarity(list(reversed(ids)), [[1.0, 1.0], [1.0, 1.0]], threshold=0.8)
    assert set(out1.values()) == {"clu-000"}
    assert out1 == out2  # input order does not change assignment


# ------------------------------------------------------- TF-IDF wrapper


def test_cluster_problems_merges_identical_statements():
    out = cluster_problems({"p1": _IDENTICAL, "p2": _IDENTICAL})
    assert out["p1"] == out["p2"]


def test_cluster_problems_separates_dissimilar_statements():
    out = cluster_problems({"p1": _IDENTICAL, "p2": _DIFFERENT})
    assert out["p1"] != out["p2"]


def test_cluster_problems_is_deterministic():
    stmts = {"p1": _A, "p2": _B, "p3": _DIFFERENT}
    assert cluster_problems(stmts) == cluster_problems(dict(reversed(list(stmts.items()))))


def test_cluster_problems_empty_input():
    assert cluster_problems({}) == {}


def test_cluster_problems_blank_statement_is_own_cluster():
    out = cluster_problems({"p1": "", "p2": _IDENTICAL})
    assert out["p1"] != out["p2"]


# ----------------------------------------------------------- split budget


def test_split_budget_full_when_enough_clusters():
    train_min, dev, test, fallback = split_budget(41)
    assert (train_min, dev, test, fallback) == (21, 5, 15, False)


def test_split_budget_more_than_enough_still_full():
    assert split_budget(50)[3] is False


def test_split_budget_fallback_below_full():
    # <41 clusters cannot meet the 21+5+15=41 full budget -> fallback mode.
    train_min, dev, test, fallback = split_budget(35)
    assert (dev, test, fallback) == (4, 12, True)


def test_split_budget_fallback_boundary_40():
    # 40 clusters: full 41 unmet -> fallback (test 12 keeps gold span invariant).
    assert split_budget(40)[1:4] == (4, 12, True)


def test_split_budget_fallback_boundary_37_keeps_train_floor():
    # 37 clusters in fallback: 12 test + 4 dev leaves train = 21 (>= floor).
    assert split_budget(37)[1:4] == (4, 12, True)


# -------------------------------------------------------------- splits


def _split_counts(splits: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in splits.values():
        counts[s] = counts.get(s, 0) + 1
    return counts


def test_assign_splits_full_budget_counts():
    cids = [f"clu-{i:03d}" for i in range(41)]
    splits, fallback = assign_splits(cids, seed=13)
    counts = _split_counts(splits)
    assert counts == {"test": 15, "dev_gold": 5, "train": 21}
    assert fallback is False


def test_assign_splits_fallback_counts():
    cids = [f"clu-{i:03d}" for i in range(35)]
    splits, fallback = assign_splits(cids, seed=13)
    counts = _split_counts(splits)
    assert counts["test"] == 12
    assert counts["dev_gold"] == 4
    assert counts["train"] == 19  # 35 - 12 - 4; below 21 -> warned, not fatal
    assert fallback is True


def test_assign_splits_deterministic_given_seed():
    cids = [f"clu-{i:03d}" for i in range(45)]
    assert assign_splits(cids, seed=13) == assign_splits(cids, seed=13)


def test_assign_splits_every_cluster_gets_a_split():
    cids = [f"clu-{i:03d}" for i in range(50)]
    splits, _ = assign_splits(cids, seed=13)
    assert set(splits) == set(cids)


def test_assign_splits_more_clusters_train_absorbs_extras():
    cids = [f"clu-{i:03d}" for i in range(46)]
    splits, _ = assign_splits(cids, seed=13)
    counts = _split_counts(splits)
    assert counts["test"] == 15
    assert counts["dev_gold"] == 5
    assert counts["train"] == 26  # 46 - 15 - 5


# ------------------------------------------------------- real CodeStream


def _real_problems_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "data" / "Data_from_Datasets" / "intermediate" / "normalized"
        / "problems" / "problems.csv"
    )


def test_real_codestream_statements_cluster_and_split():
    path = _real_problems_path()
    if not path.is_file():
        import pytest
        pytest.skip("normalized problems.csv not present")
    import csv

    stmts: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("dataset_source") == "CODESTREAM":
                stmts[row["problem_id"]] = row.get("statement") or row.get("title") or ""
    assert len(stmts) == 46

    clusters = cluster_problems(stmts)
    assert set(clusters) == set(stmts)
    cids = sorted(set(clusters.values()))
    splits, fallback = assign_splits(cids, seed=13)
    # every cluster assigned; test+dev+train cover all clusters
    assert set(splits) == set(cids)
    counts = _split_counts(splits)
    assert counts["test"] + counts["dev_gold"] + counts["train"] == len(cids)
    # budget honored for however many clusters we got
    if not fallback:
        assert counts["test"] == 15 and counts["dev_gold"] == 5
    else:
        assert counts["test"] == 12 and counts["dev_gold"] == 4
