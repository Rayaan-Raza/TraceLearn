"""The model path must never break a diagnosis and must respect the off/shadow/on switch."""
from __future__ import annotations

import pytest

from backend.app.analysis import model_runner
from backend.app.config import settings

ASSIGN = '#include <stdio.h>\nint main(){int n,f=0;scanf("%d",&n);if(f=1){printf("x");}for(int i=0;i<=n;i++){f+=i;}return 0;}\n'


@pytest.fixture(autouse=True)
def _mode(monkeypatch):
    monkeypatch.setattr(settings, "model_diagnosis", "off")
    yield


def test_off_runs_nothing(monkeypatch):
    monkeypatch.setattr(model_runner, "_classifier", lambda *a: (_ for _ in ()).throw(AssertionError("loaded")))
    assert model_runner.model_records(ASSIGN) == []


def test_shadow_is_neutral_and_weightless(monkeypatch):
    monkeypatch.setattr(settings, "model_diagnosis", "shadow")
    recs = model_runner.model_records(ASSIGN)
    assert len(recs) == 1 and recs[0].evidence_code == "MODEL_SHADOW"
    assert recs[0].direction == "neutral" and recs[0].weight == 0.0
    assert recs[0].details["top_label"]


def test_on_emits_a_model_record(monkeypatch):
    monkeypatch.setattr(settings, "model_diagnosis", "on")
    recs = model_runner.model_records(ASSIGN)
    assert len(recs) == 1 and recs[0].source_type == "model"
    assert recs[0].evidence_code in {"MODEL_PREDICTION", "MODEL_ABSTAINED", "MODEL_OTHER_ERROR"}


def test_missing_warnings_block_forces_abstain_in_on_mode(monkeypatch):
    monkeypatch.setattr(settings, "model_diagnosis", "on")
    pred = model_runner.predict_source(ASSIGN)
    if pred.n_missing / pred.n_features > model_runner.MAX_MISSING_SHARE:
        assert model_runner.model_records(ASSIGN)[0].evidence_code != "MODEL_PREDICTION"


def test_failure_never_raises(monkeypatch):
    monkeypatch.setattr(settings, "model_diagnosis", "on")
    monkeypatch.setattr(model_runner, "_classifier", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert model_runner.model_records(ASSIGN) == []


def test_oversized_or_empty_source_is_skipped(monkeypatch):
    monkeypatch.setattr(settings, "model_diagnosis", "on")
    assert model_runner.model_records("x" * (model_runner.MAX_SOURCE_CHARS + 1)) == []
    assert model_runner.model_records("   ") == []
