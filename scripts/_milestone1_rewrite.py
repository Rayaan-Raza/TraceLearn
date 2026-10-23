from pathlib import Path

ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

(ROOT / "backend/app/db/models.py").write_text(Path(r"c:/Users/rayaan/Desktop/POC/scripts/_models_content.txt").read_text(encoding="utf-8") if False else "", encoding="utf-8")
