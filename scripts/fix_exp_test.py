from pathlib import Path
p = Path("backend/tests/test_diagnosis.py")
t = p.read_text(encoding="utf-8")
t = t.replace("    metrics = ev.run(db)\n", "    metrics = ev.collect_predictions()\n")
if "from backend.app.db.models import Submission" not in t.split("test_experiment")[1]:
    t = t.replace(
        "    from backend.app.evaluation.evaluator import ExperimentEvaluator\n",
        "    from backend.app.evaluation.evaluator import ExperimentEvaluator\n    from backend.app.db.models import Submission\n",
        1,
    )
p.write_text(t, encoding="utf-8")
print("fixed")
