from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")
p = ROOT / "backend/app/db/models.py"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(r'''"""SQLAlchemy ORM models for TraceLearn POC (Milestone 1)."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base


class TestVisibility(str, enum.Enum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    DIAGNOSTIC = "diagnostic"


class LearnerStateKind(str, enum.Enum):
    NEW = "NEW"
    PERSISTENT = "PERSISTENT"
    RESOLVED = "RESOLVED"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    submissions: Mapped[list[Submission]] = relationship(back_populates="student")
    learner_states: Mapped[list[LearnerState]] = relationship(back_populates="student")


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    starter_code: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(32), default="intro")
    taxonomy_tags: Mapped[str] = mapped_column(Text, default="[]")

    test_cases: Mapped[list[TestCase]] = relationship(back_populates="problem")
    submissions: Mapped[list[Submission]] = relationship(back_populates="problem")


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    stdin: Mapped[str] = mapped_column(Text, default="")
    expected_stdout: Mapped[str] = mapped_column(Text)
    visibility: Mapped[TestVisibility] = mapped_column(Enum(TestVisibility))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    diagnostic_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)

    problem: Mapped[Problem] = relationship(back_populates="test_cases")
    test_results: Mapped[list[TestResult]] = relationship(back_populates="test_case")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    code: Mapped[str] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped[Student] = relationship(back_populates="submissions")
    problem: Mapped[Problem] = relationship(back_populates="submissions")
    test_results: Mapped[list[TestResult]] = relationship(back_populates="submission")
    evidence_items: Mapped[list[EvidenceItem]] = relationship(back_populates="submission")
    diagnoses: Mapped[list[Diagnosis]] = relationship(back_populates="submission")
    teacher_reviews: Mapped[list[TeacherReview]] = relationship(back_populates="submission")
    hint_events: Mapped[list[HintEvent]] = relationship(back_populates="submission")


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    test_case_id: Mapped[str] = mapped_column(ForeignKey("test_cases.id"), index=True)
    passed: Mapped[bool] = mapped_column(Boolean)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    runtime_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    submission: Mapped[Submission] = relationship(back_populates="test_results")
    test_case: Mapped[TestCase] = relationship(back_populates="test_results")


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    weight: Mapped[float] = mapped_column(Float, default=0.0)

    submission: Mapped[Submission] = relationship(back_populates="evidence_items")


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    misconception_id: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer, default=1)

    submission: Mapped[Submission] = relationship(back_populates="diagnoses")
    teacher_reviews: Mapped[list[TeacherReview]] = relationship(back_populates="diagnosis")


class LearnerState(Base):
    __tablename__ = "learner_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    misconception_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[LearnerStateKind] = mapped_column(Enum(LearnerStateKind))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    student: Mapped[Student] = relationship(back_populates="learner_states")


class LearnerStateHistory(Base):
    """Append-only history; queries must respect strict temporal causality (see docs)."""

    __tablename__ = "learner_state_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    misconception_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[LearnerStateKind] = mapped_column(Enum(LearnerStateKind))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    trigger_submission_id: Mapped[int | None] = mapped_column(ForeignKey("submissions.id"), nullable=True)


class TeacherReview(Base):
    __tablename__ = "teacher_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    diagnosis_id: Mapped[int | None] = mapped_column(ForeignKey("diagnoses.id"), nullable=True)
    verdict: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    submission: Mapped[Submission] = relationship(back_populates="teacher_reviews")
    diagnosis: Mapped[Diagnosis | None] = relationship(back_populates="teacher_reviews")


class HintEvent(Base):
    __tablename__ = "hint_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    hint_level: Mapped[int] = mapped_column(Integer, default=1)
    hint_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    submission: Mapped[Submission] = relationship(back_populates="hint_events")
''', encoding="utf-8", newline="\n")
print("models ok")
