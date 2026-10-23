from adjudicate_gold import cohen_kappa, fleiss_kappa, majority


def test_fleiss_perfect_and_chance():
    assert fleiss_kappa([["A"] * 4, ["B"] * 4, ["A"] * 4]) == 1.0
    # Wikipedia's worked example gives κ ≈ 0.210
    rows = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
            [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    table = [[str(c) for c, k in enumerate(r) for _ in range(k)] for r in rows]
    assert abs(fleiss_kappa(table) - 0.210) < 0.001


def test_cohen():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == 0.0


def test_majority_rules():
    assert majority(["A", "A", "B", "A"]) == "A"
    assert majority(["A", "A", "B", "B"]) == "UNCERTAIN"
    assert majority(["A", "B", "C"]) == "UNCERTAIN"
    assert majority(["A", "A", "B"]) == "A"
