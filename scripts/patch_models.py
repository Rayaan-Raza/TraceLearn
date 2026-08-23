from pathlib import Path
p = Path("backend/app/db/models.py")
t = p.read_text(encoding="utf-8-sig")
replacements = [
    ('FAILED = "failed"\n    ERROR = "error"', 'SYNTAX_ERROR = "syntax_error"\n    RUNTIME_ERROR = "runtime_error"\n    SYSTEM_ERROR = "system_error"'),
    (
        'STATIC_ANALYSIS = "static_analysis"\n    TEST_OUTCOME = "test_outcome"\n    RUNTIME = "runtime"\n    AST_PATTERN = "ast_pattern"',
        'EXECUTION = "execution"\n    TEST = "test"\n    STATIC = "static"\n    SEQUENCE = "sequence"\n    HISTORY = "history"\n    CONTEXT = "context"',
    ),
]
for a, b in replacements:
    if a not in t:
        raise SystemExit(f"missing: {a[:40]}")
    t = t.replace(a, b)
p.write_text(t, encoding="utf-8")
print("models patched")
