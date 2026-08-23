import os, sys, uuid
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / f"tracelearn_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"


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


@pytest.fixture(scope="module")
def client(seeded_db):
    from backend.app.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


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
