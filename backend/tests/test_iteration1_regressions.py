"""Regression tests for the Iteration 1 QA findings.

Each test names the defect it guards: a correct program reported as UNCERTAIN,
conflict evidence that raised confidence, a wrong answer logged as a runtime
error, duplicate attempt numbers, hints that skipped levels, and C++ that could
not run on Windows.
"""
import shutil
import threading

import pytest

from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import (
    Diagnosis, EvidenceItem, HintEvent, LearnerState, LearnerStateHistory, Student, Submission, TestResult,
)
from backend.app.diagnosis.rules import aggregate_scores
from backend.app.services.submission_service import SubmissionService

CORRECT_P01 = "def sum_first_n(n):\n    total = 0\n    for i in range(n):\n        total += i\n    return total\n"
OFF_BY_ONE_P01 = "def sum_first_n(n):\n    total = 0\n    for i in range(n + 1):\n        total += i\n    return total\n"


@pytest.fixture
def student(db):
    st = Student(display_name="QA regression student", is_synthetic=False)
    db.add(st)
    db.commit()
    db.refresh(st)
    yield st
    # Other modules count students in the shared test database.
    db.rollback()
    sub_ids = [s.id for s in db.query(Submission.id).filter(Submission.student_id == st.id)]
    for model in (HintEvent, EvidenceItem, TestResult, Diagnosis):
        db.query(model).filter(model.submission_id.in_(sub_ids)).delete(synchronize_session=False)
    for model in (LearnerStateHistory, LearnerState):
        db.query(model).filter(model.student_id == st.id).delete(synchronize_session=False)
    db.query(Submission).filter(Submission.student_id == st.id).delete(synchronize_session=False)
    db.query(Student).filter(Student.id == st.id).delete(synchronize_session=False)
    db.commit()


def test_correct_submission_is_no_misconception_without_review(db, student):
    svc = SubmissionService()
    sub = svc.create_submission(db, student.id, "P01", CORRECT_P01)
    r = svc.run_and_analyze(db, sub.id)
    assert r["execution_status"] == "success"
    for mode in ("current_only", "history_aware"):
        assert r[mode]["primary_misconception"] == "NO_MISCONCEPTION", r[mode]
        assert r[mode]["requires_teacher_review"] is False
    assert r["hint"] is None


def test_conflict_evidence_lowers_the_score():
    support = EvidenceRecord(source_type="test", evidence_code="X", misconception_id="M01_LOOP_BOUNDARY",
                             direction="support", weight=0.35, description="")
    conflict = EvidenceRecord(source_type="test", evidence_code="Y", misconception_id="M01_LOOP_BOUNDARY",
                              direction="conflict", weight=-0.20, description="")
    assert aggregate_scores([support, conflict])["M01_LOOP_BOUNDARY"] < aggregate_scores([support])["M01_LOOP_BOUNDARY"]


def test_wrong_answer_is_not_a_runtime_error(db, student):
    svc = SubmissionService()
    sub = svc.create_submission(db, student.id, "P01", OFF_BY_ONE_P01)
    r = svc.run_and_analyze(db, sub.id)
    assert r["execution_status"] == "wrong_answer"
    assert r["history_aware"]["primary_misconception"] == "M01_LOOP_BOUNDARY"


def test_first_hint_is_level_one_and_levels_escalate(db, student):
    from backend.app.api.submissions import _hint_target
    svc = SubmissionService()
    sub = svc.create_submission(db, student.id, "P05", "def square_number(x):\n    print(x * x)\n")
    r = svc.run_and_analyze(db, sub.id)
    assert r["history_aware"]["primary_misconception"] == "M03_MISSING_RETURN", r["history_aware"]
    assert r["history_aware"]["requires_teacher_review"] is False
    assert r["hint"]["level"] == 1
    _, levels = _hint_target(db, db.get(Submission, sub.id))
    assert max(levels) == 3
    events = db.query(HintEvent).filter(HintEvent.submission_id == sub.id).all()
    assert [e.hint_level for e in events] == [1]


def test_concurrent_submissions_get_distinct_attempt_numbers(seeded_db, student):
    from backend.app.db.database import SessionLocal
    numbers: list[int] = []
    lock = threading.Lock()

    def submit() -> None:
        db = SessionLocal()
        try:
            sub = SubmissionService().create_submission(db, student.id, "P02", "def count_positive(nums):\n    return 0\n")
            with lock:
                numbers.append(sub.attempt_number)
        finally:
            db.close()

    threads = [threading.Thread(target=submit) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(numbers) == list(range(1, 7))


@pytest.mark.skipif(shutil.which("g++") is None, reason="no g++ on PATH")
def test_cpp_program_runs_without_bubblewrap():
    """On Windows and macOS dev machines the binary must start (it used to fail on Windows)."""
    from backend.app.execution.cpp_runner import CppExecutionRunner
    src = "#include <iostream>\nint main(){int a; std::cin >> a; std::cout << a * 2;}\n"
    r = CppExecutionRunner().execute_with_stdin(src, "21\n", 10)
    assert r.status == "success", r
    assert r.stdout.strip() == "42"


@pytest.mark.parametrize("cond,flagged", [
    ("if (x = 0)", True), ("while (n = read())", True),
    ("if (n <= 1)", False), ("if (x >= 1 && x <= 10)", False), ("while (b != 0)", False), ("if (a == b)", False),
])
def test_assignment_in_condition_detector_ignores_comparisons(cond, flagged):
    from backend.app.analysis.cpp_static import CppStaticAnalyzer
    found = CppStaticAnalyzer()._detect_assign_vs_compare("int main() { " + cond + " { return 1; } }")
    assert bool(found) is flagged


def test_passing_submission_is_not_diagnosed_from_patterns_or_history(db, student):
    """A second passing attempt must stay NO_MISCONCEPTION when history exists."""
    svc = SubmissionService()
    src = "def sum_first_n(n):\n    total = 0\n    for i in range(n):\n        total += i\n    return total\n"
    for pid in ("P01", "P01"):
        sub = svc.create_submission(db, student.id, pid, src)
        r = svc.run_and_analyze(db, sub.id)
        assert r["history_aware"]["primary_misconception"] == "NO_MISCONCEPTION"
