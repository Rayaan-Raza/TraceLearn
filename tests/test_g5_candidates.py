"""The confirmatory-set candidate rule (Gate 5): exclusions, eligibility and the fixed order."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import g5_candidates as g5  # noqa: E402

ATCODER = ('<span class="lang-ja">日本語</span><span class="lang-en"><p>Score : <var>300</var> points</p>'
           '<h3>Problem Statement</h3><p>Print the sum.</p><h3>Sample Input 1</h3><pre>1 2</pre>'
           '<h3>Sample Output 1</h3><pre>3</pre><h3>Sample Input 2</h3><pre>2 2</pre></span>')
AOJ_EN = "<h1>Dudeney Number</h1><p>Write a program that reads n.</p><h2>Sample Input</h2><pre>5</pre>"
AOJ_JA = "<h1>問題</h1><p>整数を読み込んで和を出力するプログラムを作成してください。</p><h2>Sample Input</h2>"


def test_codenet_ids_are_normalised():
    assert g5.codenet_id("tl-codenet-p02594") == "p02594"
    assert g5.codenet_id("p03012") == "p03012"
    assert g5.codenet_id("tl-codestream-prob_029") is None
    assert g5.codenet_id(None) is None


def test_statement_facts():
    a = g5.describe(ATCODER)
    assert (a["source"], a["atcoder_score"], a["samples"]) == ("AtCoder", 300, 2)
    assert a["english_share"] == 1.0                      # the Japanese span is not counted
    b = g5.describe(AOJ_EN)
    assert (b["source"], b["title"], b["samples"], b["english_share"]) == ("AOJ", "Dudeney Number", 1, 1.0)
    assert g5.describe(AOJ_JA)["english_share"] < g5.ENGLISH_SHARE


def test_eligibility_rule_and_its_reasons():
    used = {"p02594": ["labels.jsonl"]}
    en = g5.describe(AOJ_EN)
    assert g5.eligibility("p02594", en, 5000, used) == (False, "used: labels.jsonl")
    assert g5.eligibility("p00001", None, 5000, used) == (False, "no statement")
    assert g5.eligibility("p00001", g5.describe(AOJ_JA), 5000, used)[1].startswith("statement not in English")
    assert g5.eligibility("p00001", {**en, "samples": 0}, 5000, used) == (False, "no sample in the statement")
    assert g5.eligibility("p00001", en, 99, used)[0] is False
    assert g5.eligibility("p00001", en, 100, used) == (True, "eligible")


def test_order_is_fixed_by_the_seed_and_ignores_input_order():
    ids = ["p00027", "p00379", "p03451", "p03857", "p02464"]
    first = g5.order(ids)
    assert first == g5.order(list(reversed(ids)))
    assert sorted(first) == sorted(ids)
    assert g5.order(ids, seed=1) != first or len(ids) < 3


def test_every_codenet_problem_the_project_used_is_excluded():
    used = g5.used_problem_ids()
    for pid in ("p02594", "p02607", "p02633", "p02708", "p02742", "p02766",
                "p02887", "p02981", "p03012", "p03632", "p03803"):
        assert pid in used, pid
    assert any("reference" in w for w in used["p02766"])


def test_the_committed_list_matches_the_rule():
    import csv
    rows = list(csv.DictReader((ROOT / "data" / "misconception_dataset" / "confirmatory" / "candidates_v1.csv")
                               .open(encoding="utf-8")))
    used = g5.used_problem_ids()
    eligible = [r for r in rows if r["eligible"] == "True"]
    assert not any(r["problem_id"] in used for r in eligible)
    assert [int(r["rank"]) for r in eligible] == list(range(1, len(eligible) + 1))
    assert [r["problem_id"] for r in eligible] == g5.order([r["problem_id"] for r in eligible])
