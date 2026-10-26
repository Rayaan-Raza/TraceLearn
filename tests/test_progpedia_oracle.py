"""PROGPedia oracle tests: generators, reference solvers, consensus rule."""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import progpedia_generators as gen  # noqa: E402
import progpedia_oracle_tests as oracle  # noqa: E402


def test_generators_are_deterministic_and_cover_every_kind():
    for pid in gen.GENERATORS:
        a = gen.plan_for(pid, 5)
        b = gen.plan_for(pid, 5)
        assert [t["input"] for t in a] == [t["input"] for t in b], pid
        assert {t["kind"] for t in a} == set(gen.KINDS)
        assert all(t["input"].endswith("\n") for t in a)


def test_generator_contracts():
    rng = random.Random(3)
    cic = gen.p0006(rng, "large").split()
    assert cic[-1] == "0" and cic.count(cic[-2]) == 1  # arrival place visited once
    assert len(set(cic[:-1])) <= 30
    a, b = gen.p0016(random.Random(4), "small").split()
    assert a <= b and len(a) <= 20 and len(b) <= 20
    seg = gen.p0042(random.Random(5), "large").split("\n")
    m = int(seg[0])
    pairs = [tuple(map(int, s.split())) for s in seg[2:] if s]
    reach, best = 0, 0
    for left, right in sorted(pairs):  # greedy cover check: [0, M] is coverable
        if left > reach:
            break
        best = max(best, right)
        if left <= reach:
            reach = max(reach, best)
    assert reach >= m
    n = int(gen.p0053(random.Random(6), "large").split()[0])
    assert n == 1500


def test_reference_solvers_on_statement_samples():
    assert gen.r0016("MPMCAC\nMPAMJ\n").strip() == "MA"
    assert gen.r0016("CCM\nCCMP\n").strip() == "Nenhum"
    assert gen.r0034("5\n2 4 2 3 1\n").strip() == "1 2 2 3 4"
    assert gen.r0035("4\n4 3 1 2\n").strip() == "5"
    assert gen.r0039("6\n12 3 17 5 34 33\n4\n1 51 41 21\n").split("\n")[:4] == ["8", "51", "39", "20 22"]
    assert gen.r0045("4\n2\n2 1\n3 2\n").strip() == "2"
    assert gen.r0045("5\n3\n3 2\n2 3\n1 4\n").strip() == "5"
    sample = "14\n11\n1 11\n7 11\n11 12\n12 2\n12 8\n3 13\n13 4\n13 14\n14 9\n14 5\n10 6\n"
    assert gen.r0048(sample).strip() == "3"


def test_inversions_reference_exceeds_int_range():
    big = gen.p0035(random.Random(1), "large")
    assert int(gen.r0035(big)) > 2**31 - 1


def test_consensus_rule():
    assert oracle.consensus(["5\n", "5 \n", "5\n"])[0] == "5\n"
    assert oracle.consensus(["5\n", None, None])[0] is None  # one oracle is not a consensus
    out, agree, done = oracle.consensus(["1\n", "1\n", "2\n", "3\n"])
    assert out is None and (agree, done) == (2, 4)  # 2/4 < 2/3
    assert oracle.consensus(["1 2\n", "1\n2\n", "1 2"])[0] is not None  # token-level agreement


def test_committed_oracle_tests_load_and_regenerate():
    usable = [p.name[:-8] for p in oracle.OUT_DIR.glob("*.json.gz")]
    assert len(usable) >= 10
    tests = oracle.load_tests("tl-progpedia-00000045")
    assert tests and any(t["kind"] == "large" for t in tests)
    big = [t for t in tests if t["kind"] == "large"][0]
    assert int(big["output"]) > 2**31  # pyramid paths: the INT_OVERFLOW stress test
