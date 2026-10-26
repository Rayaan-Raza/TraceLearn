"""Unit tests for the cluster-aware synthetic expansion tooling.

The compiler-backed path is exercised by the WSL pilot; these tests cover the
deterministic selection, dedupe, row-shape, and evidence-classification pieces
without requiring g++ on the host.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scripts import expand_mutants as ex


def test_deterministic_row_id_is_stable_and_cluster_specific():
    a = ex.deterministic_row_id("seed-1", "op-a", "CPP_X", "clu-001")
    b = ex.deterministic_row_id("seed-1", "op-a", "CPP_X", "clu-001")
    c = ex.deterministic_row_id("seed-1", "op-a", "CPP_X", "clu-002")
    d = ex.deterministic_row_id("seed-1", "op-b", "CPP_X", "clu-001")
    assert a == b
    assert a != c and a != d
    assert a.startswith("mut-") and len(a) == 14


def test_load_cluster_assignments_keeps_train_only(tmp_path: Path):
    path = tmp_path / "cluster_assignments.csv"
    path.write_text(
        "problem_id,cluster_id,split,statement_len\n"
        "p-1,clu-001,train,10\n"
        "p-2,clu-002,test,10\n"
        "p-3,clu-003,dev_gold,10\n",
        encoding="utf-8",
    )
    assert ex.load_cluster_assignments(path) == {"p-1": "clu-001"}


def test_load_existing_keys_skips_rows_without_seed_or_op(tmp_path: Path):
    path = tmp_path / "tier0.jsonl"
    rows = [
        {"seed_ref": "s-1", "mutation_op": "op-a", "problem_id": "p-1",
         "label": "CPP_X"},
        {"seed_ref": None, "mutation_op": "op-b", "problem_id": "p-1",
         "label": "CPP_X"},
        {"seed_ref": "s-2", "mutation_op": None, "problem_id": "p-1",
         "label": "CPP_X"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert ex.load_existing_keys(path) == {("s-1", "op-a", "p-1", "CPP_X")}


def test_select_target_clusters_prefers_underrepresented():
    counts = Counter({"clu-a": 5, "clu-b": 0})
    targets = ex.select_target_clusters(
        counts, {"clu-a", "clu-b", "clu-c"}, max_clusters=2
    )
    assert targets == ["clu-b", "clu-c"]


def test_run_tests_rich_classifies_pass_wrong_crash_timeout():
    def fake_run(cmd, timeout, cwd=None, stdin_text=None):
        value = (stdin_text or "").strip()
        return {
            "1": (0, "10\n", ""),
            "2": (0, "99\n", ""),
            "3": (-11, "", ""),
            "4": (-1, "", "TIMEOUT"),
        }[value]

    tests = [
        {"input": "1", "output": "10"},
        {"input": "2", "output": "10"},
        {"input": "3", "output": "10"},
        {"input": "4", "output": "10"},
    ]
    out = ex.run_tests_rich("exe", tests, run_cmd=fake_run)
    statuses = [r["status"] for r in out["results"]]
    assert statuses == ["pass", "wrong", "crash", "timeout"]
    assert (out["total"], out["passed"], out["failed"]) == (4, 1, 3)


def test_build_tests_block_maps_status_vocabulary():
    results = {
        "total": 4, "passed": 1, "failed": 3,
        "results": [
            {"status": "pass"}, {"status": "wrong"},
            {"status": "crash"}, {"status": "timeout"},
        ],
    }
    block = ex.build_tests_block(results)
    assert block["available"] is True
    assert block["total"] == 4
    assert block["passed"] == 1
    assert block["failed"] == 3
    assert block["pass_rate"] == 0.25
    assert block["wrong_answer_count"] == 1
    assert block["runtime_error_count"] == 1
    assert block["timeout_count"] == 1
    assert block["first_fail_index"] == 1


def test_build_runtime_block_classifies_asan_heap_overflow():
    results = {
        "total": 1, "passed": 0, "failed": 1,
        "results": [{"status": "crash", "rc": -11}],
    }
    block = ex.build_runtime_block(
        results,
        sanitizer_stderr="ERROR: AddressSanitizer: heap-buffer-overflow",
        sanitizer_ran=True,
    )
    assert block["available"] is True
    assert block["crashed"] is True
    assert block["asan_error"] is True
    assert block["asan_heap_buffer_overflow"] is True
    assert block["asan_stack_buffer_overflow"] is False
    assert block["ubsan_error"] is False


def test_load_problem_context_reads_statement_and_tests(tmp_path: Path):
    path = tmp_path / "Problem Data.csv"
    path.write_text(
        "problem_id,problem_description,evaluation_test_cases\n"
        'prob_001,"Find the sum","[{""input"":""1"",""output"":""1""}]"\n',
        encoding="utf-8",
    )
    ctx = ex.load_problem_context(path)
    item = ctx["tl-codestream-prob_001"]
    assert item["available"] is True
    assert item["statement_length"] == len("Find the sum")
    assert item["sample_test_count"] == 1
    assert item["sample_tests_present"] is True


def test_build_expansion_row_carries_canonical_evidence():
    seed = {
        "submission_id": "s-1",
        "problem_id": "p-1",
        "language": "cpp",
        "source_code": "int main() { return 0; }",
        "attempt_number": 1,
        "user_id": "u-1",
    }
    proof = {
        "compile_warnings_std": "",
        "tests_passed": 1,
        "tests_failed": 2,
        "tests_total": 3,
        "sanitizer_ok": False,
        "tests": {"available": True, "total": 3, "passed": 1, "failed": 2},
        "runtime": {"available": True, "crashed": True},
        "context": {"available": True, "statement_length": 12},
    }
    row = ex.build_expansion_row(
        seed, "int main() { return 1; }", "CPP_X", "op-a", proof, "clu-001",
        "run-test",
    )
    assert row["schema_version"] == "1.1"
    assert row["row_id"] == ex.deterministic_row_id("s-1", "op-a", "CPP_X", "clu-001")
    assert row["problem_cluster"] == "clu-001"
    assert row["tests"] == proof["tests"]
    assert row["runtime"] == proof["runtime"]
    assert row["context"] == proof["context"]
    assert row["seed_ref"] == "s-1"
    assert row["mutation_op"] == "op-a"


# --- INT_OVERFLOW forms that match real CodeStream seeds (operator library 1.1)

def _io_form(name):
    from scripts import generate_mutants as gm
    lib = gm.load_operator_library()
    return next(f for f in lib["operators"]["CPP_INT_OVERFLOW"]["forms"] if f["name"] == name)


def test_int_overflow_real_seed_forms_fire():
    from scripts import generate_mutants as gm
    cases = {
        "overflow_ll_macro_to_int": ("#define ll long long\nll a;", "#define ll int\nll a;"),
        "overflow_ll_typedef_to_int": ("typedef long long ll;\n", "typedef int ll;\n"),
        "overflow_lli_decl_to_int": ("long long int n, m;", "int n, m;"),
        "overflow_ll_decl_to_int": ("long long fact = 1;", "int fact = 1;"),
        "overflow_1ll_suffix_removed": ("x = a * 1LL * b;", "x = a * b;"),
    }
    for name, (src, want) in cases.items():
        assert gm.apply_operator_form(src, _io_form(name)) == want, name


def test_int_overflow_real_seed_forms_do_not_fire():
    from scripts import generate_mutants as gm
    # 'long long int' is left to its own form; casts and vector<long long> are untouched
    assert gm.apply_operator_form("long long int n;", _io_form("overflow_ll_decl_to_int")) is None
    assert gm.apply_operator_form("(long long)a * b", _io_form("overflow_ll_decl_to_int")) is None
    assert gm.apply_operator_form("vector<long long> v;", _io_form("overflow_ll_decl_to_int")) is None
    assert gm.apply_operator_form("#define ll int", _io_form("overflow_ll_macro_to_int")) is None


def test_real_seeds_only_flag_is_recorded(tmp_path):
    import argparse  # noqa: F401  (parser is built inside main)
    src = Path(ex.__file__).read_text(encoding="utf-8")
    assert "--real-seeds-only" in src and "real_seeds_only" in src


def test_int_overflow_rejects_format_mismatch_and_crash_only_mutants():
    wrong = {"results": [{"status": "pass"}, {"status": "wrong"}]}
    crash = {"results": [{"status": "crash"}, {"status": "crash"}]}
    fmt = "main.cpp:5:9: warning: format '%lld' expects argument of type 'long long int*' [-Wformat=]"
    assert ex.class_specific_reject("CPP_INT_OVERFLOW", wrong, fmt) == "format_specifier_mismatch"
    assert ex.class_specific_reject("CPP_INT_OVERFLOW", crash, "") == "no_wrong_answer_only_crash_or_timeout"
    assert ex.class_specific_reject("CPP_INT_OVERFLOW", wrong, "") is None
    assert ex.class_specific_reject("CPP_LOOP_BOUNDARY", crash, fmt) is None
