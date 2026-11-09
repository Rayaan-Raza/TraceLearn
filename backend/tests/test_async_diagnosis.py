"""Background diagnosis (`model_async`): the request returns the test result, the worker diagnoses in order."""
from __future__ import annotations

import pytest

from backend.app.analysis import async_diagnosis
from backend.app.config import settings


@pytest.fixture
def async_on(monkeypatch):
    for name, value in (("model_async", True), ("model_diagnosis", "on"), ("model_variant", "execution"),
                        ("model_run_records", "on")):
        monkeypatch.setattr(settings, name, value)
    yield


def test_enabled_needs_every_setting(monkeypatch, async_on):
    assert async_diagnosis.enabled()
    monkeypatch.setattr(settings, "model_run_records", "shadow")
    assert not async_diagnosis.enabled()


def test_worker_runs_jobs_in_submission_order_and_tracks_pending(monkeypatch):
    seen = []
    monkeypatch.setattr(async_diagnosis, "diagnose_now", lambda sid: seen.append(sid))
    for sid in (11, 12, 13):
        async_diagnosis.enqueue(sid, student_id=7)
    async_diagnosis.wait_idle()
    assert seen == [11, 12, 13]
    assert not async_diagnosis.has_pending(7)


def test_a_failed_job_does_not_stop_the_worker(monkeypatch):
    seen = []

    def flaky(sid):
        if sid == 21:
            raise RuntimeError("boom")
        seen.append(sid)

    monkeypatch.setattr(async_diagnosis, "diagnose_now", flaky)
    async_diagnosis.enqueue(21, student_id=8)
    async_diagnosis.enqueue(22, student_id=8)
    async_diagnosis.wait_idle()
    assert seen == [22] and not async_diagnosis.has_pending(8)


def test_run_and_analyze_defers_failing_cpp(monkeypatch, async_on):
    from backend.app.services.submission_service import SubmissionService

    queued = []
    svc = SubmissionService()
    monkeypatch.setattr(svc, "execute", lambda db, sid: {"submission_id": sid, "execution_status": "wrong_answer",
                                                         "runtime_ms": 1.0, "stderr": "", "test_results": []})

    class Sub:
        student_id = 3
        source_code = "#include <iostream>\nint main() { std::cout << 1; }\n"
        from backend.app.db.models import ExecutionStatus
        execution_status = ExecutionStatus.WRONG_ANSWER

    class DB:
        def get(self, model, sid):
            return Sub()

    monkeypatch.setattr(async_diagnosis, "enqueue", lambda sid, student: queued.append((sid, student)))
    monkeypatch.setattr(svc, "analyze", lambda *a, **k: pytest.fail("analysis must not run in the request"))
    out = svc.run_and_analyze(DB(), 5)
    assert out["diagnosis_pending"] is True and out["current_only"] is None
    assert queued == [(5, 3)]
