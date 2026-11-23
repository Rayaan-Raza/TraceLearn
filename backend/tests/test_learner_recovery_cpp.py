"""Learner-state recovery and recurrence on C++ with the model on (task U3).

`test_learner_recovery.py` runs Python problems P05/P06 with the model, run records and the
background worker off. The product is a C++ tutor with the model on by default, so these tests run
real C++ submissions through `SubmissionService.run_and_analyze` with the shipped model settings
(`model_diagnosis=on`, `execution` variant, run records on, `model_first` fusion) and read the stored
`learner_states` and `learner_state_history` rows. No test writes a state by hand.

The misconception is CPP_LOOP_BOUNDARY (bank code CPP-M01, diagnostic tag `inclusive_upper_bound`).
Problems CP09 to CP12 all probe it, so a pass on one of them is a related success. CP13 probes a
different misconception (value-versus-position) and is the unrelated problem.

Two layers, because building a run record takes tens of seconds:

* Fast layer (runs in CI): the C++ programs are really compiled and run against the tests, but the
  run record is read from `fixtures/cpp_recovery_run_records.json`, which was recorded from the real
  sandbox. The real model then predicts from it.
* Slow layer (`TL_SLOW_CPP_RECOVERY=1`): no fixtures; the sandbox builds every run record. With
  `TL_SLOW_LOG=<path>` it writes the transitions, the commit and the settings to a JSON log.

Recording the fixtures: `TL_RECORD_RUN_RECORDS=1 python -m pytest backend/tests/test_learner_recovery_cpp.py -k record`.

Transitions are asserted in submission order (by id), not by wall-clock time.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from backend.app.config import settings
from backend.app.db.models import LearnerState, LearnerStateHistory, MisconceptionState as S, Student
from backend.app.services.submission_service import SubmissionService
from backend.tests.test_cpp_end_to_end import _problem, _remove_cpp_problem, _seed_cpp_problem

LB = "CPP_LOOP_BOUNDARY"
FIXTURE = Path(__file__).parent / "fixtures" / "cpp_recovery_run_records.json"
SYNTAX_ERROR = "int main( { return 0; }\n"
RECURRENCE_PROBLEMS = ("CP11", "CP12")

pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="needs g++ to run C++ submissions")


def _key(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _bug(pid: str) -> str:
    return _problem(pid)["misconception_variant_source"]


def _ok(pid: str) -> str:
    return _problem(pid)["reference_solution_source"]


@pytest.fixture(autouse=True)
def _shipped_model_settings(monkeypatch):
    """Override the suite's rule-engine default: the model on, as shipped, run synchronously."""
    monkeypatch.setattr(settings, "model_diagnosis", "on")
    monkeypatch.setattr(settings, "model_variant", "execution")
    monkeypatch.setattr(settings, "model_run_records", "on")
    monkeypatch.setattr(settings, "model_fusion", "model_first")
    monkeypatch.setattr(settings, "model_async", False)


@pytest.fixture
def recorded(monkeypatch):
    """Fast layer: serve the recorded run record for a program; remember any program with none."""
    if os.environ.get("TL_SLOW_CPP_RECOVERY") == "1" or os.environ.get("TL_RECORD_RUN_RECORDS") == "1":
        yield []
        return
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    missing: list[str] = []

    def fake_build(source, tests, language="cpp"):
        rec = records.get(_key(source))
        if rec is None:
            missing.append(_key(source))
        return rec

    monkeypatch.setattr("backend.app.analysis.run_record.build_run_record", fake_build)
    yield missing
    assert not missing, f"no recorded run record for program(s) {missing}; re-record the fixture"


@pytest.fixture
def cpp_student(db):
    student = Student(display_name=f"cpp-recovery-{uuid.uuid4().hex[:6]}")
    db.add(student)
    db.commit()
    db.refresh(student)
    sid = student.id
    seeded: dict[str, bool] = {}
    yield student, seeded
    for pid, inserted in seeded.items():
        _remove_cpp_problem(db, pid, sid, drop_problem=inserted)  # also deletes the student and its states
    db.commit()


