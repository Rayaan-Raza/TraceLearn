from pathlib import Path
p = Path("backend/app/analysis/test_analyzer.py")
text = p.read_text(encoding="utf-8")
if "DIAGNOSTIC_CONFLICTING_OUTCOMES" not in text:
    insert = """
        by_tag: dict[str, list[bool]] = {}
        for tr, tc in rows:
            if tc.test_type == TestType.DIAGNOSTIC and tc.diagnostic_tag:
                by_tag.setdefault(tc.diagnostic_tag, []).append(tr.passed)
        for tag, passes in by_tag.items():
            if any(passes) and not all(passes):
                mid = TAG_TO_MIS.get(tag)
                items.append(EvidenceRecord(
                    source_type=\"test\", evidence_code=\"DIAGNOSTIC_CONFLICTING_OUTCOMES\",
                    misconception_id=mid, direction=\"conflict\", weight=0.0,
                    description=f\"diagnostic tests disagree for tag {tag}\",
                    details={\"tag\": tag},
                ))
        return items"""
    text = text.replace("        return items", insert, 1)
    p.write_text(text, encoding="utf-8")
    print("patched test_analyzer")

p2 = Path("backend/app/diagnosis/confidence.py")
t2 = p2.read_text(encoding="utf-8")
if "DIAGNOSTIC_CONFLICTING_OUTCOMES" not in t2:
    t2 = t2.replace(
        '"EXECUTION_SYNTAX_ERROR": w.get("conflicting_diagnostic", -0.20),',
        '"EXECUTION_SYNTAX_ERROR": w.get("conflicting_diagnostic", -0.20),\n        "DIAGNOSTIC_CONFLICTING_OUTCOMES": w.get("conflicting_diagnostic", -0.20),',
    )
if "DIAGNOSTIC_CONFLICTING_OUTCOMES" not in t2.split("fuse_diagnosis")[1]:
    marker = "    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)"
    block = """    if any(r.evidence_code == \"DIAGNOSTIC_CONFLICTING_OUTCOMES\" for r in weighted):
        uncertainty = \"high\"
        requires = True
        primary = UNCERTAIN if pconf < review_conf else primary
"""
    t2 = t2.replace(marker, block + marker)
    p2.write_text(t2, encoding="utf-8")
    print("patched confidence")
