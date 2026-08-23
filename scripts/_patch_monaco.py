from pathlib import Path
app = Path("frontend/src/App.tsx")
text = app.read_text(encoding="utf-8")
old = "options={{ lineNumbers: 'on', fontSize: 14, minimap: { enabled: false } }}"
new = """options={{
              lineNumbers: 'on',
              fontSize: 14,
              minimap: { enabled: false },
              automaticLayout: true,
              autoIndent: 'full',
              matchBrackets: 'always',
              bracketPairColorization: { enabled: true },
              tabSize: 4,
              insertSpaces: true,
            }}"""
if old in text:
    app.write_text(text.replace(old, new), encoding="utf-8")
    print("monaco ok")
cfg = Path("backend/app/config.py")
ct = cfg.read_text(encoding="utf-8")
if "5173" not in ct:
    ct = ct.replace(
        '["http://localhost:3000", "http://127.0.0.1:3000"]',
        '["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"]',
    )
    cfg.write_text(ct, encoding="utf-8")
    print("cors ok")