class Run:
    def __init__(self, db, student, seeded):
        self.db, self.student, self.seeded, self.svc = db, student, seeded, SubmissionService()
        self.log: list[dict] = []

    def submit(self, pid: str, source: str) -> dict:
        if pid not in self.seeded:
            self.seeded[pid] = _seed_cpp_problem(self.db, _problem(pid))
        sub = self.svc.create_submission(self.db, self.student.id, pid, source)
        result = self.svc.run_and_analyze(self.db, sub.id)
        state, hist = self.state(), self.history()
        self.log.append({"submission_id": sub.id, "problem": pid, "execution_status": result.get("execution_status"),
                         "diagnosis": (result.get("history_aware") or {}).get("primary_misconception"),
                         "state": state.state.value if state else None,
                         "confidence": round(state.confidence, 3) if state else None,
                         "rule": hist[-1].reason_json and json.loads(hist[-1].reason_json).get("rule") if hist else None})
        return result

    def state(self) -> LearnerState | None:
        self.db.expire_all()
        return self.db.query(LearnerState).filter_by(student_id=self.student.id, misconception_id=LB).one_or_none()

    def history(self) -> list[LearnerStateHistory]:
        self.db.expire_all()
        return (self.db.query(LearnerStateHistory).filter_by(student_id=self.student.id, misconception_id=LB)
                .order_by(LearnerStateHistory.id).all())

    def states(self) -> list[S]:
        return [h.new_state for h in self.history()]

    def make_persistent(self) -> None:
        self.submit("CP09", _bug("CP09"))
        self.submit("CP10", _bug("CP10"))
        assert self.state().state == S.PERSISTENT


@pytest.fixture
def run(db, cpp_student, recorded):
    student, seeded = cpp_student
    return Run(db, student, seeded)


def _rule(h: LearnerStateHistory) -> str:
    return json.loads(h.reason_json).get("rule")


# --------------------------------------------------------------------------------- positive path
def _positive_sequence(run: Run, recurrence_problem: str) -> None:
    run.submit("CP09", _bug("CP09"))
    assert run.state().state == S.NEW
    run.submit("CP10", _bug("CP10"))
    assert run.state().state == S.PERSISTENT
    run.submit("CP09", _ok("CP09"))
    assert run.state().state == S.IMPROVING
    run.submit("CP10", _ok("CP10"))
    assert run.state().state == S.RESOLVED, "a pass on a second probing problem resolves it"
    run.submit(recurrence_problem, _bug(recurrence_problem))


def _check_recurrence(run: Run) -> None:
    hist = run.history()
    # Stored transitions are in submission order, one per step, and never rewritten.
    assert [h.new_state for h in hist[:4]] == [S.NEW, S.PERSISTENT, S.IMPROVING, S.RESOLVED]
    assert [h.submission_id for h in hist] == sorted(h.submission_id for h in hist)
    last = hist[-1]
    assert last.old_state == S.RESOLVED
    # The rule (backend/app/learner_model/updater.py): strong evidence after RESOLVED recurs; weak
    # evidence goes to the teacher. Which one a given program gets depends on the model's confidence.
    confidence = run.state().confidence
    if confidence >= 0.45:
        assert last.new_state == S.RECURRED and _rule(last) == "strong_evidence_after_resolved"
    else:
        assert last.new_state == S.REQUIRES_TEACHER_REVIEW and _rule(last) == "weak_evidence_after_resolved"


@pytest.mark.parametrize("recurrence_problem", RECURRENCE_PROBLEMS)
def test_recovery_then_recurrence_on_cpp(run, recurrence_problem):
    _positive_sequence(run, recurrence_problem)
    _check_recurrence(run)


# --------------------------------------------------------------------------------- negative cases
def test_a_pass_on_a_problem_that_does_not_probe_it_changes_nothing(run):
    run.make_persistent()
    before, rows = run.state().confidence, len(run.history())
    run.submit("CP13", _ok("CP13"))  # CP13 probes the value-versus-position belief, not loop bounds
    assert run.state().state == S.PERSISTENT and run.state().confidence == pytest.approx(before)
    assert len(run.history()) == rows


def test_a_syntax_error_changes_nothing(run):
    run.make_persistent()
    before, rows = run.state().confidence, len(run.history())
    run.submit("CP11", SYNTAX_ERROR)
    assert run.log[-1]["execution_status"] == "syntax_error"
    assert run.state().state == S.PERSISTENT and run.state().confidence == pytest.approx(before)
    assert len(run.history()) == rows


