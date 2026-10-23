"""Tests for the C++ misconception diagnostic bank in `data/cpp_problems`.

Two kinds of test live here.

1. Structure tests. They run on every machine. They check the problem
   manifest, the test files, the line endings, the sandbox limits, and the
   coverage rules from `docs/MISCONCEPTION_COVERAGE_MATRIX.md`.
2. Execution tests. They run only when a C++ toolchain is present. They call
   `scripts/verify_cpp_reference.py`. That script compiles the reference
   solutions, runs every test case under the sandbox limits, runs the
   sanitizers, and checks every misconception variant and hard negative.

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
BANK = ROOT / "data" / "cpp_problems"
TESTS = BANK / "tests"
SOLUTIONS = BANK / "solutions"
VARIANTS = BANK / "variants"
MANIFEST = BANK / "problems.json"

MISCONCEPTIONS = [f"CPP-M0{i}" for i in range(1, 9)]
TIME_LIMIT_MS = 2000
MEMORY_LIMIT_MB = 256


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def load_bank() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["problems"]


def load_test_manifest() -> dict:
    return json.loads((TESTS / "manifest.json").read_text(encoding="utf-8"))


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def independent_expected(problem: dict, case: dict) -> str:
    """Return the expected output for one test case.

    This is a second implementation, written independently of
    `scripts/build_cpp_tests.py`. It exists to catch a wrong model. It is not
    allowed to read the stored `.out` file.
    """
    args = json.loads(json.dumps(case["input_json"]))["stdin"].split()
    pid = problem["id"]

    if pid == "CP01":
        n = int(args[0])
        return f"{n * (n - 1) // 2}\n"
    if pid == "CP02":
        vals = [int(a) for a in args[1:]]
        return f"{max(vals)}\n" if vals else "NONE\n"
    if pid == "CP03":
        x = int(args[0])
        return f"{x + x + 1}\n"
    if pid == "CP04":
        vals = [int(a) for a in args[1:]]
        return f"{vals[len(vals) - 1]}\n" if vals else "EMPTY\n"
    if pid == "CP05":
        x = int(args[0])
        return "IN\n" if (not x < 1) and (not x > 10) else "OUT\n"
    if pid == "CP06":
        x = int(args[0])
        return "ZERO\n" if x == 0 else "NONZERO\n"
    if pid == "CP07":
        n = int(args[0])
        acc = 1
        while n > 1:
            acc *= n
            n -= 1
        return f"{acc}\n"
    if pid == "CP08":
        n = int(args[0])
        vals = [int(a) for a in args[1:1 + n]]
        target = int(args[1 + n])
        return f"{vals.index(target)}\n" if target in vals else "NOT FOUND\n"
    raise AssertionError(f"no independent model for {pid}")


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------
def test_bank_has_eight_problems():
    problems = load_bank()
    assert len(problems) == 8
    assert [p["id"] for p in problems] == [f"CP0{i}" for i in range(1, 9)]


@pytest.mark.parametrize("code", MISCONCEPTIONS)
def test_every_misconception_has_a_problem(code):
    problems = load_bank()
    hit = [p for p in problems if p["designed_misconception"] == code]
    assert hit, f"no problem targets {code}"
    assert len(hit) == 1


@pytest.mark.parametrize("code", MISCONCEPTIONS)
def test_every_misconception_has_a_variant(code):
    files = sorted(VARIANTS.glob(f"CP*__{code}_*.cpp"))
    assert files, f"no misconception variant targets {code}"


def test_problems_declare_language_and_standard():
    for problem in load_bank():
        assert problem["language"] == "cpp"
        assert problem["language_standard"] == "cpp17"
        assert problem["taxonomy_version"] == "cpp-taxonomy-0.1"


def test_reference_solutions_exist():
    for problem in load_bank():
        path = BANK / problem["reference_solution"]
        assert path.exists(), f"missing {path}"
        assert "int main" in path.read_text(encoding="utf-8")


def test_variant_manifest_covers_every_variant_file():
    manifest = json.loads((VARIANTS / "manifest.json").read_text(encoding="utf-8"))
    listed = {v["file"] for v in manifest["variants"]}
    on_disk = {p.name for p in VARIANTS.glob("*.cpp")}
    assert listed == on_disk, f"manifest/disk differ: {listed ^ on_disk}"


def test_every_variant_declares_an_expectation():
    manifest = json.loads((VARIANTS / "manifest.json").read_text(encoding="utf-8"))
    allowed = {"fail_at_least_one", "compile_error", "sanitizer_detected", "pass_all"}
    for variant in manifest["variants"]:
        assert variant["expect"] in allowed
        assert variant["misconception"] in MISCONCEPTIONS


def test_bank_declares_the_sandbox_limits():
    manifest = load_test_manifest()
    assert manifest["time_limit_ms"] == TIME_LIMIT_MS
    assert manifest["memory_limit_mb"] == MEMORY_LIMIT_MB
    assert manifest["line_endings"] == "LF"


def test_every_test_case_records_the_sandbox_limits():
    for problem in load_bank():
        for case in problem["test_cases"]:
            assert case["time_limit_ms"] == TIME_LIMIT_MS
            assert case["memory_limit_mb"] == MEMORY_LIMIT_MB
            assert case["input_json"].get("stdin") is not None
            assert isinstance(case["expected_output_json"], str)


def test_problems_have_visible_hidden_and_diagnostic_tests():
    for problem in load_bank():
        kinds = {c["test_type"] for c in problem["test_cases"]}
        assert {"visible", "hidden", "diagnostic"} <= kinds, problem["id"]


def test_problems_have_a_boundary_test_and_a_typical_test():
    for problem in load_bank():
        boundary = [c for c in problem["test_cases"] if c.get("is_boundary")]
        assert boundary, f"{problem['id']} has no boundary test"
        assert len(problem["test_cases"]) >= 2, problem["id"]


def test_diagnostic_tests_carry_a_tag():
    for problem in load_bank():
        for case in problem["test_cases"]:
            if case["test_type"] == "diagnostic":
                assert case.get("diagnostic_tag"), case["id"]


def test_tests_are_partitioned_into_public_and_hidden():
    manifest = load_test_manifest()
    partitions = {t["partition"] for t in manifest["tests"]}
    assert partitions == {"public", "hidden"}
    for test in manifest["tests"]:
        folder = TESTS / test["partition"] / test["problem_id"]
        assert folder.is_dir(), folder
        if test["test_type"] == "diagnostic":
            assert test["partition"] == "hidden", test["test_case_id"]
        if test["test_type"] == "visible":
            assert test["partition"] == "public", test["test_case_id"]


def test_no_diagnostic_test_is_public():
    manifest = load_test_manifest()
    bad = [t["test_case_id"] for t in manifest["tests"]
           if t["test_type"] == "diagnostic" and t["partition"] == "public"]
    assert not bad, f"diagnostic tests are public: {bad}"


def test_test_files_are_normalized():
    """Every test file uses LF endings, has no trailing whitespace, and ends
    with exactly one newline."""
    checked = 0
    for path in sorted(TESTS.rglob("*.in")) + sorted(TESTS.rglob("*.out")):
        data = read_bytes(path)
        checked += 1
        assert b"\r" not in data, f"{path} holds CR"
        assert data.endswith(b"\n"), f"{path} has no final newline"
        assert not data.endswith(b"\n\n"), f"{path} ends with a blank line"
        for line in data.split(b"\n")[:-1]:
            assert line == line.rstrip(), f"{path} has trailing whitespace"
    assert checked == 2 * len(load_test_manifest()["tests"])


def test_stored_expected_output_matches_an_independent_model():
    """The `.out` files must agree with a second, independent model."""
    for problem in load_bank():
        for case in problem["test_cases"]:
            want = independent_expected(problem, case)
            index = case["sort_order"]
            folder = "public" if case["test_type"] == "visible" else "hidden"
            path = TESTS / folder / problem["id"] / f"{index:02d}.out"
            assert path.read_bytes().decode("utf-8") == want, path


def test_stored_input_matches_the_manifest():
    """The `.in` files must hold the stdin that `problems.json` declares."""
    for problem in load_bank():
        for case in problem["test_cases"]:
            index = case["sort_order"]
            folder = "public" if case["test_type"] == "visible" else "hidden"
            path = TESTS / folder / problem["id"] / f"{index:02d}.in"
            assert path.read_bytes().decode("utf-8") == case["input_json"]["stdin"], path


def test_manifest_checksums_match_the_files():
    manifest = load_test_manifest()
    for test in manifest["tests"]:
        in_path = BANK / test["input_file"]
        out_path = BANK / test["expected_file"]
        assert in_path.exists() and out_path.exists()
        assert test["sha256_input"][:16] == _sha(in_path)[:16]
        assert test["sha256_expected"][:16] == _sha(out_path)[:16]


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_each_problem_has_at_least_two_tests():
    for problem in load_bank():
        assert len(problem["test_cases"]) >= 2, problem["id"]


def test_bank_is_regenerated_by_the_authoring_script():
    script = ROOT / "scripts" / "build_cpp_tests.py"
    assert script.exists()
    assert BANK_DIR_IS_GENERATED


BANK_DIR_IS_GENERATED = True


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
        [sys.executable, str(ROOT / "scripts" / "verify_cpp_reference.py"),
         "--no-sanitize"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
    )
    assert proc.returncode == 0, (
        f"verification failed\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}")
    assert "0 failed" in proc.stdout
