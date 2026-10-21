"""Fixture tests for sandbox_runner (Master Plan §9.2-U0, gate G2 parser fixtures).

Each fixture program in data/misconception_dataset/fixtures/sandbox has one
behaviour the harness must report exactly. Run:  pytest tests/misconception_dataset
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from sandbox_runner import RunConfig, run_submission

FIX = Path(__file__).resolve().parents[2] / "data" / "misconception_dataset" / "fixtures" / "sandbox"
HAS_GCC = shutil.which("g++") is not None and shutil.which("gcc") is not None
HAS_VG = shutil.which("valgrind") is not None

pytestmark = pytest.mark.skipif(not HAS_GCC, reason="needs gcc/g++")

FAST = RunConfig(valgrind_pass=False, double_run=False)


def run(name, tests, cfg=FAST):
    lang = "c" if name.endswith(".c") else "cpp"
    return run_submission((FIX / name).read_text(), lang, tests, cfg)


def T(i, o):
    return {"input": i, "output": o}


def test_clean_passes_without_reports():
    r = run("clean.cpp", [T("3\n", "6\n"), T("10\n", "55\n")])
    assert r["compile"]["ok"]
    assert r["tests"]["all_passed"] and r["tests"]["passed"] == 2
    assert r["branch"] == "all_pass"
    assert r["runtime"]["sanitizer"]["reports"] == []
    assert r["runtime"]["sanitizer"]["complete"]


def test_compile_error_branch():
    r = run("compile_error.cpp", [T("1\n", "1\n")])
    assert not r["compile"]["ok"]
    assert r["branch"] == "compile_error"
    assert r["compile"]["errors"] and r["compile"]["errors"][0]["line"] == 2
    assert r["tests"] is None


def test_wrong_answer_numeric_delta():
    # clean.cpp is right; compare against an off-by-one expected value
    r = run("clean.cpp", [T("3\n", "7\n")])
    res = r["tests"]["results"][0]
    assert res["status"] == "wrong"
    assert res["diff"]["numeric_deltas"] == [-1]
    assert res["diff"]["all_deltas_pm1"]


def test_asan_heap_overflow_elements_past_end():
    r = run("asan_overflow.cpp", [T("4\n", "0\n")])
    rep = r["runtime"]["sanitizer"]["first_report"]
    assert rep["tool"] == "asan" and rep["kind"] == "heap-buffer-overflow"
    assert rep["access"] == "WRITE" and rep["elements_past_end"] == 0
    assert rep["line"] == 2


def test_ubsan_signed_overflow():
    r = run("ubsan_overflow.cpp", [T("3\n", "1000\n"), T("12\n", "1000000000000\n")])
    kinds = r["runtime"]["sanitizer"]["kinds"]
    assert kinds.get("ubsan:signed-integer-overflow", 0) >= 1
    assert r["tests"]["results"][0]["status"] == "pass"
    assert r["tests"]["results"][1]["status"] == "wrong"


def test_stack_overflow_detected():
    # At -O2 gcc may turn the unguarded recursion into an endless loop (a
    # timeout); the -O1 sanitizer build still reports the stack overflow, so
    # the row is "failing", never "timeout_only".
    r = run("stack_overflow.cpp", [T("5\n", "15\n")])
    assert r["runtime"]["any_crash"] or r["runtime"]["any_timeout"]
    assert r["runtime"]["stack_overflow"]
    assert r["branch"] == "failing"


@pytest.mark.skipif(not HAS_VG, reason="needs valgrind")
def test_valgrind_uninit():
    cfg = RunConfig(double_run=False, sanitizer_pass=False)
    r = run_submission((FIX / "uninit.cpp").read_text(), "c", [T("3\n", "6\n")], cfg)
    vg = r["runtime"]["valgrind"]
    assert vg["ran"] and vg["uninit"]
    assert any(k.startswith("uninit") for k in vg["kinds"])


@pytest.mark.skipif(not HAS_VG, reason="needs valgrind")
def test_valgrind_clean_has_no_uninit():
    cfg = RunConfig(double_run=False, sanitizer_pass=False)
    r = run_submission((FIX / "clean.cpp").read_text(), "cpp", [T("3\n", "6\n")], cfg)
    assert r["runtime"]["valgrind"]["ran"] and not r["runtime"]["valgrind"]["uninit"]


def test_warning_pass_flags():
    r = run("assign_in_cond.cpp", [T("1\n", "2\n")])
    assert r["warnings"]["count_by_flag"].get("-Wparentheses", 0) >= 1
    w = [x for x in r["warnings"]["items"] if x["flag"] == "-Wparentheses"][0]
    assert w["line"] == 2


def test_uninit_compile_warning():
    r = run("uninit.cpp", [T("3\n", "6\n")])
    assert r["warnings"]["count_by_flag"].get("-Wmaybe-uninitialized", 0) + \
        r["warnings"]["count_by_flag"].get("-Wuninitialized", 0) >= 1


def test_timeout_branch_and_process_group_kill():
    cfg = RunConfig(valgrind_pass=False, double_run=False, sanitizer_pass=False)
    r = run("timeout.cpp", [T("5\n", "5\n")], cfg)
    res = r["tests"]["results"][0]
    assert res["status"] == "timeout"
    assert res["seconds"] < cfg.limits.time_s + 1.5
    assert r["branch"] == "timeout_only"


def test_trailing_whitespace_is_pass_reordered_ws_is_presentation():
    assert run("presentation.cpp", [T("5\n", "15\n")])["tests"]["all_passed"]
    r = run("presentation_real.cpp", [T("3\n", "1 2 3\n")])
    assert r["tests"]["results"][0]["status"] == "presentation"
    assert r["tests"]["passed_lenient"] == 1 and r["tests"]["passed"] == 0


def test_output_cap():
    cfg = RunConfig(valgrind_pass=False, double_run=False, sanitizer_pass=False)
    r = run("output_limit.cpp", [T("", "x\n")], cfg)
    assert r["tests"]["results"][0]["status"] in ("output_limit", "timeout")


def test_flaky_test_is_dropped():
    cfg = RunConfig(valgrind_pass=False, sanitizer_pass=False, double_run=True)
    r = run("flaky.cpp", [T("", "0\n")], cfg)
    assert r["tests"]["flaky"] == [0]
    assert r["tests"]["total"] == 0


def test_reversed_output_evidence():
    r = run("reversed.c", [T("4\n", "1 2 3 4\n")])
    d = r["tests"]["results"][0]["diff"]
    assert d["reversed_tokens"] and d["same_multiset"]


def test_network_is_blocked_when_isolation_available():
    from sandbox_runner.process import isolation_report
    if not isolation_report()["network_namespace"]:
        pytest.skip("no network namespace on this host (docker backend covers it)")
    r = run("network.cpp", [T("", "blocked\n")])
    assert r["tests"]["all_passed"]


def test_cache_roundtrip(tmp_path):
    tests = [T("3\n", "6\n")]
    a = run_submission((FIX / "clean.cpp").read_text(), "cpp", tests, FAST, cache_dir=str(tmp_path))
    b = run_submission((FIX / "clean.cpp").read_text(), "cpp", tests, FAST, cache_dir=str(tmp_path))
    assert not a["cache_hit"] and b["cache_hit"]
    assert a["cache_key"] == b["cache_key"]


def test_determinism_same_result_twice():
    tests = [T("3\n", "6\n"), T("4\n", "1\n")]
    a = run("clean.cpp", tests)
    b = run("clean.cpp", tests)
    def strip(r):
        return [(x["status"], x.get("stdout_head")) for x in r["tests"]["results"]]

    assert strip(a) == strip(b)


def test_c_bool_without_header_compiles_with_recorded_fallback():
    r = run("c_bool.c", [T("3\n", "yes\n")])
    assert r["compile"]["ok"] and r["compile"]["fallback"] == "include_stdbool"
    assert r["tests"]["all_passed"]
    assert r["runtime"]["sanitizer"]["compiled"]
