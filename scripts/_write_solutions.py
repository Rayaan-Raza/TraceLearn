from pathlib import Path
import json
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")
data = json.loads((ROOT / "data/problems/problems.json").read_text(encoding="utf-8"))
sol_dir = ROOT / "data/problems/solutions"
sol_dir.mkdir(parents=True, exist_ok=True)
# Reference solutions match starter (correct implementations)
for p in data["problems"]:
    (sol_dir / f"{p['id']}.py").write_text(p["starter_code"], encoding="utf-8", newline="\n")
    print("solution", p["id"])
