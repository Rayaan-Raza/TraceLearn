"""SQLAlchemy ORM models for TraceLearn POC."""
from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.database import Base


class UserRole(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"

class TestType(str, enum.Enum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    DIAGNOSTIC = "diagnostic"

class ExecutionStatus(str, enum.Enum):
    SUCCESS = "success"
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    WRONG_ANSWER = "wrong_answer"  # ran cleanly, but at least one test failed
    TIMEOUT = "timeout"
    SYSTEM_ERROR = "system_error"

class EvidenceSourceType(str, enum.Enum):
    EXECUTION = "execution"
    TEST = "test"
    STATIC = "static"
    SEQUENCE = "sequence"
    HISTORY = "history"
    CONTEXT = "context"

class EvidenceDirection(str, enum.Enum):
    SUPPORT = "support"
    CONFLICT = "conflict"
    NEUTRAL = "neutral"

class DiagnosisMode(str, enum.Enum):
    CURRENT_ONLY = "current_only"
    HISTORY_AWARE = "history_aware"

class UncertaintyLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class MisconceptionState(str, enum.Enum):
    NEW = "NEW"
    PERSISTENT = "PERSISTENT"
    IMPROVING = "IMPROVING"
    RESOLVED = "RESOLVED"
    RECURRED = "RECURRED"
    REQUIRES_TEACHER_REVIEW = "REQUIRES_TEACHER_REVIEW"

class TeacherReviewAction(str, enum.Enum):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    CORRECT = "CORRECT"
    MARK_UNCERTAIN = "MARK_UNCERTAIN"

class VerificationStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    FAILED = "failed"

class User(Base):
    """Authenticated user with role. Students get a linked Student record."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    display_name: Mapped[str] = mapped_column(String(128), default="")
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    # Incremented on logout / password change; tokens carrying an older
    # version are rejected, which makes logout revoke every issued token.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(128))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submissions: Mapped[list["Submission"]] = relationship(back_populates="student")
    learner_states: Mapped[list["LearnerState"]] = relationship(back_populates="student")
    hint_events: Mapped[list["HintEvent"]] = relationship(back_populates="student")

class Problem(Base):
    __tablename__ = "problems"
    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    function_name: Mapped[str] = mapped_column(String(128))
    concept_tags: Mapped[str] = mapped_column(Text, default="[]")
    prerequisite_tags: Mapped[str] = mapped_column(Text, default="[]")
    starter_code: Mapped[str] = mapped_column(Text)
    # "python" (function-call tests) or "cpp" (stdin/stdout tests).
    language: Mapped[str] = mapped_column(String(16), default="python", server_default="python")
    # C++ standard for compile and run, for example "cpp17".
    language_standard: Mapped[str] = mapped_column(String(8), default="cpp17", server_default="cpp17")
    topic: Mapped[str] = mapped_column(String(64), default="", server_default="")
    difficulty: Mapped[str] = mapped_column(String(16), default="Easy", server_default="Easy")
    # Canonical bank metadata. Additive columns; old rows keep the defaults.
    input_spec: Mapped[str] = mapped_column(Text, default="", server_default="")
    output_spec: Mapped[str] = mapped_column(Text, default="", server_default="")
    constraints: Mapped[str] = mapped_column(Text, default="", server_default="")
    # NULL = part of the shared research dataset; otherwise the teacher who
    # created it. Custom problems are only visible to their owner and to
    # students they are assigned to.
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="problem")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="problem")
    solutions: Mapped[list["ProblemSolution"]] = relationship(back_populates="problem", cascade="all, delete-orphan")
    tags: Mapped[list["ProblemTag"]] = relationship(back_populates="problem", cascade="all, delete-orphan")
    hints: Mapped[list["ProblemHint"]] = relationship(back_populates="problem", cascade="all, delete-orphan")
    provenance: Mapped["ProblemProvenance | None"] = relationship(back_populates="problem", cascade="all, delete-orphan", uselist=False)
    quality_checks: Mapped[list["ProblemQualityCheck"]] = relationship(back_populates="problem", cascade="all, delete-orphan")

class TestCase(Base):
    __test__ = False
    __tablename__ = "test_cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    test_type: Mapped[TestType] = mapped_column(Enum(TestType))
    name: Mapped[str] = mapped_column(String(128))
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    expected_output_json: Mapped[str] = mapped_column(Text, default="null")
    diagnostic_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Per-test execution limits. NULL means "use the global settings".
    time_limit_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_limit_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    problem: Mapped[Problem] = relationship(back_populates="test_cases")
    test_results: Mapped[list["TestResult"]] = relationship(back_populates="test_case")

class Submission(Base):
    __tablename__ = "submissions"
    # One row per attempt. Without it, two concurrent submits could both read
    # the same count and log the same attempt number.
    __table_args__ = (UniqueConstraint("student_id", "problem_id", "attempt_number", name="uq_submission_attempt"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    source_code: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    execution_status: Mapped[ExecutionStatus | None] = mapped_column(Enum(ExecutionStatus), nullable=True)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    runtime_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    ground_truth_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ground_truth_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    student: Mapped[Student] = relationship(back_populates="submissions")
    problem: Mapped[Problem] = relationship(back_populates="submissions")
    test_results: Mapped[list["TestResult"]] = relationship(back_populates="submission")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="submission")
    diagnoses: Mapped[list["Diagnosis"]] = relationship(back_populates="submission")
    teacher_reviews: Mapped[list["TeacherReview"]] = relationship(back_populates="submission")
    hint_events: Mapped[list["HintEvent"]] = relationship(back_populates="submission")

class TestResult(Base):
    __tablename__ = "test_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    test_case_id: Mapped[str] = mapped_column(ForeignKey("test_cases.id"), index=True)
    passed: Mapped[bool] = mapped_column(Boolean)
    actual_output_json: Mapped[str] = mapped_column(Text, default="null")
    expected_output_json: Mapped[str] = mapped_column(Text, default="null")
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    runtime_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    submission: Mapped[Submission] = relationship(back_populates="test_results")
    test_case: Mapped[TestCase] = relationship(back_populates="test_results")

class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    source_type: Mapped[EvidenceSourceType] = mapped_column(Enum(EvidenceSourceType))
    evidence_code: Mapped[str] = mapped_column(String(64))
    misconception_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    direction: Mapped[EvidenceDirection] = mapped_column(Enum(EvidenceDirection))
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(Text, default="")
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    submission: Mapped[Submission] = relationship(back_populates="evidence_items")

class Diagnosis(Base):
    __tablename__ = "diagnoses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    mode: Mapped[DiagnosisMode] = mapped_column(Enum(DiagnosisMode))
    primary_misconception: Mapped[str] = mapped_column(String(64))
    primary_confidence: Mapped[float] = mapped_column(Float)
    alternative_misconception: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alternative_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_level: Mapped[UncertaintyLevel] = mapped_column(Enum(UncertaintyLevel))
    requires_teacher_review: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submission: Mapped[Submission] = relationship(back_populates="diagnoses")
    teacher_reviews: Mapped[list["TeacherReview"]] = relationship(back_populates="diagnosis")

class LearnerState(Base):
    __tablename__ = "learner_states"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    misconception_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[MisconceptionState] = mapped_column(Enum(MisconceptionState))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    trigger_submission_id: Mapped[int | None] = mapped_column(ForeignKey("submissions.id"), nullable=True)
    support_count: Mapped[int] = mapped_column(Integer, default=0)
    cross_problem_support_count: Mapped[int] = mapped_column(Integer, default=0)
    recent_success_count: Mapped[int] = mapped_column(Integer, default=0)
    student: Mapped[Student] = relationship(back_populates="learner_states")

class LearnerStateHistory(Base):
    __tablename__ = "learner_state_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    misconception_id: Mapped[str] = mapped_column(String(64), index=True)
    old_state: Mapped[MisconceptionState] = mapped_column(Enum(MisconceptionState))
    new_state: Mapped[MisconceptionState] = mapped_column(Enum(MisconceptionState))
    old_confidence: Mapped[float] = mapped_column(Float)
    new_confidence: Mapped[float] = mapped_column(Float)
    submission_id: Mapped[int | None] = mapped_column(ForeignKey("submissions.id"), nullable=True)
    reason_json: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

class TeacherReview(Base):
    __tablename__ = "teacher_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    diagnosis_id: Mapped[int | None] = mapped_column(ForeignKey("diagnoses.id"), nullable=True)
    action: Mapped[TeacherReviewAction] = mapped_column(Enum(TeacherReviewAction))
    corrected_misconception: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submission: Mapped[Submission] = relationship(back_populates="teacher_reviews")
    diagnosis: Mapped[Diagnosis | None] = relationship(back_populates="teacher_reviews")

class HintEvent(Base):
    __tablename__ = "hint_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    misconception_id: Mapped[str] = mapped_column(String(64))
    hint_level: Mapped[int] = mapped_column(Integer, default=1)
    hint_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    student: Mapped[Student] = relationship(back_populates="hint_events")
    submission: Mapped[Submission] = relationship(back_populates="hint_events")


class Classroom(Base):
    __tablename__ = "classrooms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Random code students use to join. Unique; rotate to stop new joins.
    join_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    members: Mapped[list["ClassroomMember"]] = relationship(back_populates="classroom", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="classroom", cascade="all, delete-orphan")


class ClassroomMember(Base):
    __tablename__ = "classroom_members"
    __table_args__ = (UniqueConstraint("classroom_id", "student_id", name="uq_classroom_student"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    classroom: Mapped[Classroom] = relationship(back_populates="members")


class AssignmentState(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"), index=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[AssignmentState] = mapped_column(Enum(AssignmentState), default=AssignmentState.ACTIVE)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    classroom: Mapped[Classroom] = relationship(back_populates="assignments")
    students: Mapped[list["AssignmentStudent"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")


class AssignmentStudent(Base):
    __tablename__ = "assignment_students"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    assignment: Mapped[Assignment] = relationship(back_populates="students")


# ---------------------------------------------------------------------------
# Canonical problem bank tables.
#
# The existing `problems` and `test_cases` tables hold the practice website
# data. These five tables add bank features without changing that data:
# reference solutions, normalized tags, per-problem hints, source provenance,
# and quality-check results. Public API code never reads solutions or
# provenance under the student role (see backend/app/api/bank.py).
# ---------------------------------------------------------------------------

class ProblemSolution(Base):
    """Reference solution for a problem. Internal only; never public."""
    __tablename__ = "problem_solutions"
    __table_args__ = (UniqueConstraint("problem_id", "language", name="uq_solution_problem_language"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    language: Mapped[str] = mapped_column(String(16), default="cpp", server_default="cpp")
    language_standard: Mapped[str] = mapped_column(String(8), default="cpp17", server_default="cpp17")
    source_code: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus), default=VerificationStatus.UNVERIFIED)
    verification_detail: Mapped[str] = mapped_column(Text, default="")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    license: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    problem: Mapped[Problem] = relationship(back_populates="solutions")


class ProblemTag(Base):
    """Normalized search tag for a problem."""
    __tablename__ = "problem_tags"
    __table_args__ = (UniqueConstraint("problem_id", "tag", name="uq_problem_tag"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    tag: Mapped[str] = mapped_column(String(48), index=True)
    problem: Mapped[Problem] = relationship(back_populates="tags")


class ProblemHint(Base):
    """Per-problem hint. It overrides the template hint for the same key."""
    __tablename__ = "problem_hints"
    __table_args__ = (UniqueConstraint("problem_id", "misconception_id", "level", name="uq_problem_hint_level"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    misconception_id: Mapped[str] = mapped_column(String(64))
    level: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    problem: Mapped[Problem] = relationship(back_populates="hints")


class ProblemProvenance(Base):
    """Source record for one problem. It links the bank row to its dataset."""
    __tablename__ = "problem_provenance"
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), primary_key=True)
    dataset_source: Mapped[str] = mapped_column(String(32), index=True)
    source_problem_id: Mapped[str] = mapped_column(String(64), default="")
    canonical_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    source_url: Mapped[str] = mapped_column(String(512), default="")
    source_license: Mapped[str] = mapped_column(String(64), default="")
    license_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    provenance_ref: Mapped[str] = mapped_column(String(512), default="")
    source_sha256: Mapped[str] = mapped_column(String(64), default="")
    parser_version: Mapped[str] = mapped_column(String(64), default="")
    ingestion_run_id: Mapped[str] = mapped_column(String(64), default="")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    problem: Mapped[Problem] = relationship(back_populates="provenance")


class ProblemQualityCheck(Base):
    """One quality-check result for a problem. The loader writes these."""
    __tablename__ = "problem_quality_checks"
    __table_args__ = (UniqueConstraint("problem_id", "check_code", name="uq_problem_quality_check"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    check_code: Mapped[str] = mapped_column(String(64))
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[str] = mapped_column(String(512), default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    problem: Mapped[Problem] = relationship(back_populates="quality_checks")