def _force_model(monkeypatch, label: str, probability: float, abstained: bool) -> None:
    """Replace only the classifier's answer; execution, evidence and the learner-state rules stay real."""
    from backend.app.analysis import model_runner
    from backend.app.diagnosis.xgb_classifier import ModelPrediction

    def fake(source, language="cpp", warnings=None, run_record=None):
        return ModelPrediction(
            variant="execution", model_sha256="0" * 64, top_label=label, top_probability=probability,
            abstained=abstained, threshold=0.63, temperature=1.0,
            probabilities={label: probability}, top_k=((label, probability),), n_features=100, n_missing=0)

    monkeypatch.setattr(model_runner, "predict_source", fake)


def test_a_confident_other_error_failure_changes_nothing(run, monkeypatch):
    """`model_first`: the model's "none of my classes" leaves the diagnosis UNCERTAIN, so no state moves."""
    run.make_persistent()
    before, rows = run.state().confidence, len(run.history())
    _force_model(monkeypatch, "CPP_OTHER_ERROR", 0.9, abstained=False)
    run.submit("CP11", _bug("CP11"))
    assert run.log[-1]["diagnosis"] != LB
    assert run.state().state == S.PERSISTENT and run.state().confidence == pytest.approx(before)
    assert len(run.history()) == rows


def test_an_abstained_failure_falls_back_to_the_rules_and_does_not_resolve_anything(run, monkeypatch):
    """The work plan expected "no change" here. With `model_first`, an abstention falls back to the
    rule scores (docs/LEARNER_STATE_RULES.md), and this program's failing diagnostic tests still name
    the misconception, so the state is refreshed: it stays PERSISTENT. It never moves towards RESOLVED."""
    run.make_persistent()
    _force_model(monkeypatch, LB, 0.2, abstained=True)
    run.submit("CP11", _bug("CP11"))
    assert run.log[-1]["diagnosis"] == LB
    assert run.state().state == S.PERSISTENT


# --------------------------------------------------------------------------------- slow layer
@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("TL_SLOW_CPP_RECOVERY") != "1", reason="set TL_SLOW_CPP_RECOVERY=1 (about 1 minute)")
@pytest.mark.parametrize("recurrence_problem", RECURRENCE_PROBLEMS)
def test_slow_real_sandbox_run_records(run, recurrence_problem):
    """Same sequence, no fixtures: the real sandbox builds every run record."""
    _positive_sequence(run, recurrence_problem)
    _check_recurrence(run)
    path = os.environ.get("TL_SLOW_LOG")
    if path:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        log = {"commit": commit, "recurrence_problem": recurrence_problem,
               "settings": {k: str(getattr(settings, k)) for k in
                            ("model_diagnosis", "model_variant", "model_run_records", "model_fusion", "model_async",
                             "execution_timeout_seconds", "max_memory_mb")},
               "model_sha256": hashlib.sha256((Path(settings.model_dir) / "xgb_execution_v1.json").read_bytes()).hexdigest(),
               "steps": run.log}
        existing = json.loads(Path(path).read_text()) if Path(path).exists() else []
        Path(path).write_text(json.dumps(existing + [log], indent=1), encoding="utf-8")


@pytest.mark.skipif(os.environ.get("TL_RECORD_RUN_RECORDS") != "1", reason="only to re-record the fixture")
def test_record_run_records(run, monkeypatch):
    """Record the real sandbox's run record for every failing program the fast layer submits."""
    from backend.app.analysis import run_record

    real, records = run_record.build_run_record, {}

    def spy(source, tests, language="cpp"):
        rec = real(source, tests, language)
        if rec is not None:
            records[_key(source)] = rec
        return rec

    monkeypatch.setattr(run_record, "build_run_record", spy)
    run.make_persistent()
    run.submit("CP11", _bug("CP11"))
    run.submit("CP12", _bug("CP12"))
    FIXTURE.parent.mkdir(exist_ok=True)
    FIXTURE.write_text(json.dumps(records, sort_keys=True), encoding="utf-8")
    assert len(records) == 4
