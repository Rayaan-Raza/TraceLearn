"""FastAPI dependencies for authentication and authorization.

Two ways to authenticate:

* Browser (the TraceLearn UI): an httpOnly ``tl_session`` cookie holding the
  JWT. Because browsers attach cookies automatically, every state-changing
  request authenticated this way must also echo the ``tl_csrf`` cookie in an
  ``X-CSRF-Token`` header (double-submit CSRF protection).
* API clients / Swagger: ``Authorization: Bearer <jwt>``. Not CSRF-able, so
  no extra header is needed.

Object-level access rules (who may see which student's data) live in
``backend.app.auth.access``.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.auth.core import decode_token, tokens_match
from backend.app.db.database import get_db
from backend.app.db.models import User, UserRole

SESSION_COOKIE = "tl_session"
CSRF_COOKIE = "tl_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# auto_error=False so that cookie auth can be used when no header is sent.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    bearer: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = bearer
    via_cookie = False
    if not token:
        token = request.cookies.get(SESSION_COOKIE)
        via_cookie = True
    if not token:
        raise _unauthorized()

    if via_cookie and request.method not in SAFE_METHODS:
        if not tokens_match(request.headers.get(CSRF_HEADER), request.cookies.get(CSRF_COOKIE)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid")

    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
        token_version = int(payload.get("ver", 0))
    except (ValueError, KeyError, TypeError):
        raise _unauthorized()

    user = db.get(User, user_id)
    if user is None or (user.token_version or 0) != token_version:
        raise _unauthorized()
    # Role in the token must still match the database (e.g. no stale teacher tokens).
    if payload.get("role") != user.role.value:
        raise _unauthorized()
    return user


def require_teacher(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher access required")
    return current_user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.STUDENT or current_user.student_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access required")
    return current_user
