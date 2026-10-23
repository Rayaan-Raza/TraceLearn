"""JWT utilities and password hashing for TraceLearn RBAC."""
from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from backend.app.config import settings

ALGORITHM = "HS256"
# bcrypt only looks at the first 72 bytes; longer passwords are rejected at
# the API layer so two different passwords can never collide.
BCRYPT_MAX_BYTES = 72

# A real bcrypt hash used to keep login timing constant when the email does
# not exist (prevents account enumeration via response time).
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode("utf-8")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), (hashed or _DUMMY_HASH).encode("utf-8")) and hashed is not None
    except ValueError:
        return False


def create_access_token(subject: str, role: str, token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "ver": token_version,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],  # pinned: never accept "none" or RS/HS confusion
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if payload.get("typ") != "access":
        raise ValueError("Wrong token type")
    return payload


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def tokens_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
