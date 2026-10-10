"""C++ misconceptions must reach a diagnosis, a learner state, and hints.

Iteration 1 of the FYP blueprint asks for 4 to 6 misconceptions that work end
to end. The Python bank covers `M01_LOOP_BOUNDARY`, `M02_INDEX_VALUE`, and
`M03_MISSING_RETURN`. The C++ diagnostic bank covers `CPP-M01` to `CPP-M08`
through `backend.app.diagnosis.cpp_mapping`, so a failing C++ diagnostic test
must reach a scored diagnosis, a learner-state row, and the bank's hints.

Three kinds of test live here.

1. Mapping tests. They read `data/cpp_diagnostics/problems.json` at run time.
   A new bank tag without a mapping fails the suite instead of failing quietly
   at runtime, which is how the gap stayed open before.
2. An end-to-end test that inserts the test results the C++ runner would
   produce. It needs no compiler.
3. An end-to-end test that submits the misconception variant for real. It
   needs `g++` and runs on the Linux CI runner.
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

# The `Test*` model classes are imported where they are used. A module-level
# name that starts with "Test" makes pytest try to collect it as a test class.
from backend.app.db.models import (
    Diagnosis,
    EvidenceItem,
    ExecutionStatus,
    HintEvent,
    LearnerState,
    LearnerStateHistory,
    Problem,
    ProblemHint,
    ProblemSolution,
    Student,
    Submission,
)

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT / "data" / "cpp_diagnostics" / "problems.json"
PYTHON_BANK = ROOT / "data" / "problems" / "problems.json"
EXAMPLE_PROBLEM = "CP09"


def _cpp_bank() -> list[dict]:
    return json.loads(BANK.read_text(encoding="utf-8"))["problems"]


def _python_bank() -> list[dict]:
    return json.loads(PYTHON_BANK.read_text(encoding="utf-8"))["problems"]


def _problem(problem_id: str) -> dict:
    return next(p for p in _cpp_bank() if p["id"] == problem_id)


# ---------------------------------------------------------------------------
# mapping
# ---------------------------------------------------------------------------
def test_every_cpp_bank_tag_maps_to_a_scored_code():
    from backend.app.diagnosis.cpp_mapping import TAG_TO_CODE
    from backend.app.diagnosis.taxonomy import SCORED_MISCONCEPTIONS

    used = {
        case["diagnostic_tag"]
        for problem in _cpp_bank()
        for case in problem["test_cases"]
        if case["db_type"] == "diagnostic"
    }
    assert used, "the bank must hold diagnostic tests"
    assert used == set(TAG_TO_CODE["cpp"]), (
        "the C++ tag table and the bank disagree")
    for tag in sorted(used):
        code = TAG_TO_CODE["cpp"][tag]
        assert code in SCORED_MISCONCEPTIONS, (
            f"tag {tag!r} maps to {code}, which the diagnosis never scores")


def test_every_python_bank_tag_maps_to_a_scored_code():
    from backend.app.diagnosis.cpp_mapping import TAG_TO_CODE
    from backend.app.diagnosis.taxonomy import SCORED_MISCONCEPTIONS

    used = {
        case["diagnostic_tag"]
        for problem in _python_bank()
        for case in problem["test_cases"]
        if case.get("diagnostic_tag")
    }
    # `index_value` is the tag the Python bank really emits. The old table held
    # `index_vs_value`, so four diagnostic tests produced no evidence at all.
    assert "index_value" in used
    for tag in sorted(used):
        assert TAG_TO_CODE["python"][tag] in SCORED_MISCONCEPTIONS, tag


def test_language_disambiguates_the_shared_tag():
    from backend.app.diagnosis.cpp_mapping import code_for_diagnostic_tag

    assert code_for_diagnostic_tag("python", "upper_boundary") == "M01_LOOP_BOUNDARY"
    assert code_for_diagnostic_tag("cpp", "upper_boundary") == "CPP_LOOP_BOUNDARY"


def test_every_bank_misconception_maps_to_a_scored_code():
    from backend.app.diagnosis.cpp_mapping import BANK_TO_BACKEND
    from backend.app.diagnosis.taxonomy import SCORED_MISCONCEPTIONS

    codes = {p["primary_misconception_id"] for p in _cpp_bank()}
    assert codes == {f"CPP-M0{i}" for i in range(1, 9)}
    for bank_code in sorted(codes):
        backend_code = BANK_TO_BACKEND[bank_code]
        assert backend_code in SCORED_MISCONCEPTIONS, (
            f"{bank_code} maps to {backend_code}, which is never scored")


def test_mapping_round_trips_through_the_reverse_table():
    from backend.app.diagnosis.cpp_mapping import BANK_TO_BACKEND, BACKEND_TO_BANK

    for bank_code, backend_code in BANK_TO_BACKEND.items():
        assert bank_code in BACKEND_TO_BANK[backend_code], bank_code


def test_cpp_evidence_codes_carry_a_real_weight():
    from backend.app.analysis.evidence_models import EvidenceRecord
    from backend.app.diagnosis.confidence import apply_evidence_weights

    support = EvidenceRecord(
        source_type="test", evidence_code="DIAGNOSTIC_INCLUSIVE_UPPER_BOUND_FAIL",
        misconception_id="CPP_LOOP_BOUNDARY", direction="support", weight=0.0,
        description="diagnostic test failed")
    [weighted] = apply_evidence_weights([support])
    assert weighted.weight >= 0.30, "a C++ diagnostic failure must not fall back to 0.05"

    static = EvidenceRecord(
        source_type="static", evidence_code="CPP_LOOP_LE_BOUND",
        misconception_id="CPP_LOOP_BOUNDARY", direction="support", weight=0.0,
        description="loop uses <=")
    [weighted_static] = apply_evidence_weights([static])
    assert weighted_static.weight >= 0.30, "a C++ static pattern must not fall back to 0.05"


def test_aggregate_scores_includes_cpp_codes():
    from backend.app.analysis.evidence_models import EvidenceRecord
    from backend.app.diagnosis.confidence import apply_evidence_weights
    from backend.app.diagnosis.rules import aggregate_scores

    records = [EvidenceRecord(
        source_type="test", evidence_code="DIAGNOSTIC_INCLUSIVE_UPPER_BOUND_FAIL",
        misconception_id="CPP_LOOP_BOUNDARY", direction="support", weight=0.0,
        description="diagnostic test failed")]
    scores = aggregate_scores(apply_evidence_weights(records))
    assert scores["CPP_LOOP_BOUNDARY"] > 0.0
    assert len(scores) >= 4, "fewer than four misconceptions are scored"


# ---------------------------------------------------------------------------
# end to end without a compiler
# ---------------------------------------------------------------------------
def _seed_cpp_problem(db, problem: dict) -> None:
    from backend.app.db.models import TestCase as TestCaseModel, TestType as TestTypeModel

    db.add(Problem(
        id=problem["id"], slug=problem["slug"], title=problem["title"],
        description=problem["statement_markdown"], function_name="main",
        concept_tags="[]", prerequisite_tags="[]", starter_code="",
        language="cpp", language_standard="cpp17",
        topic=problem["primary_topic"], difficulty=problem["difficulty"],
        created_by_user_id=None,
    ))
    for case in problem["test_cases"]:
        db.add(TestCaseModel(
            id=case["id"], problem_id=problem["id"], test_type=TestTypeModel(case["db_type"]),
            name=case["name"], input_json=json.dumps({"stdin": case["stdin"]}),
            expected_output_json=json.dumps(case["expected_output"]),
            diagnostic_tag=case.get("diagnostic_tag"),
            time_limit_ms=case.get("time_limit_ms"),
            memory_limit_mb=case.get("memory_limit_mb"),
        ))
    for hint in problem["hints"]:
        db.add(ProblemHint(
            problem_id=problem["id"],
            misconception_id=hint["related_misconception_id"],
            level=int(hint["order"]), text=hint["hint_text"],
        ))
    db.commit()


def _remove_cpp_problem(db, problem_id: str, student_id: int) -> None:
    from backend.app.db.models import TestCase as TestCaseModel, TestResult as TestResultModel

    submission_ids = [row.id for row in db.query(Submission).filter(Submission.problem_id == problem_id)]
    if submission_ids:
        db.query(HintEvent).filter(HintEvent.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        db.query(EvidenceItem).filter(EvidenceItem.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        db.query(Diagnosis).filter(Diagnosis.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        db.query(TestResultModel).filter(TestResultModel.submission_id.in_(submission_ids)).delete(synchronize_session=False)
        db.query(Submission).filter(Submission.id.in_(submission_ids)).delete(synchronize_session=False)
    db.query(LearnerStateHistory).filter(LearnerStateHistory.student_id == student_id).delete(synchronize_session=False)
    db.query(LearnerState).filter(LearnerState.student_id == student_id).delete(synchronize_session=False)
    db.query(ProblemHint).filter(ProblemHint.problem_id == problem_id).delete(synchronize_session=False)
    db.query(TestCaseModel).filter(TestCaseModel.problem_id == problem_id).delete(synchronize_session=False)
    db.query(ProblemSolution).filter(ProblemSolution.problem_id == problem_id).delete(synchronize_session=False)
    db.query(Problem).filter(Problem.id == problem_id).delete(synchronize_session=False)
    db.query(Student).filter(Student.id == student_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def cpp_submission(db):
    """A C++ submission on CP09 whose diagnostic tests fail, as a variant does."""
    from backend.app.db.models import TestResult as TestResultModel

    problem = _problem(EXAMPLE_PROBLEM)
    student = Student(display_name=f"cpp-e2e-{uuid.uuid4().hex[:6]}")
    db.add(student)
    db.commit()
    db.refresh(student)
    _seed_cpp_problem(db, problem)
    submission = Submission(
        student_id=student.id, problem_id=problem["id"],
        source_code=problem["misconception_variant_source"],
        execution_status=ExecutionStatus.RUNTIME_ERROR, stderr="",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    for case in problem["test_cases"]:
        db.add(TestResultModel(
            submission_id=submission.id, test_case_id=case["id"],
            # The variant fails every diagnostic test for its tag and passes
            # the rest, which is the shape the C++ runner produces.
            passed=case["db_type"] != "diagnostic",
            actual_output_json="null", expected_output_json=json.dumps(case["expected_output"]),
        ))
    db.commit()
    try:
        yield {"problem": problem, "student": student, "submission": submission}
    finally:
        _remove_cpp_problem(db, problem["id"], student.id)


def test_cpp_diagnostic_failure_reaches_diagnosis_state_and_hints(db, cpp_submission):
    from backend.app.api.submissions import _hint_target
    from backend.app.services.submission_service import SubmissionService

    problem = cpp_submission["problem"]
    student = cpp_submission["student"]
    submission = cpp_submission["submission"]
    service = SubmissionService()
    service.analyze(db, submission.id)
    result = service.diagnose(db, submission.id)

    history_aware = result["history_aware"]
    assert history_aware["primary_misconception"] == "CPP_LOOP_BOUNDARY", history_aware
    assert history_aware["requires_teacher_review"] is False

    state = (
        db.query(LearnerState)
        .filter(LearnerState.student_id == student.id,
                LearnerState.misconception_id == "CPP_LOOP_BOUNDARY")
        .one_or_none()
    )
    assert state is not None, "the C++ misconception must reach the learner model"

    tag, levels = _hint_target(db, submission)
    assert tag == "CPP_LOOP_BOUNDARY"
    assert sorted(levels) == [1, 2, 3]
    bank_hint = next(h for h in problem["hints"] if int(h["order"]) == 1)
    assert levels[1] == bank_hint["hint_text"], (
        "the bank's problem hints must be selected, not the generic hint")


def test_cpp_diagnosis_is_recorded_on_the_submission(db, cpp_submission):
    from backend.app.services.submission_service import SubmissionService

    submission = cpp_submission["submission"]
    service = SubmissionService()
    service.analyze(db, submission.id)
    service.diagnose(db, submission.id)
    row = (
        db.query(Diagnosis)
        .filter(Diagnosis.submission_id == submission.id)
        .order_by(Diagnosis.id.desc())
        .first()
    )
    assert row is not None
    assert row.primary_misconception == "CPP_LOOP_BOUNDARY"
    assert row.primary_confidence >= 0.35


# ---------------------------------------------------------------------------
# end to end with a compiler
# ---------------------------------------------------------------------------
@pytest.mark.skipif(shutil.which("g++") is None, reason="no g++ on PATH")
def test_cpp_variant_submission_reaches_diagnosis_end_to_end(db, cpp_submission):
    from backend.app.services.submission_service import SubmissionService

    submission = cpp_submission["submission"]
    service = SubmissionService()
    result = service.run_and_analyze(db, submission.id)
    history_aware = result["history_aware"]
    assert history_aware["primary_misconception"] == "CPP_LOOP_BOUNDARY", history_aware
    assert history_aware["primary_confidence"] >= 0.35

    state = (
        db.query(LearnerState)
        .filter(LearnerState.student_id == cpp_submission["student"].id,
                LearnerState.misconception_id == "CPP_LOOP_BOUNDARY")
        .one_or_none()
    )
    assert state is not None
