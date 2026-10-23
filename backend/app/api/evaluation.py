from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import require_teacher
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.evaluation.evaluator import ExperimentEvaluator

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/comparison")
def evaluation_comparison(db: Session = Depends(get_db), _: User = Depends(require_teacher)) -> dict:
    """Current-only vs history-aware metrics over synthetic (labelled) submissions only."""
    return ExperimentEvaluator(db).collect_predictions()
