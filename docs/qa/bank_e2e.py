"""Submit every C++ reference solution and misconception variant through the live API.

Usage: python bank_e2e.py <repo root> <base url> <out.json>
"""
import json, re, sys, time, uuid
from pathlib import Path
import httpx

ROOT, BASE, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
BANK_TO_BACKEND = {
    "CPP-M01": "CPP_LOOP_BOUNDARY", "CPP-M02": "M02_INDEX_VALUE", "CPP-M03": "M03_MISSING_RETURN",
    "CPP-M04": "CPP_ARRAY_BOUNDS", "CPP-M05": "CPP_RANGE_CHECK", "CPP-M06": "CPP_ASSIGN_VS_COMPARE",
    "CPP-M07": "CPP_MISSING_BASE_CASE", "CPP-M08": "CPP_STALE_EXIT",
}
cases = []  # (problem, kind, file, expected)
for pid in [f"CP{i:02d}" for i in range(1, 41)]:
    cases.append((pid, "reference", ROOT / "data/cpp_diagnostics/solutions" / f"{pid}.cpp", "NO_MISCONCEPTION"))
for vdir in (ROOT / "data/cpp_problems/variants", ROOT / "data/cpp_diagnostics/variants"):
    for f in sorted(vdir.glob("*.cpp")):
        if "sanitize-only" in f.name:
            continue
        pid = f.name.split("__")[0]
        m = re.search(r"__(CPP-M0\d)", f.name)
        if m:
            cases.append((pid, "variant", f, BANK_TO_BACKEND[m.group(1)]))
        elif "HARDNEG" in f.name:
            cases.append((pid, "hard_negative", f, "NO_MISCONCEPTION"))

RUN = uuid.uuid4().hex[:6]
clients, per_client = [], 10
for i in range((len(cases) + per_client - 1) // per_client):
    r = httpx.post(BASE + "/api/auth/register", json={"email": f"bank{i}_{RUN}@qa.test", "password": "Passw0rd!QA", "role": "student"}, timeout=30)
    r.raise_for_status()
    clients.append(httpx.Client(base_url=BASE, timeout=120, headers={"Authorization": "Bearer " + r.json()["access_token"]}))

rows = []
for n, (pid, kind, f, expected) in enumerate(cases):
    c = clients[n // per_client]
    sub = c.post("/api/submissions", json={"problem_id": pid, "source_code": f.read_text(encoding="utf-8")})
    if sub.status_code != 200:
        rows.append({"problem": pid, "kind": kind, "file": f.name, "error": sub.text[:200]}); continue
    sid = sub.json()["id"]
    r = c.post(f"/api/submissions/{sid}/run-and-analyze")
    if r.status_code != 200:
        rows.append({"problem": pid, "kind": kind, "file": f.name, "error": f"{r.status_code} {r.text[:200]}"}); continue
    j = r.json(); ha = j["history_aware"] or {}
    tests = j["test_results"]
    levels = []
    for _ in range(3):
        h = c.post(f"/api/submissions/{sid}/next-hint")
        if h.status_code == 200:
            levels.append(h.json()["level"])
    rows.append({
        "problem": pid, "kind": kind, "file": f.name, "expected": expected,
        "status": j["execution_status"], "passed": sum(t["passed"] for t in tests), "total": len(tests),
        "primary": ha.get("primary_misconception"), "confidence": round(ha.get("primary_confidence") or 0, 2),
        "review": ha.get("requires_teacher_review"), "first_hint_level": (j.get("hint") or {}).get("level"),
        "hint_levels_reached": max(levels) if levels else None,
        "correct": ha.get("primary_misconception") == expected,
    })
    print(f"{pid} {kind:13} {f.name:42} {j['execution_status']:12} {rows[-1]['passed']}/{rows[-1]['total']} -> {ha.get('primary_misconception')} ({rows[-1]['confidence']}) review={ha.get('requires_teacher_review')} expected={expected} {'OK' if rows[-1]['correct'] else 'MISS'}")

Path(OUT).write_text(json.dumps(rows, indent=1), encoding="utf-8")
for kind in ("reference", "variant", "hard_negative"):
    k = [r for r in rows if r.get("kind") == kind and "error" not in r]
    print(f"{kind}: {sum(r['correct'] for r in k)}/{len(k)} correct label, {sum(1 for r in k if r['review'])} need review")
print("errors:", [r for r in rows if "error" in r])
