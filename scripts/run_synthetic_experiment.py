"""Run full synthetic experiment pipeline and export results."""
from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.database import Base, SessionLocal, engine, init_db
from backend.app.db.seed import run_seed
from backend.app.db.models import Diagnosis, EvidenceItem, LearnerStateHistory, Student, Submission
from backend.app.evaluation.evaluator import ExperimentEvaluator
from backend.app.services.submission_service import SubmissionService
from backend.app.services import demo_service

EXPORT_DIR = ROOT / "data" / "exports"
DEMO_DIR = ROOT / "data" / "demo_sequences"

def main() -> None:
    if (ROOT / "tracelearn.db").exists():
        (ROOT / "tracelearn.db").unlink()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    service = SubmissionService()
    try:
        run_seed(db)
        for name in ["SYN001", "SYN002", "SYN003", "SYN004", "SYN005"]:
            if not db.query(Student).filter(Student.display_name == name).first():
                db.add(Student(display_name=name, is_synthetic=True))
            db.commit()
            demo_service.run_sequence(db, name)
        evaluator = ExperimentEvaluator(db)
        summary = evaluator.collect_predictions()
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        subs_rows = []
        for s in db.query(Submission).filter(Submission.is_synthetic == True).all():  # noqa: E712
            for mode in ["current_only", "history_aware"]:
                d = db.query(Diagnosis).filter(Diagnosis.submission_id == s.id, Diagnosis.mode == mode).order_by(Diagnosis.id.desc()).first()
                subs_rows.append({
                    "submission_id": s.id, "student_id": s.student_id, "problem_id": s.problem_id,
                    "ground_truth": s.ground_truth_label, "mode": mode,
                    "prediction": d.primary_misconception if d else None,
                    "confidence": d.primary_confidence if d else None,
                })
        pd.DataFrame(subs_rows).to_csv(EXPORT_DIR / "submission_predictions.csv", index=False)
        ev_rows = []
        for e in db.query(EvidenceItem).all():
            ev_rows.append({
                "id": e.id, "submission_id": e.submission_id, "source_type": e.source_type.value,
                "evidence_code": e.evidence_code, "misconception_id": e.misconception_id,
                "direction": e.direction.value, "weight": e.weight,
            })
        pd.DataFrame(ev_rows).to_csv(EXPORT_DIR / "evidence_items.csv", index=False)
        st_rows = []
        for h in db.query(LearnerStateHistory).all():
            st_rows.append({
                "student_id": h.student_id, "misconception_id": h.misconception_id,
                "old_state": h.old_state.value, "new_state": h.new_state.value,
                "submission_id": h.submission_id,
            })
        pd.DataFrame(st_rows).to_csv(EXPORT_DIR / "state_transitions.csv", index=False)
        (EXPORT_DIR / "experiment_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        cm_cur = summary.get("current_only_metrics", {})
        if cm_cur.get("confusion_matrix"):
            pd.DataFrame(cm_cur["confusion_matrix"], index=cm_cur.get("labels", []), columns=cm_cur.get("labels", [])).to_csv(EXPORT_DIR / "confusion_current_only.csv")
        cm_hist = summary.get("history_aware_metrics", {})
        if cm_hist.get("confusion_matrix"):
            pd.DataFrame(cm_hist["confusion_matrix"], index=cm_hist.get("labels", []), columns=cm_hist.get("labels", [])).to_csv(EXPORT_DIR / "confusion_history_aware.csv")
        print("=== Experiment Summary ===")
        print(json.dumps({k: summary[k] for k in summary if k not in ("current_only_metrics", "history_aware_metrics")}, indent=2))
        print(f"Submissions processed: {db.query(Submission).count()}")
        print(f"Exports written to: {EXPORT_DIR}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
