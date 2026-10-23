"""Object-level authorization rules.

Every route that takes an id in its path resolves the object and then calls
one of these helpers. They return 404 (not 403) when the caller may not see
an object, so ids of other people's data cannot be probed.

Rules
-----
* A student can see only their own student record, submissions, diagnoses,
  evidence, learner states and timeline.
* A teacher can see students who are members of a classroom they own, plus
  synthetic research students (is_synthetic=True, not real people).
* Dataset problems (created_by_user_id is NULL) are visible to everyone
  signed in. A custom problem is visible to the teacher who created it and to
  students it has been assigned to.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Assignment,
    AssignmentStudent,
    Classroom,
    ClassroomMember,
    Diagnosis,
    Problem,
    Student,
    Submission,
    User,
    UserRole,
)


def not_found(what: str = "Not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=what)


def teacher_student_ids(db: Session, teacher: User) -> set[int]:
    rows = (
        db.query(ClassroomMember.student_id)
        .join(Classroom, Classroom.id == ClassroomMember.classroom_id)
        .filter(Classroom.teacher_user_id == teacher.id)
        .all()
    )
    return {r[0] for r in rows}


def can_view_student(db: Session, user: User, student_id: int) -> bool:
    if user.role == UserRole.STUDENT:
        return user.student_id is not None and user.student_id == student_id
    if user.role == UserRole.TEACHER:
        student = db.get(Student, student_id)
        if student is None:
            return False
        if student.is_synthetic:
            return True
        return (
            db.query(ClassroomMember.id)
            .join(Classroom, Classroom.id == ClassroomMember.classroom_id)
            .filter(Classroom.teacher_user_id == user.id, ClassroomMember.student_id == student_id)
            .first()
            is not None
        )
    return False


def get_student_for(db: Session, user: User, student_id: int) -> Student:
    if not can_view_student(db, user, student_id):
        raise not_found("Student not found")
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("Student not found")
    return student


def get_submission_for(db: Session, user: User, submission_id: int) -> Submission:
    sub = db.get(Submission, submission_id)
    if sub is None or not can_view_student(db, user, sub.student_id):
        raise not_found("Submission not found")
    return sub


def get_own_submission(db: Session, user: User, submission_id: int) -> Submission:
    """Submissions may only be executed/analyzed by the student who made them."""
    sub = db.get(Submission, submission_id)
    if sub is None or user.role != UserRole.STUDENT or sub.student_id != user.student_id:
        raise not_found("Submission not found")
    return sub


def get_diagnosis_for_teacher(db: Session, user: User, diagnosis_id: int) -> Diagnosis:
    diag = db.get(Diagnosis, diagnosis_id)
    if diag is None:
        raise not_found("Diagnosis not found")
    sub = db.get(Submission, diag.submission_id)
    if sub is None or user.role != UserRole.TEACHER or not can_view_student(db, user, sub.student_id):
        raise not_found("Diagnosis not found")
    return diag


def can_view_problem(db: Session, user: User, problem: Problem) -> bool:
    if problem.created_by_user_id is None:
        return True
    if user.role == UserRole.TEACHER:
        return problem.created_by_user_id == user.id
    if user.role == UserRole.STUDENT and user.student_id is not None:
        return (
            db.query(AssignmentStudent.id)
            .join(Assignment, Assignment.id == AssignmentStudent.assignment_id)
            .filter(Assignment.problem_id == problem.id, AssignmentStudent.student_id == user.student_id)
            .first()
            is not None
        )
    return False


def get_problem_for(db: Session, user: User, problem_id: str) -> Problem:
    problem = db.get(Problem, problem_id)
    if problem is None or not can_view_problem(db, user, problem):
        raise not_found("Problem not found")
    return problem


def get_owned_classroom(db: Session, user: User, classroom_id: int) -> Classroom:
    room = db.get(Classroom, classroom_id)
    if room is None or user.role != UserRole.TEACHER or room.teacher_user_id != user.id:
        raise not_found("Classroom not found")
    return room


def get_classroom_for(db: Session, user: User, classroom_id: int) -> Classroom:
    room = db.get(Classroom, classroom_id)
    if room is None:
        raise not_found("Classroom not found")
    if user.role == UserRole.TEACHER and room.teacher_user_id == user.id:
        return room
    if user.role == UserRole.STUDENT and user.student_id is not None:
        member = (
            db.query(ClassroomMember.id)
            .filter(ClassroomMember.classroom_id == room.id, ClassroomMember.student_id == user.student_id)
            .first()
        )
        if member is not None:
            return room
    raise not_found("Classroom not found")


def get_assignment_for(db: Session, user: User, assignment_id: int) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if a is None:
        raise not_found("Assignment not found")
    room = db.get(Classroom, a.classroom_id)
    if user.role == UserRole.TEACHER and room is not None and room.teacher_user_id == user.id:
        return a
    if user.role == UserRole.STUDENT and any(s.student_id == user.student_id for s in a.students):
        return a
    raise not_found("Assignment not found")
