"""Print the evidence the analyser records for given bank solutions (via the live API)."""
import sys, uuid
from pathlib import Path
import httpx

ROOT, BASE = Path(sys.argv[1]), sys.argv[2]
R = uuid.uuid4().hex[:6]
tok = httpx.post(BASE + "/api/auth/register", json={"email": f"ev_{R}@qa.test", "password": "Passw0rd!QA", "role": "student"}).json()["access_token"]
C = httpx.Client(base_url=BASE, timeout=120, headers={"Authorization": "Bearer " + tok})
for name in sys.argv[3:]:
    path = ROOT / "data/cpp_diagnostics/solutions" / f"{name}.cpp" if "__" not in name else next((ROOT / "data").glob(f"cpp_*/variants/{name}"))
    sid = C.post("/api/submissions", json={"problem_id": name[:4], "source_code": path.read_text(encoding="utf-8")}).json()["id"]
    C.post(f"/api/submissions/{sid}/run-and-analyze")
    print("==", name)
    for e in C.get(f"/api/submissions/{sid}/evidence").json():
        if e["direction"] != "neutral":
            print("  ", e["source_type"], e["evidence_code"], e["misconception_id"], e["direction"], e["weight"], "|", e["description"][:90])
