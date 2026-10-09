"""Authentication endpoints: register and login."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import Student, User, UserRole
from backend.app.auth.core import create_access_token, hash_password, verify_password
from backend.app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "student"
    display_name: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    student_id: int | None = None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    try:
        role = UserRole(payload.role.lower())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid role '{payload.role}', must be 'student' or 'teacher'")

    student = None
    if role == UserRole.STUDENT:
        name = payload.display_name or payload.email.split("@")[0]
        student = Student(display_name=name, is_synthetic=False)
        db.add(student)
        db.flush()

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=role,
        student_id=student.id if student else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id), role.value)
    return TokenResponse(access_token=token, role=role.value, user_id=user.id, student_id=user.student_id)


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(str(user.id), user.role.value)
    return TokenResponse(access_token=token, role=user.role.value, user_id=user.id, student_id=user.student_id)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role.value,
        "student_id": current_user.student_id,
    }
