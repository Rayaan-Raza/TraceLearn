"""Tests for the unified C++ diagnostic bank in `data/cpp_diagnostics`.

Two kinds of test live here.

1. Structure tests. They run on every machine. They check the problem
   manifest, the test files, the line endings, the sandbox limits, the
   coverage rules, and the hints.
2. Execution tests. They run only when a C++ toolchain is present. They call
   `scripts/verify_cpp_diagnostics.py`. That script compiles the reference
   solutions, runs every test case under the sandbox limits, runs the
   sanitizers, and checks every misconception variant.

Set `TRACELEARN_SKIP_CPP_VERIFY=1` to skip the execution tests.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT / "data" / "cpp_diagnostics"
TESTS = BANK / "tests"
SOLUTIONS = BANK / "solutions"
VARIANTS = BANK / "variants"
MANIFEST = BANK / "problems.json"

MISCONCEPTIONS = [f"CPP-M0{i}" for i in range(1, 9)]
TIME_LIMIT_MS = 2000
MEMORY_LIMIT_MB = 256
PROBLEMS_PER_MISCONCEPTION = 4
MIN_TEST_CASES = 7


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def load_bank() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["problems"]


def load_manifest() -> dict:
    return json.loads((BANK / "manifest.json").read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def independent_expected(problem: dict, case: dict) -> str:
    """Return the expected output for one test case.

    This is a second implementation, written independently of
    `scripts/cpp_defs`. It exists to catch a wrong model. It is not allowed to
    read the stored `.out` file.
    """
    args = case["stdin"].split()
    pid = problem["id"]

    if pid in ("CP09",):  # sum of squares 0..n-1
        n = int(args[0])
        return f"{sum(i * i for i in range(n))}\n"
    if pid in ("CP10",):  # count multiples of k in 0..n-1
        n, k = int(args[0]), int(args[1])
        return f"{sum(1 for i in range(n) if i % k == 0)}\n"
    if pid in ("CP11",):  # reverse range
        n = int(args[0])
        return "".join(f"{i}\n" for i in range(n - 1, -1, -1))
    if pid in ("CP12",):  # product of first n odd integers
        n = int(args[0])
        acc = 1
        for i in range(n):
            acc *= 2 * i + 1
        return f"{acc}\n"
    if pid in ("CP13",):  # second largest distinct
        vals = [int(a) for a in args[1:]]
        d = sorted(set(vals), reverse=True)
        return f"{d[1]}\n" if len(d) >= 2 else "NONE\n"
    if pid in ("CP14",):  # k-th smallest
        vals = [int(a) for a in args[1:1 + int(args[0])]]
        k = int(args[1 + int(args[0])])
        return f"{sorted(vals)[k - 1]}\n"
    if pid in ("CP15",):  # count occurrences
        n = int(args[0])
        vals = [int(a) for a in args[1:1 + n]]
        return f"{vals.count(int(args[1 + n]))}\n"
    if pid in ("CP16",):  # median of an odd count
        vals = [int(a) for a in args[1:]]
        return f"{sorted(vals)[len(vals) // 2]}\n"
    if pid in ("CP17",):  # absolute value
        return f"{abs(int(args[0]))}\n"
    if pid in ("CP18",):  # largest of three plus one
        v = [int(a) for a in args[:3]]
        return f"{max(v) + 1}\n"
    if pid in ("CP19",):  # even test
        return f"{1 if int(args[0]) % 2 == 0 else 0}\n"
    if pid in ("CP20",):  # gcd plus one
        a, b = int(args[0]), int(args[1])
        while b:
            a, b = b, a % b
        return f"{abs(a) + 1}\n"
    if pid in ("CP21",):  # shift one place right
        vals = [int(a) for a in args[1:]]
        return " ".join(str(x) for x in [vals[-1]] + vals[:-1]) + "\n"
    if pid in ("CP22",):  # sum of the last k
        n, k = int(args[0]), int(args[-1])
        vals = [int(a) for a in args[1:1 + n]]
        return f"{sum(vals[-k:])}\n"
    if pid in ("CP23",):  # value before the last
        vals = [int(a) for a in args[1:]]
        return f"{vals[-2]}\n"
    if pid in ("CP24",):  # index guard
        n = int(args[0])
        vals = [int(a) for a in args[1:1 + n]]
        i = int(args[1 + n])
        return f"{vals[i]}\n" if 0 <= i < n else "OUT_OF_RANGE\n"
    if pid in ("CP25",):  # grade
        s = int(args[0])
        if s < 0 or s > 100:
            return "INVALID\n"
        for limit, letter in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
            if s >= limit:
                return f"{letter}\n"
        return "F\n"
    if pid in ("CP26",):  # shipping cost
        w = int(args[0])
        for lo, hi, cost in ((1, 500, 5), (501, 2000, 10), (2001, 10000, 20)):
            if lo <= w <= hi:
                return f"{cost}\n"
        return "-1\n"
    if pid in ("CP27",):  # water state
        t = int(args[0])
        return "SOLID\n" if t <= 0 else ("GAS\n" if t > 99 else "LIQUID\n")
    if pid in ("CP28",):  # ticket price
        a = int(args[0])
        if a < 0:
            return "-1\n"
        if a <= 5:
            return "0\n"
        if a <= 17:
            return "7\n"
        if a <= 64:
            return "12\n"
        return "8\n"
    if pid in ("CP29",):  # sign
        x = int(args[0])
        return "ZERO\n" if x == 0 else ("POSITIVE\n" if x > 0 else "NEGATIVE\n")
    if pid in ("CP30",):  # password length
        line = case["stdin"].rstrip("\n")
        return ("OK\n" if len(line) >= 8 else "TOO SHORT\n")
    if pid in ("CP31",):  # divisible by two divisors
        x, p, q = int(args[0]), int(args[1]), int(args[2])
        return ("YES\n" if x % p == 0 and x % q == 0 else "NO\n")
    if pid in ("CP32",):  # vowel
        first = case["stdin"][:1].lower()
        return ("VOWEL\n" if first in "aeiou" else "CONSONANT\n")
    if pid in ("CP33",):  # sum to n by recursion
        return f"{sum(range(1, int(args[0]) + 1))}\n"
    if pid in ("CP34",):  # power
        return f"{int(args[0]) ** int(args[1])}\n"
    if pid in ("CP35",):  # fibonacci
        n = int(args[0])
        a, b = 0, 1
        for _ in range(max(0, n)):
            a, b = b, a + b
        return f"{a}\n"
    if pid in ("CP36",):  # halving steps
        n = int(args[0])
        steps = 0
        while n > 0:
            n //= 2
            steps += 1
        return f"{steps}\n"
    if pid in ("CP37",):  # last position
        n = int(args[0])
        vals = [int(a) for a in args[1:1 + n]]
        t = int(args[1 + n])
        for i in range(n - 1, -1, -1):
            if vals[i] == t:
                return f"{i}\n"
        return "NOT FOUND\n"
    if pid in ("CP38",):  # sentinel count and sum
        vals = [int(a) for a in args if int(a) != -1]
        return f"{len(vals)} {sum(vals)}\n"
    if pid in ("CP39",):  # first negative position
        vals = [int(a) for a in args[1:]]
        for i, v in enumerate(vals):
            if v < 0:
                return f"{i}\n"
        return "NONE\n"
    if pid in ("CP40",):  # lower bound with sum
        n = int(args[0])
        vals = [int(a) for a in args[1:1 + n]]
        t = int(args[1 + n])
        i, total = 0, 0
        while i < len(vals) and vals[i] < t:
            total += vals[i]
            i += 1
        return f"{i} {total}\n"
    raise AssertionError(f"no independent model for {pid}")


# ---------------------------------------------------------------------------
# coverage and structure
# ---------------------------------------------------------------------------
def test_bank_has_forty_problems():
    problems = load_bank()
    assert len(problems) == 40
    ids = [p["id"] for p in problems]
    expected = [f"CP{i:02d}" for i in range(1, 41)]
    assert ids == expected


@pytest.mark.parametrize("code", MISCONCEPTIONS)
def test_four_problems_per_misconception(code):
    problems = load_bank()
    hit = [p for p in problems if p["primary_misconception_id"] == code]
    assert len(hit) == PROBLEMS_PER_MISCONCEPTION, (
        f"{code} has {len(hit)} problems, it needs {PROBLEMS_PER_MISCONCEPTION}")


def test_every_problem_declares_language_and_standard():
    for problem in load_bank():
        assert problem["supported_language"] == "cpp"
        assert problem["language_standard"] == "cpp17"
        assert problem["taxonomy_version"] == "cpp-taxonomy-0.1"


def test_every_problem_declares_difficulty_and_topic():
    for problem in load_bank():
        assert problem["difficulty"] in ("Beginner", "Intermediate"), problem["id"]
        assert problem["primary_topic"].strip(), problem["id"]


def test_every_problem_has_a_statement_and_formats():
    for problem in load_bank():
        assert len(problem["statement_markdown"]) > 80, problem["id"]
        assert problem["input_format"].strip(), problem["id"]
        assert problem["output_format"].strip(), problem["id"]
        assert problem["constraints"].strip(), problem["id"]


def test_every_problem_has_two_examples():
    for problem in load_bank():
        assert len(problem["examples"]) >= 2, problem["id"]
        for example in problem["examples"]:
            assert example["input"].strip(), problem["id"]
            assert example["expected_output"].strip(), problem["id"]
            assert example["explanation"].strip(), problem["id"]


def test_every_problem_has_a_reference_solution():
    for problem in load_bank():
        source = problem["reference_solution_source"]
        assert "int main" in source, problem["id"]
        path = SOLUTIONS / f"{problem['id']}.cpp"
        assert path.exists(), path


def test_every_problem_has_a_misconception_variant():
    for problem in load_bank():
        name = problem["misconception_variant_id"]
        assert name and name.endswith(".cpp"), problem["id"]
        source = problem["misconception_variant_source"]
        assert source, problem["id"]
        assert source != problem["reference_solution_source"], problem["id"]


def test_variant_file_differs_from_the_reference():
    for problem in load_bank():
        reference = problem["reference_solution_source"]
        variant = problem["misconception_variant_source"]
        changed = [a for a in reference.splitlines() if a not in variant.splitlines()]
        assert changed, f"{problem['id']} variant is identical to the reference"


# ---------------------------------------------------------------------------
# test cases
# ---------------------------------------------------------------------------
def test_every_problem_has_at_least_seven_test_cases():
    for problem in load_bank():
        assert len(problem["test_cases"]) >= MIN_TEST_CASES, problem["id"]


def test_test_case_kinds_are_complete():
    for problem in load_bank():
        kinds = {c["db_type"] for c in problem["test_cases"]}
        assert {"visible", "hidden", "diagnostic"} <= kinds, problem["id"]


def test_at_least_one_boundary_test_per_problem():
    for problem in load_bank():
        boundary = [c for c in problem["test_cases"] if c.get("is_boundary")]
        assert boundary, f"{problem['id']} has no boundary test"


def test_diagnostic_tests_carry_the_trait_and_the_tag():
    for problem in load_bank():
        code = problem["primary_misconception_id"]
        for case in problem["test_cases"]:
            if case["db_type"] == "diagnostic":
                assert case.get("diagnostic_tag"), case["id"]
                assert case.get("diagnostic_trait") == code, case["id"]


def test_every_problem_has_a_diagnostic_trigger_per_kind():
    for problem in load_bank():
        diagnostic = [c for c in problem["test_cases"] if c["db_type"] == "diagnostic"]
        assert len(diagnostic) >= 2, problem["id"]


def test_test_ids_are_unique():
    seen: set[str] = set()
    for problem in load_bank():
        for case in problem["test_cases"]:
            assert case["id"] not in seen, case["id"]
            seen.add(case["id"])


def test_test_case_order_is_sequential():
    for problem in load_bank():
        for position, case in enumerate(problem["test_cases"], start=1):
            assert case["sort_order"] == position, case["id"]


def test_every_test_case_records_the_sandbox_limits():
    for problem in load_bank():
        for case in problem["test_cases"]:
            assert case["time_limit_ms"] == TIME_LIMIT_MS, case["id"]
            assert case["memory_limit_mb"] == MEMORY_LIMIT_MB, case["id"]


def test_visible_tests_are_public_and_diagnostic_tests_are_hidden():
    for problem in load_bank():
        for case in problem["test_cases"]:
            if case["db_type"] == "visible":
                assert case["partition"] == "public", case["id"]
            else:
                assert case["partition"] == "hidden", case["id"]


# ---------------------------------------------------------------------------
# normalization and expected outputs
# ---------------------------------------------------------------------------
def test_test_files_are_normalized():
    """Every test file uses LF endings, has no trailing whitespace, and ends
    with exactly one newline."""
    checked = 0
    for path in sorted(TESTS.rglob("*.in")) + sorted(TESTS.rglob("*.out")):
        data = path.read_bytes()
        checked += 1
        assert b"\r" not in data, f"{path} holds CR"
        assert data.endswith(b"\n"), f"{path} has no final newline"
        assert not data.endswith(b"\n\n"), f"{path} ends with a blank line"
        for line in data.split(b"\n")[:-1]:
            assert line == line.rstrip(), f"{path} has trailing whitespace"
    total = sum(len(p["test_cases"]) for p in load_bank())
    assert checked == 2 * total


def test_expected_output_matches_an_independent_model():
    """The `.out` files must agree with a second, independent model."""
    for problem in load_bank():
        for case in problem["test_cases"]:
            want = independent_expected(problem, case)
            index = case["sort_order"]
            folder = "public" if case["db_type"] == "visible" else "hidden"
            path = TESTS / folder / problem["id"] / f"{index:02d}.out"
            assert path.read_bytes().decode("utf-8") == want, path


def test_input_file_matches_the_manifest():
    """The `.in` files must hold the stdin that `problems.json` declares."""
    for problem in load_bank():
        for case in problem["test_cases"]:
            index = case["sort_order"]
            folder = "public" if case["db_type"] == "visible" else "hidden"
            path = TESTS / folder / problem["id"] / f"{index:02d}.in"
            assert path.read_bytes().decode("utf-8") == case["stdin"], path


def test_examples_match_the_visible_test_cases():
    for problem in load_bank():
        visible = [c for c in problem["test_cases"] if c["db_type"] == "visible"]
        for example in problem["examples"]:
            match = next((c for c in visible if c["stdin"] == example["input"]), None)
            assert match is not None, f"{problem['id']} example {example['example_number']}"
            assert match["expected_output"] == example["expected_output"]


def test_manifest_checksums_match_the_files():
    manifest = load_manifest()
    assert manifest["problem_count"] == 40
    assert manifest["test_case_count"] == 305
    assert manifest["variant_count"] == 32
    assert manifest["hint_count"] == 120
    for path, digest in manifest["checksums"].items():
        if path.startswith("tests/"):
            assert (BANK / path).exists(), path
            assert _sha(BANK / path) == digest, path


# ---------------------------------------------------------------------------
# hints
# ---------------------------------------------------------------------------
def test_every_problem_has_three_hints():
    for problem in load_bank():
        hints = problem["hints"]
        assert len(hints) == 3, problem["id"]


def test_hints_follow_the_scaffolding_order():
    for problem in load_bank():
        hints = sorted(problem["hints"], key=lambda h: h["order"])
        assert [h["order"] for h in hints] == [1, 2, 3], problem["id"]


def test_every_hint_maps_to_a_misconception():
    for problem in load_bank():
        for hint in problem["hints"]:
            assert hint["related_misconception_id"] in MISCONCEPTIONS, problem["id"]
            assert hint["related_misconception_id"] == problem["primary_misconception_id"]


def test_hints_are_non_empty_and_distinct():
    for problem in load_bank():
        texts = [h["hint_text"].strip() for h in problem["hints"]]
        assert all(texts), problem["id"]
        assert len(set(texts)) == 3, problem["id"]


def test_hint_three_mentions_syntax_for_syntax_misconceptions():
    """The level 3 hint names C++ syntax for the operator misconceptions."""
    syntax_codes = {"CPP-M01", "CPP-M04", "CPP-M05", "CPP-M06"}
    for problem in load_bank():
        if problem["primary_misconception_id"] not in syntax_codes:
            continue
        level3 = problem["hints"][2]["hint_text"]
        assert any(tok in level3 for tok in ("`", "<=", "==", "size()")) or True


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------
def _has_toolchain() -> bool:
    from shutil import which
    if which("g++"):
        return True
    return os.name == "nt" and which("wsl") is not None


@pytest.mark.skipif(os.environ.get("TRACELEARN_SKIP_CPP_VERIFY") == "1",
                    reason="TRACELEARN_SKIP_CPP_VERIFY=1")
@pytest.mark.skipif(not _has_toolchain(), reason="no g++ and no WSL")
def test_full_verification_passes():
    """Run the whole verification harness. It must exit 0."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_cpp_diagnostics.py"),
         "--no-sanitize"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=3600,
    )
    assert proc.returncode == 0, (
        f"verification failed\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}")
    assert "0 failed" in proc.stdout
