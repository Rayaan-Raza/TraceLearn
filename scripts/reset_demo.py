"""Reset synthetic research data (SYN* students). Real users are untouched."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db.database import SessionLocal, init_db  # noqa: E402
from backend.app.services.demo_service import reset_synthetic  # noqa: E402

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        print(reset_synthetic(db))
    finally:
        db.close()
