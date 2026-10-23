from pathlib import Path
ROOT = Path("c:/Users/rayaan/Desktop/POC")

def w(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print("w", rel)
