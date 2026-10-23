import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.db.database import SessionLocal
from backend.app.evaluation.evaluator import ExperimentEvaluator
db = SessionLocal()
try:
    print(json.dumps(ExperimentEvaluator(db).collect_predictions(), indent=2))
finally:
    db.close()
