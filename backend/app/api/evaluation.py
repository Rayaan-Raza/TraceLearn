from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.evaluation.evaluator import ExperimentEvaluator

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

@router.get("/comparison")
def evaluation_comparison(db: Session = Depends(get_db)) -> dict:
    return ExperimentEvaluator(db).collect_predictions()
