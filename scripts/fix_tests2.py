from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

def w(rel, text):
    (ROOT / rel).write_text(text.strip() + "\n", encoding="utf-8", newline="\n")

conf = (ROOT / "backend/app/diagnosis/confidence.py").read_text(encoding="utf-8")
if "conflict = any" not in conf:
    conf = conf.replace(
        "    if pconf < review_conf or (alt and abs(pconf - (aconf or 0)) < margin):",
        "    conflict = any(r.direction == \"conflict\" and r.weight for r in weighted)\n    if pconf < review_conf or (alt and abs(pconf - (aconf or 0)) < margin) or conflict:",
    )
    (ROOT / "backend/app/diagnosis/confidence.py").write_text(conf, encoding="utf-8")

# write test files from fix_all remainder - invoke by reading fix_all and exec from line 42
exec(open(ROOT / "scripts/fix_all.py", encoding="utf-8").read().split("# confidence conflict check")[1].split("print(\"all fixes written\")")[0])
print("done")
