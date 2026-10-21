"""Repair-and-rerun verification (Master Plan §5-U2, Layer 4).

When a labeling function fires class C on a real row, apply the *inverse*
operator of C — one minimal edit at a time — and re-run the problem's tests.
If one edit makes every test pass, the row is ``repair_verified`` for C and
counts toward the certain floor. The proof (edit, line, before/after text,
tests passed) is stored on the row.

Each candidate generator returns ``Repair`` objects; none of them reformat
code. The same operators double-check Eman's mutation operators: a mutant
whose inverse repair does not restore the seed is suspicious.

    python scripts/repair_verify.py FILE.cpp --class CPP_LOOP_BOUNDARY --tests tests.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from codestream_static import (  # noqa: E402
    CMP_RE, Program, Span, assigned_vars, comparisons, line_of, parse, splice,
)

MAX_CANDIDATES = 12
FLIP = {"<=": "<", "<": "<=", ">=": ">", ">": ">="}


@dataclass
class Repair:
    cls: str
    op: str
    line: int
    before: str
    after: str
    code: str

    def proof(self) -> dict:
        d = asdict(self)
        d.pop("code")
        return d


def _mk(cls, op, prog: Program, start, end, new) -> Repair:
    return Repair(cls, op, line_of(prog.code, start), prog.code[start:end], new,
                  splice(prog.code, start, end, new))


# ------------------------------------------------------------- class 1 ----

def repairs_loop_boundary(prog: Program) -> list[Repair]:
    out = []
    for lp in prog.loops:
        if not lp.cond:
            continue
        for op, a, b in comparisons(prog.text, lp.cond):
            if op in FLIP:
                out.append(_mk("CPP_LOOP_BOUNDARY", f"loop_cmp_{op}_to_{FLIP[op]}", prog, a, b, FLIP[op]))
        seg = prog.text[lp.cond.start:lp.cond.end]
        for m in re.finditer(r"(<|!=)\s*([A-Za-z_]\w*(?:\s*\.\s*\w+\s*\(\s*\))?)\s*\+\s*1\b", seg):
            a = lp.cond.start + m.start()
            b = lp.cond.start + m.end()
            new = f"{m.group(1)} {prog.code[lp.cond.start + m.start(2):lp.cond.start + m.end(2)]}"
            out.append(_mk("CPP_LOOP_BOUNDARY", f"loop_{m.group(1)}_n_plus_1_to_n", prog, a, b, new))
    return out[:MAX_CANDIDATES]


# ------------------------------------------------------------- class 2 ----

def repairs_off_by_one(prog: Program) -> list[Repair]:
    out = []
    t = prog.text
    for lp in prog.loops:
        if lp.kind == "for" and lp.init:
            seg = t[lp.init.start:lp.init.end]
            m = re.search(r"=\s*([01])\s*$", seg)
            if m:
                a = lp.init.start + m.start(1)
                new = "1" if m.group(1) == "0" else "0"
                out.append(_mk("CPP_OFF_BY_ONE", f"init_{m.group(1)}_to_{new}", prog, a, a + 1, new))
        if lp.cond:
            seg = t[lp.cond.start:lp.cond.end]
            for m in re.finditer(r"\s*-\s*1\b", seg):
                a, b = lp.cond.start + m.start(), lp.cond.start + m.end()
                out.append(_mk("CPP_OFF_BY_ONE", "bound_minus_1_removed", prog, a, b, ""))
            m = re.search(r"(<=|<|>=|>|!=)\s*([A-Za-z_]\w*)\s*$", seg)
            if m and not re.search(r"[+-]\s*1\s*$", seg):
                a = lp.cond.start + m.end(2)
                out.append(_mk("CPP_OFF_BY_ONE", "bound_minus_1_added", prog, a, a, " - 1"))
    for m in re.finditer(r"\[\s*([A-Za-z_]\w*)\s*([+-])\s*1\s*\]", t):
        a, b = m.start(), m.end()
        out.append(_mk("CPP_OFF_BY_ONE", f"index_{m.group(2)}1_removed", prog, a, b,
                       f"[{prog.code[m.start(1):m.end(1)]}]"))
    for m in re.finditer(r"\[\s*([A-Za-z_]\w*)\s*\]", t):
        if len(out) >= MAX_CANDIDATES * 2:
            break
        v = prog.code[m.start(1):m.end(1)]
        for sign in ("-", "+"):
            out.append(_mk("CPP_OFF_BY_ONE", f"index_{sign}1_added", prog, m.start(), m.end(),
                           f"[{v} {sign} 1]"))
    # ±1 on printed values: cout << x + 1  /  printf("%d", x - 1)
    for m in re.finditer(r"(<<|,)\s*([A-Za-z_]\w*)\s*([+-])\s*1\b(?=\s*(?:<<|;|\)|,))", t):
        a, b = m.start(2), m.end()
        out.append(_mk("CPP_OFF_BY_ONE", f"output_{m.group(3)}1_removed", prog, a, b,
                       prog.code[m.start(2):m.end(2)]))
    return out[:MAX_CANDIDATES]


# ------------------------------------------------------------- class 3 ----

def _size_value(prog: Program, size: str):
    size = size.strip()
    if re.fullmatch(r"\d+", size):
        return int(size)
    if size in prog.defines:
        return prog.defines[size]
    m = re.fullmatch(r"(\d+)\s*\+\s*(\d+)", size)
    if m:
        return int(m.group(1)) + int(m.group(2))
    return None


def repairs_array_bounds(prog: Program) -> list[Repair]:
    out = []
    for d in prog.decls:
        if not d.array_size_span:
            continue
        v = _size_value(prog, d.array_size or "")
        if v is None or v <= 0:
            continue
        new_v = max(v * 10, v + 1000)
        if new_v * 8 > 48 * 1024 * 1024 and d.in_function:
            continue  # would blow the 64 MB stack
        s = d.array_size_span
        out.append(_mk("CPP_ARRAY_BOUNDS", f"enlarge_{d.var}_{v}_to_{new_v}", prog, s.start, s.end,
                       str(new_v)))
    return out[:MAX_CANDIDATES]


# ------------------------------------------------------------- class 4 ----

def repairs_uninitialized(prog: Program, lines: set[int] | None = None) -> list[Repair]:
    out = []
    for d in prog.decls:
        if d.initialized or d.array_size_span or not d.in_function:
            continue
        s = d.span
        out.append(_mk("CPP_UNINITIALIZED_VAR", f"init_{d.var}_0", prog, s.end, s.end, " = 0"))
    if lines:
        # variables mentioned on the flagged lines first
        flagged = set()
        for ln in lines:
            row = prog.code.split("\n")[ln - 1] if 0 < ln <= prog.code.count("\n") + 1 else ""
            flagged |= set(re.findall(r"\b[A-Za-z_]\w*\b", row))
        out.sort(key=lambda r: 0 if r.op[5:-2] in flagged else 1)
    return out[:MAX_CANDIDATES]


# ------------------------------------------------------------- class 5 ----

def repairs_int_overflow(prog: Program) -> list[Repair]:
    code = prog.code
    new = re.sub(r"\bint\b(?!\s+main\b)", "long long", code)
    new = re.sub(r"\blong long long long\b", "long long", new)
    new = re.sub(r"\blong\s+long\s+long\b", "long long", new)
    new = re.sub(r"\bunsigned long long\b", "unsigned long long", new)
    new = re.sub(r"%(\d*)d", r"%\1lld", new)
    new = re.sub(r"%(\d*)i\b", r"%\1lld", new)
    new = re.sub(r"%(\d*)u", r"%\1llu", new)
    new = new.replace("%llld", "%lld").replace("%lllld", "%lld")
    new = re.sub(r"%l+ld", "%lld", new)
    new = re.sub(r"\babs\s*\(", "llabs(", new) if prog.code.lstrip().startswith("#include <stdio") else new
    if new == code:
        return []
    return [Repair("CPP_INT_OVERFLOW", "int_to_long_long", 1, "int", "long long", new)]


# ------------------------------------------------------------- class 6 ----

def recursive_functions(prog: Program):
    out = []
    for f in prog.functions:
        body = prog.text[f.body.start:f.body.end]
        if re.search(r"\b" + re.escape(f.name) + r"\s*\(", body):
            out.append(f)
    return out


def repairs_missing_base_case(prog: Program) -> list[Repair]:
    out = []
    for f in recursive_functions(prog):
        void = re.search(r"\bvoid\b", f.return_type) is not None
        at = f.body.start + 1
        for p in f.params[:2]:
            if void:
                guards = [f"if ({p} <= 0) return;", f"if ({p} < 0) return;"]
            else:
                guards = [f"if ({p} <= 0) return 0;", f"if ({p} <= 1) return {p};",
                          f"if ({p} <= 1) return 1;", f"if ({p} == 0) return 1;",
                          f"if ({p} < 0) return 0;"]
            for g in guards:
                out.append(Repair("CPP_MISSING_BASE_CASE", "add_guard", f.line, "", g,
                                  splice(prog.code, at, at, " " + g + " ")))
    return out[:MAX_CANDIDATES]


# ------------------------------------------------------------- class 7 ----

ASSIGN_IN_COND = re.compile(r"(?<![=!<>+\-*/%&|^])=(?!=)")


def assignments_in_conditions(prog: Program):
    """(cond, abs_offset, assigned_var) for `=` used inside if/while/for-test."""
    out = []
    for c in prog.conds:
        if c.kind not in ("if", "while", "for"):
            continue
        seg = prog.text[c.span.start:c.span.end]
        for m in ASSIGN_IN_COND.finditer(seg):
            left = seg[:m.start()]
            vm = re.search(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*$", left)
            out.append((c, c.span.start + m.start(), vm.group(1) if vm else None))
    return out


def repairs_assign_vs_compare(prog: Program) -> list[Repair]:
    return [_mk("CPP_ASSIGN_VS_COMPARE", "assign_to_eq", prog, off, off + 1, "==")
            for _, off, _ in assignments_in_conditions(prog)][:MAX_CANDIDATES]


# ------------------------------------------------------------- class 8 ----

def descending_for_loops(prog: Program):
    out = []
    t = prog.text
    for lp in prog.loops:
        if lp.kind != "for" or not (lp.init and lp.cond and lp.step) or not lp.var:
            continue
        v = re.escape(lp.var)
        step = t[lp.step.start:lp.step.end].strip()
        if not re.fullmatch(rf"(?:{v}\s*--|--\s*{v}|{v}\s*-=\s*1|{v}\s*=\s*{v}\s*-\s*1)", step):
            continue
        init = t[lp.init.start:lp.init.end]
        im = re.search(rf"\b{v}\s*=\s*(.+)$", init.strip())
        cm = re.fullmatch(rf"\s*{v}\s*(>=|>)\s*(.+?)\s*", t[lp.cond.start:lp.cond.end])
        if im and cm:
            out.append((lp, im.group(1).strip(), cm.group(1), cm.group(2).strip()))
    return out


def repairs_wrong_loop_dir(prog: Program) -> list[Repair]:
    out = []
    for lp, start, op, bound in descending_for_loops(prog):
        lo = bound if op == ">=" else f"{bound} + 1"
        decl = re.match(r"\s*((?:unsigned\s+|long\s+|short\s+)*(?:int|long|size_t|unsigned)\s+)",
                        prog.text[lp.init.start:lp.init.end])
        prefix = decl.group(1) if decl else ""
        new_hdr = f"{prefix}{lp.var} = {lo}; {lp.var} <= {start}; {lp.var}++"
        out.append(Repair("CPP_WRONG_LOOP_DIR", "reverse_loop_direction", lp.line,
                          prog.code[lp.init.start:lp.step.end], new_hdr,
                          splice(prog.code, lp.init.start, lp.step.end, new_hdr)))
    return out[:MAX_CANDIDATES]


# ------------------------------------------------------------- class 9 ----

def range_check_conditions(prog: Program):
    """if-conditions that look like range validation: a comparison against a
    literal, or two comparisons on the same variable joined by && / ||."""
    out = []
    for c in prog.conds:
        if c.kind != "if":
            continue
        seg = prog.text[c.span.start:c.span.end]
        cmps = list(comparisons(prog.text, c.span))
        rel = [x for x in cmps if x[0] in FLIP]
        if not rel:
            continue
        lit = re.search(r"(?:<=|>=|<|>)\s*-?\d+\b|-?\b\d+\s*(?:<=|>=|<|>)", seg)
        names = re.findall(r"([A-Za-z_]\w*)\s*(?:<=|>=|<|>)", seg)
        same_var = len(names) >= 2 and len(set(names)) < len(names) and ("&&" in seg or "||" in seg)
        if lit or same_var:
            out.append((c, rel))
    return out


def repairs_range_check(prog: Program) -> list[Repair]:
    out = []
    for c, rel in range_check_conditions(prog):
        for op, a, b in rel:
            out.append(_mk("CPP_RANGE_CHECK", f"if_cmp_{op}_to_{FLIP[op]}", prog, a, b, FLIP[op]))
    return out[:MAX_CANDIDATES]


# ------------------------------------------------------------ class 10 ----

def stale_while_loops(prog: Program):
    """while loops whose condition variables are never written in the body."""
    out = []
    for lp in prog.loops:
        if lp.kind != "while" or not lp.cond:
            continue
        cond = prog.text[lp.cond.start:lp.cond.end]
        if re.search(r"\b(?:scanf|cin|getline|getchar|gets|fgets|read)\b|\(\s*\)|\w\s*\(", cond):
            continue  # condition calls a function / reads input: updates itself
        if re.fullmatch(r"\s*(?:1|true)\s*", cond):
            continue
        vars_ = set(re.findall(r"\b([A-Za-z_]\w*)\b", cond)) - {"true", "false", "NULL"}
        if not vars_:
            continue
        written = assigned_vars(prog.text, lp.body) | assigned_vars(prog.text, lp.cond)
        body = prog.text[lp.body.start:lp.body.end]
        if re.search(r"\bbreak\b|\breturn\b|\bexit\s*\(|\bgoto\b", body):
            continue
        if not (vars_ & written):
            out.append((lp, sorted(vars_)))
    return out


GENERATORS = {
    "CPP_LOOP_BOUNDARY": repairs_loop_boundary,
    "CPP_OFF_BY_ONE": repairs_off_by_one,
    "CPP_ARRAY_BOUNDS": repairs_array_bounds,
    "CPP_UNINITIALIZED_VAR": repairs_uninitialized,
    "CPP_INT_OVERFLOW": repairs_int_overflow,
    "CPP_MISSING_BASE_CASE": repairs_missing_base_case,
    "CPP_ASSIGN_VS_COMPARE": repairs_assign_vs_compare,
    "CPP_WRONG_LOOP_DIR": repairs_wrong_loop_dir,
    "CPP_RANGE_CHECK": repairs_range_check,
    # CPP_STALE_EXIT has no safe generic inverse operator: detector + human review only.
}


def candidates(code: str, cls: str, prog: Program | None = None, **kw) -> list[Repair]:
    prog = prog or parse(code)
    gen = GENERATORS.get(cls)
    if not gen:
        return []
    if cls == "CPP_UNINITIALIZED_VAR":
        return gen(prog, kw.get("lines"))
    return gen(prog)


def verify(code: str, lang: str, tests: list[dict], cls: str, *, prog: Program | None = None,
           cache_dir: str | None = None, max_tries: int = MAX_CANDIDATES, **kw) -> dict:
    """Try the inverse operators of ``cls``; return the first edit that passes every test."""
    from sandbox_runner import RunConfig, run_submission
    cfg = RunConfig(sanitizer_pass=False, valgrind_pass=False, double_run=False,
                    stop_after_timeouts=1)
    tried = []
    for rep in candidates(code, cls, prog, **kw)[:max_tries]:
        res = run_submission(rep.code, lang, tests, cfg, cache_dir=cache_dir)
        t = res.get("tests") or {}
        ok = bool(res.get("compile", {}).get("ok")) and bool(t.get("all_passed"))
        tried.append({"op": rep.op, "line": rep.line, "passed": t.get("passed"),
                      "total": t.get("total"), "compiled": res.get("compile", {}).get("ok")})
        if ok:
            return {"verified": True, "class": cls, "repair": rep.proof(), "tries": tried,
                    "proof": {"tests_passed": t.get("passed"), "tests_total": t.get("total"),
                              "cache_key": res.get("cache_key")}}
    return {"verified": False, "class": cls, "tries": tried}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--class", dest="cls", required=True, choices=sorted(GENERATORS))
    ap.add_argument("--tests", required=True)
    ap.add_argument("--lang", default=None)
    a = ap.parse_args()
    code = Path(a.source).read_text(encoding="utf-8")
    lang = a.lang or ("c" if a.source.endswith(".c") else "cpp")
    tests = json.loads(Path(a.tests).read_text(encoding="utf-8"))
    print(json.dumps(verify(code, lang, tests, a.cls), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
