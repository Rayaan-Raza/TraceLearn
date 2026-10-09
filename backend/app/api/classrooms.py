"""Classrooms, membership (join codes) and assignments."""
from __future__ import annotations

from typing import Annotated

import secrets
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.auth.access import (
    get_assignment_for,
    get_classroom_for,
    get_owned_classroom,
    get_problem_for,
)
from backend.app.auth.dependencies import get_current_user, require_student, require_teacher
from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import (
    Assignment,
    AssignmentState,
    AssignmentStudent,
    Classroom,
    ClassroomMember,
    LearnerState,
    Problem,
    Student,
    Submission,
    User,
    UserRole,
)
from backend.app.api.learners import summarize_submissions
from backend.app.schemas.submissions import SubmissionSummary
from backend.app.security.rate_limit import client_ip, limiter

router = APIRouter(tags=["classrooms"])

IdPath = Annotated[int, Path(ge=1, le=2**31 - 1)]
JOIN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
ATTENTION_STATES = {"PERSISTENT", "RECURRED", "REQUIRES_TEACHER_REVIEW"}


def _new_join_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(JOIN_ALPHABET) for _ in range(8))
        if not db.query(Classroom.id).filter(Classroom.join_code == code).first():
            return code


def _clean(v: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError("must not be empty")
    return v


# ----------------------------------------------------------------- schemas
class ClassroomCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    _c = field_validator("code", "name")(_clean)


class ClassroomRead(BaseModel):
    id: int
    code: str
    name: str
    teacher_name: str
    member_count: int
    join_code: str | None = None  # owner only
    created_at: datetime


class MemberRead(BaseModel):
    student_id: int
    display_name: str
    joined_at: datetime


class JoinRequest(BaseModel):
    join_code: str = Field(min_length=4, max_length=16)


class AssignmentCreate(BaseModel):
    problem_id: str = Field(min_length=1, max_length=8, pattern=r"^[A-Za-z0-9_-]+$")
    student_ids: list[int] = Field(default_factory=list, max_length=500)
    due_date: str = Field(default="", max_length=32)
    notes: str = Field(default="", max_length=1000)

    @field_validator("due_date")
    @classmethod
    def _due(cls, v: str) -> str:
        return " ".join(v.split())


class AssignmentUpdate(BaseModel):
    state: Literal["active", "closed"]


class AssignmentRead(BaseModel):
    id: int
    classroom_id: int
    classroom_name: str
    problem_id: str
    problem_title: str
    problem_topic: str
    problem_difficulty: str
    student_ids: list[int]
    due_date: str
    notes: str
    state: str
    assigned_at: datetime


class StudentResult(BaseModel):
    student_id: int
    display_name: str
    submissions: list[SubmissionSummary]


class AssignmentDetail(AssignmentRead):
    results: list[StudentResult]


class StudentOverview(BaseModel):
    id: int
    display_name: str
    submission_count: int
    solved_problems: int
    latest_submitted_at: datetime | None
    states: list[dict]


class ClassroomOverview(BaseModel):
    classroom: ClassroomRead
    totals: dict
    students: list[StudentOverview]
    misconceptions: list[dict]


# ----------------------------------------------------------------- helpers
def _room_read(db: Session, room: Classroom, user: User) -> ClassroomRead:
    teacher = db.get(User, room.teacher_user_id)
    count = db.query(func.count(ClassroomMember.id)).filter(ClassroomMember.classroom_id == room.id).scalar() or 0
    return ClassroomRead(
        id=room.id, code=room.code, name=room.name,
        teacher_name=(teacher.display_name or "Teacher") if teacher else "Teacher",
        member_count=count,
        join_code=room.join_code if user.role == UserRole.TEACHER and room.teacher_user_id == user.id else None,
        created_at=room.created_at,
    )


def _assignment_read(db: Session, a: Assignment, user: User) -> AssignmentRead:
    problem = db.get(Problem, a.problem_id)
    room = db.get(Classroom, a.classroom_id)
    ids = [s.student_id for s in a.students]
    if user.role == UserRole.STUDENT:
        ids = [i for i in ids if i == user.student_id]  # never reveal classmates
    return AssignmentRead(
        id=a.id, classroom_id=a.classroom_id, classroom_name=room.name if room else "",
        problem_id=a.problem_id, problem_title=problem.title if problem else a.problem_id,
        problem_topic=(problem.topic or "") if problem else "", problem_difficulty=(problem.difficulty or "") if problem else "",
        student_ids=ids, due_date=a.due_date or "", notes=a.notes or "",
        state=a.state.value if a.state else "active", assigned_at=a.assigned_at,
    )


def _member_ids(db: Session, room_id: int) -> list[int]:
    return [r[0] for r in db.query(ClassroomMember.student_id).filter(ClassroomMember.classroom_id == room_id).all()]


# ----------------------------------------------------------------- classrooms
@router.post("/classrooms", response_model=ClassroomRead, status_code=status.HTTP_201_CREATED)
def create_classroom(payload: ClassroomCreate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> ClassroomRead:
    if db.query(func.count(Classroom.id)).filter(Classroom.teacher_user_id == teacher.id).scalar() >= 50:
        raise HTTPException(400, "Classroom limit reached")
    room = Classroom(code=payload.code, name=payload.name, teacher_user_id=teacher.id, join_code=_new_join_code(db))
    db.add(room)
    db.commit()
    db.refresh(room)
    return _room_read(db, room, teacher)


@router.get("/classrooms", response_model=list[ClassroomRead])
def list_classrooms(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ClassroomRead]:
    if user.role == UserRole.TEACHER:
        rooms = db.query(Classroom).filter(Classroom.teacher_user_id == user.id).order_by(Classroom.id).all()
    else:
        rooms = (
            db.query(Classroom)
            .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
            .filter(ClassroomMember.student_id == user.student_id)
            .order_by(Classroom.id)
            .all()
        )
    return [_room_read(db, r, user) for r in rooms]


@router.get("/classrooms/{classroom_id}", response_model=ClassroomRead)
def get_classroom(classroom_id: IdPath, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ClassroomRead:
    return _room_read(db, get_classroom_for(db, user, classroom_id), user)


@router.post("/classrooms/join", response_model=ClassroomRead)
def join_classroom(payload: JoinRequest, request: Request, db: Session = Depends(get_db), student: User = Depends(require_student)) -> ClassroomRead:
    # Join codes are 40-bit random; rate limiting makes guessing infeasible.
    limiter.hit(f"join:user:{student.id}", settings.join_attempts_per_minute, 60)
    limiter.hit(f"join:ip:{client_ip(request)}", settings.join_attempts_per_minute * 3, 60)
    code = "".join(payload.join_code.split()).upper()
    room = db.query(Classroom).filter(Classroom.join_code == code).first()
    if room is None:
        raise HTTPException(404, "No classroom with that code")
    exists = db.query(ClassroomMember.id).filter(
        ClassroomMember.classroom_id == room.id, ClassroomMember.student_id == student.student_id
    ).first()
    if not exists:
        db.add(ClassroomMember(classroom_id=room.id, student_id=student.student_id))
        db.commit()
    return _room_read(db, room, student)


@router.post("/classrooms/{classroom_id}/rotate-code", response_model=ClassroomRead)
def rotate_join_code(classroom_id: IdPath, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> ClassroomRead:
    room = get_owned_classroom(db, teacher, classroom_id)
    room.join_code = _new_join_code(db)
    db.commit()
    return _room_read(db, room, teacher)


@router.get("/classrooms/{classroom_id}/members", response_model=list[MemberRead])
def list_members(classroom_id: IdPath, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> list[MemberRead]:
    room = get_owned_classroom(db, teacher, classroom_id)
    rows = (
        db.query(ClassroomMember, Student)
        .join(Student, Student.id == ClassroomMember.student_id)
        .filter(ClassroomMember.classroom_id == room.id)
        .order_by(Student.display_name)
        .all()
    )
    return [MemberRead(student_id=s.id, display_name=s.display_name, joined_at=m.joined_at) for m, s in rows]


@router.delete("/classrooms/{classroom_id}/members/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(classroom_id: IdPath, student_id: IdPath, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> None:
    room = get_owned_classroom(db, teacher, classroom_id)
    db.query(ClassroomMember).filter(ClassroomMember.classroom_id == room.id, ClassroomMember.student_id == student_id).delete()
    assignment_ids = [a.id for a in db.query(Assignment.id).filter(Assignment.classroom_id == room.id).all()]
    if assignment_ids:
        db.query(AssignmentStudent).filter(
            AssignmentStudent.assignment_id.in_(assignment_ids), AssignmentStudent.student_id == student_id
        ).delete(synchronize_session=False)
    db.commit()


@router.get("/classrooms/{classroom_id}/overview", response_model=ClassroomOverview)
def classroom_overview(classroom_id: IdPath, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> ClassroomOverview:
    room = get_owned_classroom(db, teacher, classroom_id)
    ids = _member_ids(db, room.id)
    students = db.query(Student).filter(Student.id.in_(ids)).order_by(Student.display_name).all() if ids else []
    states = db.query(LearnerState).filter(LearnerState.student_id.in_(ids)).all() if ids else []
    subs = db.query(Submission).filter(Submission.student_id.in_(ids)).all() if ids else []
    summaries = {s.id: s for s in summarize_submissions(db, subs)}

    by_student_states: dict[int, list[dict]] = {}
    by_misc: dict[str, list[dict]] = {}
    names = {s.id: s.display_name for s in students}
    for st in states:
        row = {"misconception_id": st.misconception_id, "state": st.state.value, "confidence": st.confidence, "updated_at": st.updated_at}
        by_student_states.setdefault(st.student_id, []).append(row)
        by_misc.setdefault(st.misconception_id, []).append(
            {"student_id": st.student_id, "display_name": names.get(st.student_id, ""), "state": st.state.value, "confidence": st.confidence}
        )

    student_rows = []
    total_solved = 0
    for s in students:
        mine = [summaries[x.id] for x in subs if x.student_id == s.id]
        solved = len({m.problem_id for m in mine if m.passed})
        total_solved += solved
        student_rows.append(StudentOverview(
            id=s.id, display_name=s.display_name, submission_count=len(mine), solved_problems=solved,
            latest_submitted_at=max((m.submitted_at for m in mine), default=None),
            states=by_student_states.get(s.id, []),
        ))
    misconceptions = [
        {"misconception_id": mid, "students": rows,
         "attention_count": sum(1 for r in rows if r["state"] in ATTENTION_STATES)}
        for mid, rows in sorted(by_misc.items())
    ]
    return ClassroomOverview(
        classroom=_room_read(db, room, teacher),
        totals={
            "students": len(students),
            "submissions": len(subs),
            "problems_completed": total_solved,
            "areas_needing_attention": sum(1 for m in misconceptions if m["attention_count"] > 0),
            "active_assignments": db.query(func.count(Assignment.id)).filter(
                Assignment.classroom_id == room.id, Assignment.state == AssignmentState.ACTIVE
            ).scalar() or 0,
        },
        students=student_rows,
        misconceptions=misconceptions,
    )


# ----------------------------------------------------------------- assignments
@router.post("/classrooms/{classroom_id}/assignments", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def create_assignment(
    payload: AssignmentCreate,
    classroom_id: IdPath,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> AssignmentRead:
    room = get_owned_classroom(db, teacher, classroom_id)
    problem = get_problem_for(db, teacher, payload.problem_id)  # dataset or the teacher's own
    members = set(_member_ids(db, room.id))
    targets = set(payload.student_ids) or members
    if not targets:
        raise HTTPException(400, "This classroom has no students yet")
    if not targets <= members:
        raise HTTPException(400, "Every selected student must be a member of this classroom")
    a = Assignment(
        classroom_id=room.id, problem_id=problem.id, assigned_by_user_id=teacher.id,
        due_date=payload.due_date, notes=payload.notes, state=AssignmentState.ACTIVE,
    )
    db.add(a)
    db.flush()
    for sid in sorted(targets):
        db.add(AssignmentStudent(assignment_id=a.id, student_id=sid))
    db.commit()
    db.refresh(a)
    return _assignment_read(db, a, teacher)


@router.get("/classrooms/{classroom_id}/assignments", response_model=list[AssignmentRead])
def list_classroom_assignments(classroom_id: IdPath, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[AssignmentRead]:
    room = get_classroom_for(db, user, classroom_id)
    q = db.query(Assignment).filter(Assignment.classroom_id == room.id)
    if user.role == UserRole.STUDENT:
        q = q.join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id).filter(
            AssignmentStudent.student_id == user.student_id
        )
    return [_assignment_read(db, a, user) for a in q.order_by(Assignment.assigned_at.desc(), Assignment.id.desc()).all()]


@router.get("/assignments/mine", response_model=list[AssignmentRead])
def my_assignments(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[AssignmentRead]:
    if user.role == UserRole.TEACHER:
        q = db.query(Assignment).join(Classroom, Classroom.id == Assignment.classroom_id).filter(Classroom.teacher_user_id == user.id)
    else:
        q = db.query(Assignment).join(AssignmentStudent, AssignmentStudent.assignment_id == Assignment.id).filter(
            AssignmentStudent.student_id == user.student_id
        )
    return [_assignment_read(db, a, user) for a in q.order_by(Assignment.assigned_at.desc(), Assignment.id.desc()).all()]


@router.get("/assignments/{assignment_id}", response_model=AssignmentDetail)
def get_assignment(assignment_id: IdPath, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AssignmentDetail:
    a = get_assignment_for(db, user, assignment_id)
    base = _assignment_read(db, a, user)
    ids = base.student_ids
    students = {s.id: s for s in db.query(Student).filter(Student.id.in_(ids)).all()} if ids else {}
    subs = (
        db.query(Submission)
        .filter(Submission.problem_id == a.problem_id, Submission.student_id.in_(ids))
        .order_by(Submission.submitted_at.desc(), Submission.id.desc())
        .all()
        if ids else []
    )
    summaries = summarize_submissions(db, subs)
    results = [
        StudentResult(
            student_id=sid, display_name=students[sid].display_name if sid in students else "",
            submissions=[s for s in summaries if s.student_id == sid],
        )
        for sid in ids
    ]
    return AssignmentDetail(**base.model_dump(), results=results)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentRead)
def update_assignment(payload: AssignmentUpdate, assignment_id: IdPath, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> AssignmentRead:
    a = get_assignment_for(db, teacher, assignment_id)
    a.state = AssignmentState(payload.state)
    db.commit()
    return _assignment_read(db, a, teacher)
