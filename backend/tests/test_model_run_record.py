"""The `execution` variant uses a run record when given one and abstains without it."""
from __future__ import annotations

import pytest

from backend.app.analysis import model_runner
from backend.app.config import settings
from tracelearn_features.execution import REPAIR_CLASSES

SOURCE = "#include <stdio.h>\nint main(){int a[3];for(int i=0;i<=3;i++)a[i]=i;printf(\"%d\",a[0]);return 0;}\n"
RECORD = {
    "compiled": True,
    "tests": {"results": [{"status": "crash"}, {"status": "pass"}]},
    "runtime": {"sanitizer": {"complete": True, "kinds": {"asan:stack-buffer-overflow": 1}, "reports": []}},
    "cf": {"classes": {"CPP_ARRAY_BOUNDS": {"compiled": 1, "fix_first": 1, "fix_first_noreg": 1, "fix_all": 1, "best_gain": 0.5}}},
}


@pytest.fixture(autouse=True)
def _execution_variant(monkeypatch):
    monkeypatch.setattr(settings, "model_variant", "execution")
    monkeypatch.setattr(model_runner, "compiler_warnings", lambda source: {"_compiled": True})
    model_runner._classifier.cache_clear()
    yield
    model_runner._classifier.cache_clear()


def test_code_features_carry_the_run_record():
    with_run = model_runner.code_features(SOURCE, run_record=RECORD)
    assert with_run["evidence.ff_crash"] == 1 and with_run["repair.array_bounds_fix_all"] == 1
    without = model_runner.code_features(SOURCE)
    assert without["evidence.ff_crash"] is None and without["repair.array_bounds_fix_all"] is None
    assert without["source.lp_le"] == 1


@pytest.mark.parametrize("mode", ["shadow", "on"])
def test_abstains_without_a_run_record(monkeypatch, mode):
    monkeypatch.setattr(settings, "model_diagnosis", mode)
    record = model_runner.model_records(SOURCE)[0]
    if mode == "shadow":
        assert record.evidence_code == "MODEL_SHADOW" and record.details["abstained"] is True
    else:
        assert record.evidence_code == "MODEL_ABSTAINED"


def test_a_run_record_lets_it_answer(monkeypatch):
    monkeypatch.setattr(settings, "model_diagnosis", "shadow")
    # A real record fills almost every field (median 4.3% missing on the held-out rows); this one is small
    # on purpose, so the test pins the mechanism: the record's fields reach the model.
    with_run = model_runner.model_records(SOURCE, run_record=RECORD)[0].details["n_missing"]
    without = model_runner.model_records(SOURCE)[0].details["n_missing"]
    assert with_run < without


def test_a_full_record_is_under_the_missing_limit(monkeypatch):
    monkeypatch.setattr(settings, "model_diagnosis", "shadow")
    classes = {"CPP_" + c: {"compiled": 1, "fix_first": 1, "fix_first_noreg": 1, "fix_all": 1, "best_gain": 1.0} for c in REPAIR_CLASSES}
    diff = {"expected_tokens": 4, "actual_tokens": 4, "prefix_tokens": 1, "token_count_delta": 0, "max_abs_delta": 1, "numeric_deltas": [1],
            **{k: False for k in ("is_prefix_of_expected", "expected_is_prefix", "is_suffix_of_expected", "expected_is_suffix", "empty_output",
                                  "reversed_tokens", "reversed_lines", "same_multiset", "all_deltas_pm1", "negative_where_positive")}}
    full = {"compiled": True, "tests": {"results": [{"status": "wrong", "diff": diff}, {"status": "pass"}]},
            "runtime": {"sanitizer": {"complete": True, "kinds": {}, "reports": []}, "stack_overflow": False},
            "cf": {"classes": classes, "uninit": {"differs": False, "zero_fixes": False}}}
    details = model_runner.model_records(SOURCE, run_record=full)[0].details
    assert details["n_missing"] / details["n_features"] <= model_runner.MAX_MISSING_SHARE


def test_off_runs_nothing(monkeypatch):
    monkeypatch.setattr(settings, "model_diagnosis", "off")
    assert model_runner.model_records(SOURCE, run_record=RECORD) == []
