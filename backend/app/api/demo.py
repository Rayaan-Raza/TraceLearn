"""Research demo endpoints (synthetic data only).

Disabled unless ENABLE_DEMO_ENDPOINTS=true, and teacher-only when enabled.
They never touch real students' data.
"""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import require_teacher
from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.execution.sandbox import sandbox_status
from backend.app.security.rate_limit import limiter
from backend.app.services import demo_service

router = APIRouter(prefix="/demo", tags=["demo"])


def _require_enabled() -> None:
    if not settings.enable_demo_endpoints:
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/status")
def demo_status(_: User = Depends(require_teacher)) -> dict:
    return {
        "enabled": settings.enable_demo_endpoints,
        "sequences": demo_service.available_sequences() if settings.enable_demo_endpoints else [],
        "sandbox": sandbox_status(),
    }


@router.post("/reset", dependencies=[Depends(_require_enabled)])
def reset_demo(db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> dict:
    limiter.hit(f"demo:{teacher.id}", 10, 60)
    return demo_service.reset_synthetic(db)


@router.post("/run-sequence/{student_id}", dependencies=[Depends(_require_enabled)])
def run_sequence(
    student_id: str = Path(pattern=r"^SYN\d{3}$"),
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> dict:
    limiter.hit(f"demo:{teacher.id}", 10, 60)
    try:
        return demo_service.run_sequence(db, student_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Sequence {student_id} not found")
    except demo_service.SequenceAlreadyRun:
        raise HTTPException(409, f"{student_id} already ran. Reset the demo data first.")
