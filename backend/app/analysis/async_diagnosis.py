"""Background diagnosis for failing C++ submissions (`model_async=true`).

The run record the `execution` model needs takes seconds to minutes (sanitizer builds, repair
counterfactuals). With `model_async` the student gets the test result at once and this worker
then measures the run record, collects the evidence (model included), diagnoses both modes and
updates the learner state.

Order matters: a learner state depends on the student's earlier submissions. So there is ONE
worker thread and ONE first-in-first-out queue per process, and while a student has a queued
submission every later submission of that student (passing or not, any language) is queued
behind it rather than diagnosed in the request. Run the API as one process when this is on;
across processes the order per student is not guaranteed.

Nothing is lost on a restart: `recover_pending` queues, in submission order, every executed
submission that has no diagnosis yet.
"""
from __future__ import annotations

import logging
import queue
import threading
from collections import Counter

from backend.app.config import settings

log = logging.getLogger(__name__)

_jobs: "queue.Queue[tuple[int, int]]" = queue.Queue()
_pending: Counter[int] = Counter()     # student id -> queued submissions
_lock = threading.Lock()
_worker: threading.Thread | None = None


def enabled() -> bool:
    return (settings.model_async and settings.model_diagnosis == "on"
            and settings.model_variant == "execution" and settings.model_run_records == "on")


def has_pending(student_id: int) -> bool:
    with _lock:
        return _pending[student_id] > 0


def enqueue(submission_id: int, student_id: int) -> None:
    global _worker
    with _lock:
        _pending[student_id] += 1
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="diagnosis-worker", daemon=True)
            _worker.start()
    _jobs.put((submission_id, student_id))


def diagnose_now(submission_id: int) -> None:
    """Evidence (with the run record and the model), both diagnoses and the learner state."""
    from backend.app.db.database import SessionLocal
    from backend.app.services.submission_service import SubmissionService

    db = SessionLocal()
    try:
        svc = SubmissionService()
        svc.analyze(db, submission_id, defer_model=False)
        svc.diagnose(db, submission_id)
    finally:
        db.close()


def _run() -> None:
    while True:
        submission_id, student_id = _jobs.get()
        try:
            diagnose_now(submission_id)
        except Exception:   # a background failure must never reach a student's request
            log.exception("background diagnosis failed for submission %s", submission_id)
        finally:
            with _lock:
                _pending[student_id] -= 1
                if _pending[student_id] <= 0:
                    del _pending[student_id]
            _jobs.task_done()


def wait_idle() -> None:
    """Block until every queued diagnosis is done (tests and batch runs)."""
    _jobs.join()


def recover_pending() -> int:
    """Queue executed submissions that never got a diagnosis (for example after a restart)."""
    if not enabled():
        return 0
    from backend.app.db.database import SessionLocal
    from backend.app.db.models import Diagnosis, Submission

    db = SessionLocal()
    try:
        done = db.query(Diagnosis.submission_id)
        rows = (db.query(Submission.id, Submission.student_id)
                .filter(Submission.execution_status.isnot(None), Submission.id.notin_(done))
                .order_by(Submission.id).all())
    finally:
        db.close()
    for sid, student in rows:
        enqueue(sid, student)
    return len(rows)
