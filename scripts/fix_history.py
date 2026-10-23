from pathlib import Path
p = Path("backend/app/learner_model/history.py")
t = p.read_text(encoding="utf-8")
old = """        if misconception_id:
            from backend.app.analysis.static_analyzer import StaticAnalyzer
            cur_evs = db.query(EvidenceItem).filter(
                EvidenceItem.submission_id == current.id,
                EvidenceItem.misconception_id == misconception_id,
                EvidenceItem.direction == "support",
            ).count()
            if cur_evs:
                problems.add(current.problem_id)"""
new = """        cur_evs = db.query(EvidenceItem).filter(
            EvidenceItem.submission_id == current.id,
            EvidenceItem.misconception_id == misconception_id,
            EvidenceItem.direction == "support",
        ).count()
        if cur_evs and problems:
            problems.add(current.problem_id)"""
if old not in t:
    raise SystemExit("pattern missing")
p.write_text(t.replace(old, new), encoding="utf-8")
print("history fixed")
