"""Execution and repair evidence for a live submission, for the `execution` model variant.

This compiles and runs many edited copies of a student's program, so it takes 10-35 s (up to a few
minutes) and never runs in a request. `schedule_shadow_prediction` runs it on a background thread after
the student already has their result, one submission at a time, and skips when one is in progress.
Its only output is a weightless MODEL_SHADOW evidence row, so nothing the student or teacher sees changes.

Every process stays inside `run_in_sandbox`. The address-space cap is lifted for this one call because
sanitizer builds reserve terabytes of virtual memory. Plain builds keep their own cap inside the worker
(`sandbox_runner/process.py`), but a sanitizer build has none, so the container needs a memory limit.
"""
from __future__ import annotations

import json
import logging
import shutil
import threading
from pathlib import Path
from typing import Any

from backend.app.config import settings

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
# What the worker imports. The sandbox hides the app directory, so these are copied in.
WORKER_FILES = ("run_record_worker.py", "counterfactual_evidence.py", "repair_verify.py", "repair_extra.py", "codestream_static.py")
WORKER_TIMEOUT_S = 330
WORKER_OUTPUT_BYTES = 64 * 1024 * 1024   # also the file-size cap, and compiled sanitizer binaries are large
WORKER_MEMORY_MB = 2048
_one_at_a_time = threading.BoundedSemaphore(1)


def tests_for_problem(db, problem_id: str) -> list[dict[str, str]]:
    """The problem's stdin/stdout tests, in the shape the worker takes. Empty when a test has no stdin form."""
    from backend.app.db.models import TestCase

    out = []
    for tc in db.query(TestCase).filter(TestCase.problem_id == problem_id).order_by(TestCase.id).all():
        payload = json.loads(tc.input_json or "{}")
        expected = json.loads(tc.expected_output_json or "null")
        stdin = payload.get("stdin") if isinstance(payload, dict) else None
        if not isinstance(stdin, str) or expected is None:
            return []
        out.append({"input": stdin, "output": expected if isinstance(expected, str) else str(expected)})
    return out


def _copy_worker(into: Path) -> None:
    (into / "scripts").mkdir()
    for name in WORKER_FILES:
        shutil.copy(ROOT / "scripts" / name, into / "scripts" / name)
    shutil.copytree(ROOT / "sandbox_runner", into / "sandbox_runner", ignore=shutil.ignore_patterns("__pycache__"))


def build_run_record(source: str, tests: list[dict[str, str]], language: str = "cpp") -> dict[str, Any] | None:
    """One submission's run record, or None if it could not be produced. Never raises."""
    from backend.app.execution.sandbox import check_cpp_source, new_workdir, run_in_sandbox

    if not tests or check_cpp_source(source):
        return None
    try:
        tmp = new_workdir()
        try:
            workdir = Path(tmp.name)
            _copy_worker(workdir)
            res = run_in_sandbox(["python3", "scripts/run_record_worker.py"], workdir,
                                 stdin_data=json.dumps({"code": source, "lang": language, "tests": tests}),
                                 timeout=WORKER_TIMEOUT_S, memory_mb=WORKER_MEMORY_MB,
                                 output_bytes=WORKER_OUTPUT_BYTES, address_limit=False)
            if res.timed_out or res.returncode != 0:
                log.warning("run record worker failed: rc=%s timed_out=%s %s", res.returncode, res.timed_out, res.stderr[:300])
                return None
            record = json.loads(res.stdout)
            return record if isinstance(record, dict) else None
        finally:
            tmp.cleanup()
    except Exception:
        log.exception("run record failed; there is no execution prediction for this submission")
        return None


def _store_shadow_prediction(submission_id: int) -> None:
    from backend.app.analysis.model_runner import execution_shadow_record
    from backend.app.db.database import SessionLocal
    from backend.app.db.models import EvidenceDirection, EvidenceItem, EvidenceSourceType, Submission

    db = SessionLocal()
    try:
        sub = db.get(Submission, submission_id)
        if not sub:
            return
        record = build_run_record(sub.source_code, tests_for_problem(db, sub.problem_id))
        rec = execution_shadow_record(sub.source_code, record) if record else None
        if rec is None:
            return
        db.add(EvidenceItem(submission_id=submission_id, source_type=EvidenceSourceType(rec.source_type),
                            evidence_code=rec.evidence_code, misconception_id=rec.misconception_id,
                            direction=EvidenceDirection(rec.direction), weight=rec.weight,
                            description=rec.description, details_json=json.dumps(rec.details)))
        db.commit()
    finally:
        db.close()


def schedule_shadow_prediction(submission_id: int) -> bool:
    """Start the background prediction when `model_run_records` is on. Returns whether it started."""
    if settings.model_run_records != "shadow" or not _one_at_a_time.acquire(blocking=False):
        return False

    def work() -> None:
        try:
            _store_shadow_prediction(submission_id)
        except Exception:  # a background failure must not surface anywhere a student can see
            log.exception("shadow prediction failed for submission %s", submission_id)
        finally:
            _one_at_a_time.release()

    threading.Thread(target=work, name=f"run-record-{submission_id}", daemon=True).start()
    return True
