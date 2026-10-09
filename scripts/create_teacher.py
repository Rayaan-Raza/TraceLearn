"""Create a teacher account from the command line.

Teachers can read their students' code and diagnoses, so the role cannot be
self-assigned through the public API unless TEACHER_SIGNUP_CODE is set.

    python scripts/create_teacher.py teacher@school.edu "Dr. Sarah Ahmed"

You will be prompted for the password (it is never passed on the command line).
"""
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.api.auth import _check_password, _normalize_email  # noqa: E402
from backend.app.auth.core import hash_password  # noqa: E402
from backend.app.db.database import SessionLocal, init_db  # noqa: E402
from backend.app.db.models import User, UserRole  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    email = _normalize_email(sys.argv[1])
    name = sys.argv[2] if len(sys.argv) > 2 else email.split("@")[0]
    pw = getpass.getpass("Password: ")
    if pw != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match")
    _check_password(pw)
    init_db()
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            sys.exit("A user with that email already exists")
        db.add(User(email=email, hashed_password=hash_password(pw), role=UserRole.TEACHER, display_name=name[:64]))
        db.commit()
        print(f"Teacher account created for {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
