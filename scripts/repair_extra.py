"""A second set of inverse edits, for the mistakes `repair_verify.GENERATORS` cannot try.

Measured on the training problems, the first set's own-class repair fixed the first failing test
on 0 of 11 RANGE_CHECK, 0 of 7 STALE_EXIT, 8 of 36 UNINITIALIZED_VAR and 38 of 122 ARRAY_BOUNDS
rows, and OFF_BY_ONE hit the candidate cap on 26 of 39 before reaching its printed-value edits.

These are kept apart from `repair_verify`, whose operators back the `repair_verified` label proofs:
a change there would change what those proofs mean. Nothing here reads a label.

Some operators edit several places at once, because the mistake repeats: `65<=ch<=90` usually has an
`else if (97<=ch<=122)` beside it, and one fix alone passes nothing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codestream_static import Program, comparisons, splice  # noqa: E402
from repair_verify import FLIP, Repair, _mk, _size_value, stale_while_loops  # noqa: E402

MAX_CANDIDATES = 16
REVERSE = {"<=": ">=", ">=": "<=", "<": ">", ">": "<"}
_OPERAND = r"(?:'[^']*'|[A-Za-z_]\w*(?:\[[^\]]*\])?|-?\d+)"
_CHAINED = re.compile(rf"({_OPERAND})\s*(<=|>=|<|>)\s*({_OPERAND})\s*(<=|>=|<|>)\s*({_OPERAND})")


def _apply(prog: Program, edits: list[tuple[int, int, str]]) -> str:
    """Apply (start, end, new) edits from the back, so earlier offsets stay valid."""
    code = prog.code
    for start, end, new in sorted(edits, key=lambda e: -e[0]):
        code = splice(code, start, end, new)
    return code


def _multi(cls: str, op: str, prog: Program, edits: list[tuple[int, int, str]], line: int = 1) -> Repair:
    return Repair(cls, op, line, "", "", _apply(prog, edits))


def _if_spans(prog: Program):
    return [c for c in prog.conds if c.kind == "if"]


# ---------------------------------------------------------------- RANGE_CHECK


def _chained_edits(prog: Program) -> list[tuple[int, int, str]]:
    out = []
    for c in prog.conds:
        if c.kind not in ("if", "while", "for"):
            continue
        for m in _CHAINED.finditer(prog.text[c.span.start:c.span.end]):
            base = c.span.start
            part = lambda g: prog.code[base + m.start(g):base + m.end(g)]  # noqa: E731,B023
            out.append((base + m.start(), base + m.end(),
                        f"{part(1)} {m.group(2)} {part(3)} && {part(3)} {m.group(4)} {part(5)}"))
    return out


def extra_range_check(prog: Program) -> list[Repair]:
    cls = "CPP_RANGE_CHECK"
    out = []
    chained = _chained_edits(prog)
    if chained:
        out.append(_multi(cls, "chained_compare_split_all", prog, chained))
    for c in _if_spans(prog):
        cmps = [x for x in comparisons(prog.text, c.span) if x[0] in REVERSE]
        if len(cmps) >= 2:
            out.append(_multi(cls, "if_reverse_all_comparisons", prog, [(a, b, REVERSE[op]) for op, a, b in cmps], c.line))
        seg = prog.text[c.span.start:c.span.end]
        logic = [(c.span.start + m.start(), c.span.start + m.end(), "||" if m.group() == "&&" else "&&")
                 for m in re.finditer(r"&&|\|\|", seg)]
        if logic:
            out.append(_multi(cls, "if_swap_and_or", prog, logic, c.line))
    for c in _if_spans(prog):
        for op, a, b in comparisons(prog.text, c.span):
            if op in FLIP:
                out.append(_mk(cls, f"if_any_cmp_{op}_to_{FLIP[op]}", prog, a, b, FLIP[op]))
            if op in REVERSE:
                out.append(_mk(cls, f"if_any_cmp_{op}_to_{REVERSE[op]}", prog, a, b, REVERSE[op]))
    return out[:MAX_CANDIDATES]


# --------------------------------------------------------------- ARRAY_BOUNDS


def _dynamic_size_edits(prog: Program) -> list[tuple[str, int, int, str]]:
    """(name, start, end, new) for sizes that are not constants: a[n], new T[n], malloc(n), vector<T> v(n)."""
    out = []
    for d in prog.decls:
        s = d.array_size_span
        if s and d.array_size and _size_value(prog, d.array_size) is None:
            out.append((d.var, s.start, s.end, f"({prog.code[s.start:s.end]}) + 1000"))
    for pattern, tag in ((r"\bnew\s+[\w:<>]+\s*\[\s*([^\]]+?)\s*\]", "new"), (r"\bmalloc\s*\(\s*([^;]+?)\s*\)\s*;", "malloc"),
                         (r"\bvector\s*<[^;>]*>\s*\w+\s*\(\s*([^,;)]+?)\s*[,)]", "vector")):
        for m in re.finditer(pattern, prog.text):
            a, b = m.start(1), m.end(1)
            extra = "+ 8000" if tag == "malloc" else "+ 1000"
            out.append((tag, a, b, f"({prog.code[a:b]}) {extra}"))
    return out


def extra_array_bounds(prog: Program) -> list[Repair]:
    cls = "CPP_ARRAY_BOUNDS"
    dynamic = _dynamic_size_edits(prog)
    out = [_mk(cls, f"enlarge_dynamic_{name}", prog, a, b, new) for name, a, b, new in dynamic]
    whole = [(a, b, new) for _, a, b, new in dynamic]
    for d in prog.decls:
        s = d.array_size_span
        value = _size_value(prog, d.array_size or "") if s else None
        if value is not None and 0 < value:
            bigger = max(value * 10, value + 1000)
            if not (bigger * 8 > 48 * 1024 * 1024 and d.in_function):
                whole.append((s.start, s.end, str(bigger)))
    if len(whole) >= 2:
        out.insert(0, _multi(cls, "enlarge_every_array", prog, whole))
    return out[:MAX_CANDIDATES]


# ---------------------------------------------------------- UNINITIALIZED_VAR


def extra_uninitialized(prog: Program) -> list[Repair]:
    cls = "CPP_UNINITIALIZED_VAR"
    out = []
    scalars = [d for d in prog.decls if d.in_function and not d.initialized and not d.array_size_span]
    if len(scalars) >= 2:
        out.append(_multi(cls, "init_every_scalar_0", prog, [(d.span.end, d.span.end, " = 0") for d in scalars]))
    for d in prog.decls:
        s = d.array_size_span
        if not (s and d.in_function and not d.initialized and _size_value(prog, d.array_size or "") is not None):
            continue
        m = re.match(r"\s*\]\s*(?:\[[^\]]*\]\s*)*", prog.text[s.end:])
        if m:
            at = s.end + m.end()
            out.append(_mk(cls, f"init_array_{d.var}_0", prog, at, at, " = {0}"))
    for d in scalars:
        out.append(_mk(cls, f"init_{d.var}_1", prog, d.span.end, d.span.end, " = 1"))
    return out[:MAX_CANDIDATES]


# ----------------------------------------------------------------- OFF_BY_ONE


def extra_off_by_one(prog: Program) -> list[Repair]:
    """Edits to values and formulas, not to loop headers: `repair_verify` covers those first."""
    cls = "CPP_OFF_BY_ONE"
    t = prog.text
    headers = [(lp.keyword, lp.body.start) for lp in prog.loops]
    in_header = lambda i: any(a <= i < b for a, b in headers)  # noqa: E731
    out = []
    for m in re.finditer(r"(<<|,)\s*([A-Za-z_]\w*)\s*([+-])\s*1\b(?=\s*(?:<<|;|\)|,))", t):
        out.append(_mk(cls, f"output_{m.group(3)}1_removed", prog, m.start(2), m.end(), prog.code[m.start(2):m.end(2)]))
    for m in re.finditer(r"\breturn\s+([A-Za-z_]\w*)\s*([+-])\s*1\s*;", t):
        out.append(_mk(cls, f"return_{m.group(2)}1_removed", prog, m.start(1), m.end() - 1, prog.code[m.start(1):m.end(1)]))
    for m in re.finditer(r"(<<\s*|,\s*)([A-Za-z_]\w*)(?=\s*(?:<<\s*(?:endl|\"|'|[A-Za-z_])|;|\)\s*;))", t):
        if prog.text[m.start(2):m.end(2)] in ("endl", "cout", "cin", "stdin", "stdout"):
            continue
        v = prog.code[m.start(2):m.end(2)]
        for sign in ("+", "-"):
            out.append(_mk(cls, f"output_{sign}1_added", prog, m.start(2), m.end(2), f"{v} {sign} 1"))
    for m in re.finditer(r"\breturn\s+([A-Za-z_]\w*)\s*;", t):
        v = prog.code[m.start(1):m.end(1)]
        for sign in ("+", "-"):
            out.append(_mk(cls, f"return_{sign}1_added", prog, m.start(1), m.end(1), f"{v} {sign} 1"))
    for m in re.finditer(r"([+-])\s*1\b(?!\s*[\]\d])", t):
        if in_header(m.start()) or t[max(m.start() - 1, 0)] in "+-":
            continue
        swap = "-" if m.group(1) == "+" else "+"
        out.append(_mk(cls, f"formula_{m.group(1)}1_to_{swap}1", prog, m.start(1), m.end(1), swap))
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*=\s*([01])\s*(?=[;,])", t):
        if not in_header(m.start()):
            new = "1" if m.group(2) == "0" else "0"
            out.append(_mk(cls, f"start_{m.group(2)}_to_{new}", prog, m.start(2), m.end(2), new))
    return out[:MAX_CANDIDATES]


# ----------------------------------------------------------------- STALE_EXIT


def _step_var(step: str) -> str | None:
    m = re.search(r"\b([A-Za-z_]\w*)\s*(?:\+\+|--|[+\-*/]=)", step) or re.search(r"(?:\+\+|--)\s*([A-Za-z_]\w*)", step)
    return m.group(1) if m else None


def extra_stale_exit(prog: Program) -> list[Repair]:
    """Make the loop's condition move: test the variable the step changes, or add the missing update."""
    cls = "CPP_STALE_EXIT"
    out = []
    t = prog.text
    for lp in prog.loops:
        if lp.kind != "for" or not (lp.cond and lp.step):
            continue
        step_var = _step_var(t[lp.step.start:lp.step.end])
        cond = t[lp.cond.start:lp.cond.end]
        m = re.match(r"\s*([A-Za-z_]\w*)\s*(?:<=|>=|<|>|!=)", cond)
        if step_var and m and m.group(1) != step_var and not re.search(rf"\b{re.escape(step_var)}\b", cond):
            a = lp.cond.start + m.start(1)
            out.append(_mk(cls, "for_test_the_stepped_variable", prog, a, a + len(m.group(1)), step_var))
    for lp, names in stale_while_loops(prog):
        body = lp.body
        braced = t[body.start:body.end].lstrip().startswith("{")
        cond = t[lp.cond.start:lp.cond.end]
        for var in names:
            pointer = re.search(rf"\b{re.escape(var)}\s*!=\s*(?:NULL|nullptr|0)\b", cond) or "NULL" in cond or "nullptr" in cond
            updates = [f"{var} = {var}->next;"] if pointer else [f"{var}++;", f"{var}--;"]
            for update in updates:
                if braced:
                    at = body.start + t[body.start:body.end].rfind("}")
                    code = splice(prog.code, at, at, f" {update} ")
                else:
                    code = splice(prog.code, body.start, body.end, "{ " + prog.code[body.start:body.end] + f" {update} }}")
                out.append(Repair(cls, "while_add_update", lp.line, "", update, code))
    return out[:MAX_CANDIDATES]


EXTRA_GENERATORS = {
    "CPP_OFF_BY_ONE": extra_off_by_one,
    "CPP_ARRAY_BOUNDS": extra_array_bounds,
    "CPP_UNINITIALIZED_VAR": extra_uninitialized,
    "CPP_RANGE_CHECK": extra_range_check,
    "CPP_STALE_EXIT": extra_stale_exit,
}
