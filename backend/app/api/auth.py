"""Authentication endpoints: register, login, logout, me."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.app.auth.core import (
    BCRYPT_MAX_BYTES,
    create_access_token,
    hash_password,
    new_csrf_token,
    tokens_match,
    verify_password,
)
from backend.app.auth.dependencies import CSRF_COOKIE, SESSION_COOKIE, get_current_user
from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import Student, User, UserRole
from backend.app.security.rate_limit import client_ip, limiter

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")


def _normalize_email(v: str) -> str:
    v = (v or "").strip().lower()
    if len(v) > 254 or not EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address")
    return v


def _check_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
    return v


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    role: str = "student"
    display_name: str = Field(default="", max_length=64)
    teacher_code: str | None = Field(default=None, max_length=128)

    _email = field_validator("email")(_normalize_email)
    _password = field_validator("password")(_check_password)

    @field_validator("display_name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if any(ord(c) < 32 for c in v):
            raise ValueError("Invalid characters in name")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    student_id: int | None = None
    display_name: str = ""


def _set_session_cookies(response: Response, token: str) -> None:
    common = {
        "secure": settings.effective_cookie_secure,
        "samesite": settings.cookie_samesite,
        "domain": settings.cookie_domain,
        "max_age": settings.jwt_expire_minutes * 60,
    }
    response.set_cookie(SESSION_COOKIE, token, httponly=True, path="/", **common)
    # Readable by the SPA so it can echo it in X-CSRF-Token (double submit).
    response.set_cookie(CSRF_COOKIE, new_csrf_token(), httponly=False, path="/", **common)


def _clear_session_cookies(response: Response) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            name, path="/", domain=settings.cookie_domain,
            secure=settings.effective_cookie_secure, samesite=settings.cookie_samesite,
        )


def _token_response(user: User, response: Response) -> TokenResponse:
    token = create_access_token(str(user.id), user.role.value, user.token_version or 0)
    _set_session_cookies(response, token)
    return TokenResponse(
        access_token=token, role=user.role.value, user_id=user.id,
        student_id=user.student_id, display_name=user.display_name or "",
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    limiter.hit(f"register:{client_ip(request)}", settings.register_attempts_per_hour, 3600)

    try:
        role = UserRole(payload.role.lower())
    except ValueError:
        raise HTTPException(status_code=422, detail="Role must be 'student' or 'teacher'")

    if role == UserRole.TEACHER:
        # Teachers can see student work, so the role cannot be self-assigned
        # without the invite code configured by the deployment.
        if not settings.teacher_signup_code or not tokens_match(payload.teacher_code, settings.teacher_signup_code):
            raise HTTPException(status_code=403, detail="A valid teacher invite code is required to register as a teacher")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    name = payload.display_name or payload.email.split("@")[0][:64]
    student = None
    if role == UserRole.STUDENT:
        student = Student(display_name=name, is_synthetic=False)
        db.add(student)
        db.flush()

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=role,
        display_name=name,
        student_id=student.id if student else None,
        token_version=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user, response)


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip = client_ip(request)
    try:
        email = _normalize_email(form.username)
    except ValueError:
        email = (form.username or "")[:254].lower()
    limiter.hit(f"login:ip:{ip}", settings.login_attempts_per_minute * 3, 60)
    limiter.hit(f"login:acct:{email}", settings.login_attempts_per_minute, 60)

    user = db.query(User).filter(User.email == email).first() if len(form.password) <= 256 else None
    # verify_password runs bcrypt even when the user is missing (constant time).
    ok = verify_password(form.password[:256], user.hashed_password if user else None)
    if not user or not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_response(user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    # Bumping the version revokes every token issued to this user so far.
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()
    _clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role.value,
        "student_id": current_user.student_id,
        "display_name": current_user.display_name or "",
    }
