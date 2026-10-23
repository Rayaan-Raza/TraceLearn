from pathlib import Path
p = Path("backend/app/execution/test_runner.py")
lines = p.read_text(encoding="utf-8").splitlines()
out = []
i = 0
while i < len(lines):
    if lines[i].strip().startswith("submission.stderr = ") and i + 1 < len(lines) and lines[i+1].strip().startswith(".join(stderr_parts)"):
        out.append('    submission.stderr = "\\n".join(stderr_parts)')
        i += 2
        continue
    out.append(lines[i])
    i += 1
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("fixed test_runner")
