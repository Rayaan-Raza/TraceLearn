"""Generate complete TraceLearn POC."""
from __future__ import annotations
import json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def w(rel: str, text: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")

def build_models():
    w("backend/app/db/models.py", '''
"""SQLAlchemy ORM models for TraceLearn POC."""
from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.database import Base

class TestType(str, enum.Enum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    DIAGNOSTIC = "diagnostic"

class ExecutionStatus(str, enum.Enum):
    SUCCESS = "success"
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="problem")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="problem")

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
    problem: Mapped[Problem] = relationship(back_populates="test_cases")
    test_results: Mapped[list["TestResult"]] = relationship(back_populates="test_case")

class Submission(Base):
    __tablename__ = "submissions"
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
''')

if __name__ == "__main__":
    build_models()
    print("models done")
