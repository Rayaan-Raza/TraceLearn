from pathlib import Path
p = Path("backend/app/diagnosis/confidence.py")
t = p.read_text(encoding="utf-8")
bad = """    if any(r.evidence_code == \"DIAGNOSTIC_CONFLICTING_OUTCOMES\" for r in weighted):
        uncertainty = \"high\"
        requires = True
        primary = UNCERTAIN if pconf < review_conf else primary
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)"""
good = """    conflict_diag = any(r.evidence_code == \"DIAGNOSTIC_CONFLICTING_OUTCOMES\" for r in weighted)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)"""
if bad in t:
    t = t.replace(bad, good)
else:
    raise SystemExit('bad block not found')
insert_after = """    else:
        uncertainty = \"low\"
        requires = False"""
replacement = """    else:
        uncertainty = \"low\"
        requires = False
    if conflict_diag:
        uncertainty = \"high\"
        requires = True"""
if insert_after in t:
    t = t.replace(insert_after, replacement, 1)
p.write_text(t, encoding="utf-8")
print('fixed confidence')
