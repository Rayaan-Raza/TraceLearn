"""Light-weight static views of C/C++ source for Lane B labeling functions.

No compiler front-end: student code is often broken, and these signatures
only need loop headers, conditions, declarations and functions. The scanner
blanks comments, string and char literals *in place* (same length), so every
offset found in the blanked text is valid in the original code and repairs
can be spliced back without re-formatting the submission.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TYPES = r"(?:unsigned\s+|signed\s+|const\s+|static\s+)*(?:long\s+long|long\s+double|long|short|int|char|float|double|bool|size_t|unsigned)"


def blank(code: str) -> str:
    """Replace comment / string / char-literal bodies with spaces, keeping offsets."""
    out = list(code)
    i, n = 0, len(code)
    while i < n:
        c = code[i]
        nx = code[i + 1] if i + 1 < n else ""
        if c == "/" and nx == "/":
            j = code.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif c == "/" and nx == "*":
            j = code.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif c in "\"'":
            q = c
            j = i + 1
            while j < n and code[j] != q and code[j] != "\n":
                j += 2 if code[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = j + 1
        elif c == "#":
            # preprocessor line: keep it (array sizes may come from #define)
            j = code.find("\n", i)
            i = n if j < 0 else j
        else:
            i += 1
    return "".join(out)


def line_of(code: str, offset: int) -> int:
    return code.count("\n", 0, offset) + 1


def match_paren(text: str, open_idx: int, o: str = "(", c: str = ")") -> int:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == o:
            depth += 1
        elif text[i] == c:
            depth -= 1
            if depth == 0:
                return i
    return -1


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def statement_end(text: str, i: int) -> int:
    """End offset (exclusive) of the statement starting at ``i`` (block or simple)."""
    i = _skip_ws(text, i)
    if i < len(text) and text[i] == "{":
        j = match_paren(text, i, "{", "}")
        return len(text) if j < 0 else j + 1
    m = re.match(r"(for|while|if|switch)\b", text[i:])
    if m:
        p = text.find("(", i)
        j = match_paren(text, p)
        if j < 0:
            return len(text)
        end = statement_end(text, j + 1)
        if m.group(1) == "if":
            k = _skip_ws(text, end)
            if text.startswith("else", k) and not text[k + 4:k + 5].isalnum():
                end = statement_end(text, k + 4)
        return end
    if text.startswith("do", i) and not text[i + 2:i + 3].isalnum():
        end = statement_end(text, i + 2)
        k = text.find(";", end)
        return len(text) if k < 0 else k + 1
    depth = 0
    for k in range(i, len(text)):
        ch = text[k]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth < 0:
                return k
        elif ch == ";" and depth == 0:
            return k + 1
    return len(text)


@dataclass
class Span:
    start: int
    end: int

    def text(self, code: str) -> str:
        return code[self.start:self.end]


@dataclass
class Loop:
    kind: str  # for | while | do
    keyword: int
    line: int
    init: Span | None
    cond: Span | None
    step: Span | None
    body: Span
    var: str | None = None


@dataclass
class Cond:
    kind: str  # if | while | for | ternary
    span: Span
    line: int


@dataclass
class Function:
    name: str
    params: list[str]
    body: Span
    line: int
    return_type: str


@dataclass
class Decl:
    var: str
    type: str
    span: Span  # the declarator, e.g. "s" in "int s;"
    line: int
    initialized: bool
    array_size: str | None = None
    array_size_span: Span | None = None
    in_function: str | None = None


@dataclass
class Program:
    code: str
    text: str
    loops: list[Loop] = field(default_factory=list)
    conds: list[Cond] = field(default_factory=list)
    functions: list[Function] = field(default_factory=list)
    decls: list[Decl] = field(default_factory=list)
    defines: dict = field(default_factory=dict)


_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "else", "do", "case"}


def _loop_var(init: str, cond: str) -> str | None:
    m = re.search(r"([A-Za-z_]\w*)\s*=(?!=)", init or "")
    if m:
        return m.group(1)
    m = re.match(r"\s*([A-Za-z_]\w*)", cond or "")
    return m.group(1) if m else None


def parse(code: str) -> Program:
    text = blank(code)
    prog = Program(code=code, text=text)
    for m in re.finditer(r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+(\d+)\b", code, re.M):
        prog.defines[m.group(1)] = int(m.group(2))
    for m in re.finditer(r"\bconst\s+(?:int|long\s+long|long|size_t|unsigned)\s+([A-Za-z_]\w*)\s*=\s*(\d+)", text):
        prog.defines.setdefault(m.group(1), int(m.group(2)))

    for m in re.finditer(r"\b(for|while)\s*\(", text):
        kw = m.group(1)
        p = m.end() - 1
        q = match_paren(text, p)
        if q < 0:
            continue
        inner = text[p + 1:q]
        if kw == "for":
            parts, depth, last = [], 0, p + 1
            for k in range(p + 1, q):
                ch = text[k]
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                elif ch == ";" and depth == 0:
                    parts.append(Span(last, k))
                    last = k + 1
            parts.append(Span(last, q))
            if len(parts) != 3:
                continue  # range-for or broken header
            body_end = statement_end(text, q + 1)
            init, cond, step = parts
            loop = Loop("for", m.start(), line_of(code, m.start()), init, cond, step,
                        Span(q + 1, body_end))
            loop.var = _loop_var(init.text(text), cond.text(text))
            prog.loops.append(loop)
            prog.conds.append(Cond("for", cond, line_of(code, cond.start)))
        else:
            # skip the while of a do-while (preceded by '}')
            before = text[:m.start()].rstrip()
            k = _skip_ws(text, q + 1)
            if before.endswith("}") and k < len(text) and text[k] == ";":
                prog.conds.append(Cond("while", Span(p + 1, q), line_of(code, p)))
                continue
            body_end = statement_end(text, q + 1)
            loop = Loop("while", m.start(), line_of(code, m.start()), None, Span(p + 1, q), None,
                        Span(q + 1, body_end))
            loop.var = _loop_var("", inner)
            prog.loops.append(loop)
            prog.conds.append(Cond("while", Span(p + 1, q), line_of(code, p)))

    for m in re.finditer(r"\bif\s*\(", text):
        p = m.end() - 1
        q = match_paren(text, p)
        if q > 0:
            prog.conds.append(Cond("if", Span(p + 1, q), line_of(code, p)))

    # functions: type name(params) {  at brace depth 0
    depth = 0
    i = 0
    fn_re = re.compile(r"([A-Za-z_][\w:<>,\s\*&]*?)\b([A-Za-z_]\w*)\s*\(")
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0 and (ch.isalpha() or ch == "_"):
            m = fn_re.match(text, i)
            if m and m.group(2) not in _KEYWORDS:
                p = m.end() - 1
                q = match_paren(text, p)
                if q > 0:
                    k = _skip_ws(text, q + 1)
                    while text.startswith("const", k):
                        k = _skip_ws(text, k + 5)
                    if k < len(text) and text[k] == "{":
                        e = match_paren(text, k, "{", "}")
                        if e > 0:
                            params = [x.strip() for x in text[p + 1:q].split(",") if x.strip()]
                            pnames = []
                            for x in params:
                                pm = re.search(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*$", x)
                                if pm and x.strip() != "void":
                                    pnames.append(pm.group(1))
                            prog.functions.append(Function(m.group(2), pnames, Span(k, e + 1),
                                                           line_of(code, m.start(2)),
                                                           m.group(1).strip()))
                            i = e + 1
                            continue
            # jump to end of this identifier
            j = i
            while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                j += 1
            i = j
            continue
        i += 1

    # declarations
    for m in re.finditer(r"(?<![\w.>])(" + _TYPES + r")\s+([^;(){}]*?);", text):
        typ = re.sub(r"\s+", " ", m.group(1)).strip()
        decl_list = m.group(2)
        base = m.start(2)
        # split on top-level commas
        depth, last = 0, 0
        pieces = []
        for k, ch in enumerate(decl_list):
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                pieces.append((last, k))
                last = k + 1
        pieces.append((last, len(decl_list)))
        fn = next((f.name for f in prog.functions if f.body.start <= m.start() < f.body.end), None)
        for a, b in pieces:
            piece = decl_list[a:b]
            dm = re.match(r"\s*\**\s*&?\s*([A-Za-z_]\w*)\s*(\[\s*([^\]]*)\])?\s*(=)?", piece)
            if not dm:
                continue
            name = dm.group(1)
            if name in _KEYWORDS or name in {"main"}:
                continue
            arr = dm.group(3).strip() if dm.group(2) else None
            arr_span = None
            if dm.group(2):
                lb = base + a + piece.index("[")
                arr_span = Span(lb + 1, base + a + piece.index("]"))
            off = base + a + dm.start(1)
            prog.decls.append(Decl(name, typ, Span(off, off + len(name)), line_of(code, off),
                                   initialized=bool(dm.group(4)) or "{" in piece,
                                   array_size=arr, array_size_span=arr_span, in_function=fn))
    return prog


# ----------------------------------------------------------- small helpers --

CMP_RE = re.compile(r"(<=|>=|==|!=|<(?![<=])|>(?![>=]))")


def comparisons(text: str, span: Span):
    """Yield (op, abs_start, abs_end) for comparison operators inside ``span``."""
    seg = text[span.start:span.end]
    for m in CMP_RE.finditer(seg):
        a = span.start + m.start()
        # skip << >> stream / shift operators and templates like vector<int>
        if seg[m.start():m.start() + 2] in ("<<", ">>"):
            continue
        prev = seg[max(0, m.start() - 1):m.start()]
        if prev in ("<", ">", "-"):
            continue
        yield m.group(1), a, a + len(m.group(1))


def assigned_vars(text: str, span: Span) -> set[str]:
    """Variables written inside ``span`` (=, op=, ++, --, scanf/cin targets)."""
    seg = text[span.start:span.end]
    out = set()
    for m in re.finditer(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*(?:[+\-*/%&|^]|<<|>>)?=(?!=)", seg):
        out.add(m.group(1))
    for m in re.finditer(r"(?:\+\+|--)\s*([A-Za-z_]\w*)|([A-Za-z_]\w*)\s*(?:\+\+|--)", seg):
        out.add(m.group(1) or m.group(2))
    for m in re.finditer(r"&\s*([A-Za-z_]\w*)", seg):  # scanf(&x), f(&x)
        out.add(m.group(1))
    for m in re.finditer(r">>\s*([A-Za-z_]\w*)", seg):  # cin >> x
        out.add(m.group(1))
    return out


def identifiers(text: str) -> set[str]:
    return set(re.findall(r"\b[A-Za-z_]\w*\b", text)) - _KEYWORDS


def splice(code: str, start: int, end: int, new: str) -> str:
    return code[:start] + new + code[end:]
