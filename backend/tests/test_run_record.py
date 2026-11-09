"""Live run records: served features must equal training features, and the path must stay safe and optional."""
from __future__ import annotations

import csv
import json
import math
import os
import shutil
from pathlib import Path

import pytest

from backend.app.analysis import model_runner, run_record
from backend.app.config import Settings, settings

ROOT = Path(__file__).resolve().parents[2]
DS = ROOT / "data" / "misconception_dataset"
CACHE = DS / "cache" / "counterfactual" / "evidence.jsonl"
OFF_BY_ONE = ('#include <iostream>\nusing namespace std;\nint main(){int n;cin>>n;long long s=0;'
              'for(int i=1;i<n;i++)s+=i;cout<<s<<endl;return 0;}\n')
TESTS = [{"input": "3\n", "output": "6\n"}, {"input": "5\n", "output": "15\n"}]


@pytest.mark.skipif(not CACHE.exists(), reason="the evidence cache is generated, and gitignored")
def test_served_features_equal_training_features():
    """Same program, same run record: the live feature builder reproduces features.csv for the execution model."""
    code = {}
    for line in (DS / "annotations" / "tier0c_student_synthetic_v2.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        code[row["row_id"]] = (row.get("static") or {}).get("source_code")
    records = {}
    for line in CACHE.open(encoding="utf-8"):
        rec = json.loads(line)
        if rec["row_id"] in code:
            records[rec["row_id"]] = rec
    names = json.loads((DS / "models" / "metrics_v1.json").read_text(encoding="utf-8"))["execution"]["features"]
    checked = 0
    for row in csv.DictReader((DS / "features" / "features.csv").open(encoding="utf-8", newline="")):
        rid = row["row_id"]
        if rid not in records or not code.get(rid) or not records[rid].get("compiled"):
            continue
        served = model_runner.code_features(code[rid], "cpp", run_record=records[rid])
        for name in names:
            stored = math.nan if row[name] in ("", "nan", "NaN") else float(row[name])
            value = served.get(name)
            value = math.nan if value is None else float(value)
            assert (math.isnan(stored) and math.isnan(value)) or abs(stored - value) < 1e-9, (rid, name, stored, value)
        checked += 1
        if checked == 40:
            break
    assert checked == 40


def test_tests_for_problem_maps_stdin_and_refuses_function_tests():
    class TC:
        def __init__(self, i, inp, out):
            self.id, self.input_json, self.expected_output_json = i, json.dumps(inp), json.dumps(out)

    class Query:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *_):
            return self

        def order_by(self, *_):
            return self

        def all(self):
            return self.rows

    class Db:
        def __init__(self, rows):
            self.rows = rows

        def query(self, _):
            return Query(self.rows)

    assert run_record.tests_for_problem(Db([TC("a", {"stdin": "1\n"}, "2\n"), TC("b", {"stdin": "2\n"}, 3)]), "p") == [
        {"input": "1\n", "output": "2\n"}, {"input": "2\n", "output": "3"}]
    assert run_record.tests_for_problem(Db([TC("a", {"args": [1]}, 2)]), "p") == []


def test_no_tests_or_a_forbidden_directive_never_runs_anything(monkeypatch):
    monkeypatch.setattr(run_record.shutil, "copy", lambda *a: (_ for _ in ()).throw(AssertionError("ran")))
    assert run_record.build_run_record(OFF_BY_ONE, []) is None
    assert run_record.build_run_record('#include "/etc/passwd"\nint main(){}', TESTS) is None


def test_on_by_default_and_schedules_no_shadow_run():
    # "on" measures the record before the diagnosis (on the background worker); only "shadow" schedules here
    assert Settings().model_run_records == "on"
    assert run_record.schedule_shadow_prediction(1) is False


def test_only_one_record_at_a_time(monkeypatch):
    monkeypatch.setattr(settings, "model_run_records", "shadow")
    assert run_record._one_at_a_time.acquire(blocking=False)
    try:
        assert run_record.schedule_shadow_prediction(1) is False
    finally:
        run_record._one_at_a_time.release()


def test_a_background_failure_is_contained(monkeypatch):
    monkeypatch.setattr(settings, "model_run_records", "shadow")
    monkeypatch.setattr(run_record, "_store_shadow_prediction", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    assert run_record.schedule_shadow_prediction(1) is True
    for t in __import__("threading").enumerate():
        if t.name == "run-record-1":
            t.join(5)
    assert run_record._one_at_a_time.acquire(blocking=False)  # the slot came back
    run_record._one_at_a_time.release()


def test_shadow_record_is_weightless_and_uses_the_execution_model():
    record = {"compiled": True, "warnings": {}, "tests": {"results": [{"status": "wrong"}]}, "cf": {"classes": {}}}
    rec = model_runner.execution_shadow_record(OFF_BY_ONE, record)
    assert rec.evidence_code == "MODEL_SHADOW" and rec.weight == 0.0 and rec.direction == "neutral"
    assert rec.details["variant"] == "execution"


@pytest.mark.skipif(os.name != "posix" or not shutil.which("g++"), reason="needs Linux and g++")
def test_a_real_submission_gives_a_full_record_inside_the_sandbox():
    """The whole path: copy the worker, run it through run_in_sandbox, parse its record, predict."""
    record = run_record.build_run_record(OFF_BY_ONE, TESTS)
    assert record and record["compiled"] and record["tests"]["results"][0]["status"] == "wrong"
    assert record["cf"]["classes"]["CPP_LOOP_BOUNDARY"]["fix_all"] == 1
    assert record["runtime"]["sanitizer"]["complete"] is True
    assert model_runner.execution_shadow_record(OFF_BY_ONE, record).details["n_missing"] < 60


@pytest.mark.skipif(os.name != "posix" or not shutil.which("g++"), reason="needs Linux and g++")
def test_student_output_cannot_forge_the_record():
    forged = ('#include <iostream>\nint main(){std::cout<<"{\\"compiled\\":true,\\"forged\\":1}";return 0;}\n')
    record = run_record.build_run_record(forged, TESTS)
    assert record and "forged" not in record and record["tests"]["results"][0]["status"] == "wrong"
