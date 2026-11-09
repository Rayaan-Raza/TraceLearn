"""Mine real (failing -> accepted) attempt pairs and label each by the edit that fixed it.

    wsl python3 scripts/mine_fix_pairs.py --raw /mnt/g/TraceLearn/Datasets_RAW

For every failing submission with a LATER Accepted attempt by the same user on the same
problem, tokenise both versions and diff them. When the whole fix is ONE contiguous
token edit, that edit alone turns a failing program into a passing one, so the label is
read off the edit, not guessed from the failing code:

  `<`<->`<=` (or `>`<->`>=`) in a loop header        -> CPP_LOOP_BOUNDARY
  the same flip in an `if`/ternary condition          -> CPP_RANGE_CHECK
  a +1/-1 added/removed, or a literal moved by 1,
    in an index, bound, start value or count         -> CPP_OFF_BY_ONE
  a declared array size increased by more than 1     -> CPP_ARRAY_BOUNDS
  `=` -> `==` in a condition                         -> CPP_ASSIGN_VS_COMPARE
  `++` <-> `--` in a loop update                     -> CPP_WRONG_LOOP_DIR
  a declaration gains an initialiser                 -> CPP_UNINITIALIZED_VAR
  any other single-token edit                        -> CPP_OTHER_ERROR (output text, formula, ...)

Multi-edit fixes are not labelled (the failing cause is ambiguous). The failing code is
the only thing the model sees; the fix is used for the label and never as a feature.
Output: annotations/fix_pairs.jsonl (gitignored cache copy has the code).
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DS = ROOT / "data" / "misconception_dataset"
TOK = re.compile(r'"(?:\\.|[^"\\])*"|' + r"'(?:\\.|[^'\\])*'|[A-Za-z_]\w*|" + r"\d+\.?\d*|<<=|>>=|<=|>=|==|!=|\+\+|--|&&|\|\||<<|>>|->|[^\sA-Za-z_\d]")
CMP = {"<", "<=", ">", ">="}
NUM = re.compile(r"\d+")


def tokens(code: str) -> list[str]:
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", code, flags=re.S)
    return TOK.findall(code)


def enclosing(toks: list[str], at: int) -> str:
    """Keyword of the innermost `( ... )` header that contains token index `at`, else ''."""
    depth = 0
    for i in range(at - 1, -1, -1):
        t = toks[i]
        if t == ")":
            depth += 1
        elif t == "(":
            if depth == 0:
                return toks[i - 1] if i else ""
            depth -= 1
        elif t in (";", "{", "}") and depth == 0:
            break
    return ""


def in_brackets(toks: list[str], at: int) -> bool:
    depth = 0
    for i in range(at - 1, -1, -1):
        if toks[i] == "]":
            depth += 1
        elif toks[i] == "[":
            if depth == 0:
                return True
            depth -= 1
        elif toks[i] in (";", "{", "}"):
            break
    return False


def classify(old: list[str], new: list[str]) -> tuple[str, str] | None:
    """(label, short reason) when the fix is one contiguous edit, else None."""
    ops = [o for o in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes() if o[0] != "equal"]
    if len(ops) != 1:
        return None
    tag, i1, i2, j1, j2 = ops[0]
    a, b = old[i1:i2], new[j1:j2]
    if len(a) > 6 or len(b) > 6:
        return None
    where = enclosing(old, i1)
    text = f"{' '.join(a) or '-'} => {' '.join(b) or '-'}"
    if len(a) == 1 and len(b) == 1:
        x, y = a[0], b[0]
        if x in CMP and y in CMP and x.rstrip("=") == y.rstrip("="):
            if where in ("for", "while"):
                return "CPP_LOOP_BOUNDARY", f"loop operator {text}"
            if where in ("if", ""):
                return "CPP_RANGE_CHECK", f"condition operator {text}"
        if x in CMP and y in CMP and where in ("for", "while"):
            return "CPP_WRONG_LOOP_DIR", f"loop comparison direction {text}"
        if x == "=" and y == "==" and where in ("if", "while"):
            return "CPP_ASSIGN_VS_COMPARE", f"assignment in condition {text}"
        if x in ("++", "--") and y in ("++", "--"):
            return "CPP_WRONG_LOOP_DIR", f"loop step {text}"
        if NUM.fullmatch(x) and NUM.fullmatch(y):
            dx, dy = int(x), int(y)
            if abs(dx - dy) == 1:
                if where == "if":
                    return "CPP_RANGE_CHECK", f"condition constant {text}"
                return "CPP_OFF_BY_ONE", f"constant moved by one {text}"
            if in_brackets(old, i1) and dy > dx and where == "":
                return "CPP_ARRAY_BOUNDS", f"array size {text}"
    if tag in ("insert", "delete") or (a and b):
        pm = [t for t in a + b if t in ("+", "-")]
        nums = [t for t in a + b if NUM.fullmatch(t) and t == "1"]
        if pm and nums and len(a + b) <= 3 and tag in ("insert", "delete"):
            return "CPP_OFF_BY_ONE", f"+/-1 {'added' if tag == 'insert' else 'removed'}: {text}"
        if len(a) == len(b) == 0:
            return None
        if tag == "insert" and b[:1] == ["="] and i1 >= 1 and re.fullmatch(r"[A-Za-z_]\w*", old[i1 - 1]) and \
                i1 >= 2 and old[i1 - 2] in ("int", "float", "double", "long", "char"):
            return "CPP_UNINITIALIZED_VAR", f"initialiser added {text}"
    return "CPP_OTHER_ERROR", f"other edit {text}"


def hunks(old: list[str], new: list[str]):
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    return [o for o in sm.get_opcodes() if o[0] != "equal"]


def hunk_label(old, new, op):
    tag, i1, i2, j1, j2 = op
    return classify(old[:i1] + new[j1:j2] + old[i2:], old) and None  # placeholder, replaced below


def candidates(old: list[str], new: list[str], max_hunks: int = 4, max_tokens: int = 30):
    """Per-hunk classification of a small multi-edit fix: [(label, reason)], or None when too large."""
    ops = hunks(old, new)
    if not ops or len(ops) > max_hunks or sum(max(o[2] - o[1], o[4] - o[3]) for o in ops) > max_tokens:
        return None
    out = []
    for tag, i1, i2, j1, j2 in ops:
        a, b = old[max(0, i1 - 0):i2], new[j1:j2]
        mid_old = old[:i1] + a + old[i2:]
        # classify this hunk alone: diff old against old-with-only-this-hunk-applied
        patched = old[:i1] + b + old[i2:]
        r = classify(old, patched)
        if r:
            out.append(r)
    return out or None


def main(argv=None) -> int:
    from codestream_common import find_raw, load_problems, load_submissions
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None)
    args = ap.parse_args(argv)
    raw = find_raw(args.raw)
    subs = load_submissions(raw)
    groups = defaultdict(list)
    for s in subs:
        groups[(s.user_id, s.problem_id)].append(s)
    rows = []
    multi = []
    for group in groups.values():
        group.sort(key=lambda s: s.attempt_number)
        for i, s in enumerate(group):
            if s.verdict == "Accepted" or s.verdict == "Compilation Error":
                continue
            fixed = next((t for t in group[i + 1:] if t.verdict == "Accepted"), None)
            if fixed is None:
                continue
            res = classify(tokens(s.code), tokens(fixed.code))
            if not res:
                cands = candidates(tokens(s.code), tokens(fixed.code))
                multi.append((s, fixed, cands))
            if res:
                rows.append({"submission_id": s.submission_id, "problem_id": s.problem_id, "verdict": s.verdict,
                             "label": res[0], "edit": res[1], "fixed_submission_id": fixed.submission_id,
                             "attempts_to_fix": fixed.attempt_number - s.attempt_number})
    rows.sort(key=lambda r: r["submission_id"])
    out = DS / "cache" / "fix_pairs.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(len(rows), "single-edit fix pairs;", Counter(r["label"] for r in rows).most_common())
    print("problems:", len({r["problem_id"] for r in rows}))
    c2 = Counter()
    for s, fixed, cands in multi:
        if cands:
            for lab in {c[0] for c in cands if c[0] != "CPP_OTHER_ERROR"}:
                c2[lab] += 1
    print("multi-edit pairs with a classifiable hunk:", c2.most_common(), "of", len(multi))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
