from pathlib import Path
ROOT = Path("c:/Users/rayaan/Desktop/POC")

# fix history test id collision
p = ROOT / "backend/tests/test_history_model.py"
t = p.read_text(encoding="utf-8")
t = t.replace(
    "sub = Submission(id=10, student_id=1, problem_id=\"P01\", attempt_number=1, source_code=\"pass\", submitted_at=datetime.now(timezone.utc))",
    "sub = Submission(student_id=1, problem_id=\"P01\", attempt_number=1, source_code=\"pass\", submitted_at=datetime.now(timezone.utc))",
)
p.write_text(t, encoding="utf-8")

# fix experiment test
p2 = ROOT / "backend/tests/test_diagnosis.py"
t2 = p2.read_text(encoding="utf-8")
old = """    from backend.app.evaluation.evaluator import ExperimentEvaluator
    ev = ExperimentEvaluator()
    metrics = ev.run(db)
    assert \"accuracy\" in metrics
    assert metrics[\"submission_count\"] >= 1"""
new = """    from backend.app.evaluation.evaluator import ExperimentEvaluator
    from backend.app.db.models import Submission
    ev = ExperimentEvaluator(db)
    metrics = ev.collect_predictions()
    assert \"accuracy\" in metrics[\"current_only_metrics\"]
    assert db.query(Submission).count() >= 1"""
if old in t2:
    t2 = t2.replace(old, new)
else:
    t2 = t2.replace("ev = ExperimentEvaluator()\n    metrics = ev.run(db)", "ev = ExperimentEvaluator(db)\n    metrics = ev.collect_predictions()")
    t2 = t2.replace('assert "accuracy" in metrics', 'assert "accuracy" in metrics["current_only_metrics"]')
    t2 = t2.replace('assert metrics["submission_count"] >= 1', "assert db.query(Submission).count() >= 1")
p2.write_text(t2, encoding="utf-8")

# conftest rollback autouse
conf = ROOT / "backend/tests/conftest.py"
ct = conf.read_text(encoding="utf-8")
if "_rollback_each_test" not in ct:
    ct += """

@pytest.fixture(autouse=True)
def _rollback_each_test(db):
    yield
    db.rollback()
"""
    conf.write_text(ct, encoding="utf-8")
print("patched tests")
