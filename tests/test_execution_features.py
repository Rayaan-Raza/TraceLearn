"""The source, evidence and repair blocks (tracelearn_features/execution.py)."""
from __future__ import annotations

import json
import math

import pytest

from tracelearn_features.execution import REPAIR_CLASSES, evidence_features, execution_blocks, repair_features, source_features
from tracelearn_features.normalize import runner_warnings
from tracelearn_features.schema import FEATURE_BLOCKS


def test_every_block_key_is_in_the_schema():
    src = "#define N 10\nint a[N]; int main(){ long long s; for(int i=0;i<=N;i++) s+=a[i]; while(s>0){} if(s<3&&s>1) return 1; }"
    assert set(source_features(src)) <= set(FEATURE_BLOCKS["source"])
    tests = {"results": [{"status": "pass"}, {"status": "wrong", "diff": {
        "expected_tokens": 2, "actual_tokens": 2, "numeric_deltas": [1], "max_abs_delta": 1, "all_deltas_pm1": True}}]}
    runtime = {"sanitizer": {"complete": True, "kinds": {"asan:stack-buffer-overflow": 1},
                             "reports": [{"elements_past_end": 2, "index": 5, "access": "WRITE"}]}, "stack_overflow": False}
    assert set(evidence_features(tests, runtime)) <= set(FEATURE_BLOCKS["evidence"])
    cf = {"classes": {"CPP_" + c: {"compiled": 1, "fix_first": 1, "fix_first_noreg": 1, "fix_all": 1, "best_gain": 1.0} for c in REPAIR_CLASSES},
          "uninit": {"differs": True, "zero_fixes": False}}
    assert set(repair_features(cf)) == set(FEATURE_BLOCKS["repair"])


def test_source_features_read_loops_and_arrays():
    f = source_features("#define N 100\nint a[N];\nint main(){ for(int i=1;i<=N;i++) a[i]=0; return 0; }")
    assert f["arr_fixed_n"] == 1 and f["arr_fixed_max_log"] == math.log10(101)
    assert f["lp_le"] == 1 and f["lp_s1_le"] == 1 and f["lp_le_idx"] == 1


def test_source_features_ignore_comments_and_strings():
    f = source_features('int main(){ /* for(int i=0;i<=9;i++) */ // while(x<1)\n puts("for(i=0;i<=9;i++)"); }')
    assert f["lp_le"] == 0 and f["lp_stale"] == 0


def test_evidence_reads_the_first_failing_test():
    tests = {"results": [{"status": "pass"}, {"status": "wrong", "diff": {
        "expected_tokens": 4, "actual_tokens": 2, "prefix_tokens": 1, "max_abs_delta": 999, "numeric_deltas": [-3]}},
        {"status": "crash"}]}
    f = evidence_features(tests, None)
    assert f["n"] == 3 and f["pass_frac"] == pytest.approx(1 / 3) and f["ff_frac"] == pytest.approx(1 / 3)
    assert f["ff_wrong"] == 1 and f["ff_crash"] == 0 and f["fr_crash"] == 0.5
    assert f["tok_ratio"] == 0.5 and f["prefix_frac"] == 0.25 and f["maxd_log"] == 3.0 and f["sign_delta"] == -1


def test_a_passing_program_has_no_first_failure():
    f = evidence_features({"results": [{"status": "pass"}]}, None)
    assert f["pass_frac"] == 1.0 and math.isnan(f["ff_frac"]) and math.isnan(f["maxd_log"]) and "fr_pm1" not in f


def test_sanitizer_absent_stays_missing_and_clean_pass_is_zero():
    assert "sa_oob" not in evidence_features(None, {})
    clean = evidence_features(None, {"sanitizer": {"complete": True, "kinds": {}, "reports": []}})
    assert clean["sa_avail"] == 1 and clean["sa_oob"] == 0


def test_repair_counts_are_capped_and_summed():
    cf = {"classes": {"CPP_OFF_BY_ONE": {"compiled": 3, "fix_first": 9, "fix_first_noreg": 4, "fix_all": 2, "best_gain": 0.5},
                      "CPP_RANGE_CHECK": {"compiled": 0, "fix_first": 0, "fix_first_noreg": 0, "fix_all": 0, "best_gain": 0}}}
    f = repair_features(cf)
    assert f["off_by_one_fix_first"] == 3 and f["off_by_one_noreg"] == 3 and f["off_by_one_fix_all"] == 1
    assert f["range_check_tried"] == 0 and f["n_fix_all"] == 1 and f["n_fix_first"] == 1


def test_no_usable_run_gives_no_blocks_and_no_warnings():
    for record in (None, {"row_id": "x", "error": "boom"}, {"row_id": "x", "compiled": False}):
        assert execution_blocks(record) == {}
        assert runner_warnings(record) is None


def test_blocks_leave_missing_values_out_so_they_stay_nan():
    blocks = execution_blocks({"compiled": True, "tests": {"results": [{"status": "pass"}]}})
    assert "ff_frac" not in blocks["evidence"] and blocks["repair"] == {}
    json.dumps(blocks, allow_nan=False)  # labels.jsonl must stay strict JSON


def test_no_label_field_reaches_the_features():
    record = {"compiled": True, "tests": {"results": [{"status": "pass"}]}, "cf": {"classes": {}}}
    with_label = {**record, "label": "CPP_OFF_BY_ONE", "problem": "p", "row_id": "r"}
    assert execution_blocks(record) == execution_blocks(with_label)
