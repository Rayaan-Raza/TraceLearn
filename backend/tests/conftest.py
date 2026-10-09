import os, sys, uuid
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / f"tracelearn_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-" + uuid.uuid4().hex
os.environ["TEACHER_SIGNUP_CODE"] = "test-teacher-invite-code"
os.environ["ENABLE_DEMO_ENDPOINTS"] = "true"

TEACHER_CODE = "test-teacher-invite-code"


def _dispose_engine() -> None:
    try:
        from backend.app.db.database import engine
        engine.dispose()
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def _reset_test_db():
    yield
    _dispose_engine()
    try:
        if TEST_DB.exists():
            TEST_DB.unlink()
    except PermissionError:
        pass


@pytest.fixture(scope="module")
def seeded_db():
    from backend.app.db.database import SessionLocal, init_db
    from backend.app.db.seed import run_seed
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from backend.app.security.rate_limit import limiter
    limiter.reset()
    yield


def make_user(role: str = "student", name: str | None = None):
    """Register a fresh user and return (TestClient with Bearer auth, auth body)."""
    from backend.app.main import app
    from fastapi.testclient import TestClient
    tc = TestClient(app)
    email = f"{role}-{uuid.uuid4().hex[:10]}@example.com"
    body = {"email": email, "password": "correct-horse-battery", "role": role, "display_name": name or role.title()}
    if role == "teacher":
        body["teacher_code"] = TEACHER_CODE
    r = tc.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    tc.headers["Authorization"] = f"Bearer {data['access_token']}"
    tc.cookies.clear()
    data["email"] = email
    data["password"] = body["password"]
    return tc, data


@pytest.fixture(scope="module")
def client(seeded_db):
    """An authenticated *teacher* client (legacy tests use research endpoints)."""
    tc, _ = make_user("teacher")
    return tc


@pytest.fixture(scope="module")
def db(seeded_db):
    from backend.app.db.database import SessionLocal
    db = SessionLocal()
    yield db
    db.close()
    _dispose_engine()


@pytest.fixture(autouse=True)
def _rollback_each_test(db):
    yield
    db.rollback()
