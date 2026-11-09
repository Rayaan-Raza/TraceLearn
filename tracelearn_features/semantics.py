"""Deterministic source-semantics features for SYNTHETIC and CODESTREAM rows.

These are *source* signals, never label metadata. They are intentionally
regex-level (no compiler / CPG dependency) so every lane can compute them from
the code it already carries. The block is left NaN when no source is available
(PROGPEDIA), preserving the §6 null policy.

The 15 features mirror the audit prototype that improved grouped-CV macro-F1
from 0.2025 (static+warnings) to 0.2324 (static+warnings+semantics) and test
macro-F1 over the seven present classes from 0.420 to 0.493.
"""

from __future__ import annotations

import re

_COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_FUNC_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{")


def _strip_noise(source: str) -> str:
    """Remove comments and string/char literals before counting signals."""
    return _STRING_RE.sub('""', _COMMENT_RE.sub("", source))


def _has_recursion(source: str) -> int:
    """1 when a function body calls the function's own name."""
    for match in _FUNC_RE.finditer(source):
        name = match.group(1)
        body_start = match.end()
        depth = 1
        i = body_start
        while i < len(source) and depth:
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        body = source[body_start:i]
        if re.search(r"\b" + re.escape(name) + r"\s*\(", body):
            return 1
    return 0


# ---------------------------------------------------------------- surface patterns
# Ten more deterministic source signals, each a bug the real CodeStream failures
# show again and again (see docs/6-nov.md): chained comparisons, an index equal to
# the length, scanf without &, a program that reads nothing, prompt text in the
# output, printf given an address, constant integer division, comparing a char
# with a string literal, an empty loop/if body, and a nested loop that reuses its
# outer loop variable. Source only; label metadata is never read.

_TEMPLATE_RE = re.compile(r"\b(?:std\s*::\s*)?\w+\s*<[^<>;(){}=]*>")
_CHAIN_RE = re.compile(r"[\w.\]\)]\s*(?:<=|>=|<|>)\s*[\w.\[\]]+\s*(?:<=|>=|<|>)\s*[\w.\[]")
_TYPE_TAIL_RE = re.compile(
    r"\b(?:int|long|short|double|float|char|bool|unsigned|signed|size_t|ll|string)\s+(?:long\s+)?$")
_BOUND_NAMES = r"(?:n|N|len|length|size|sz|cnt|count|m|k)"
_INPUT_RE = re.compile(r"\b(?:cin|scanf|sscanf|fscanf|getline|fgets|gets|getchar|read)\b")
_PROMPT_RE = re.compile(
    r"(?:cout|printf|puts)\b[^;]*\"[^\"]*\b(?:enter|input|please|type|give)\b[^\"]*\"", re.IGNORECASE)
_INT_DIV_RE = re.compile(r"(?<![\w.])\d+\s*/\s*\d+(?![\w.])")
_CHAR_STR_CMP_RE = re.compile(r"(?:==|!=|<=|>=|<|>)\s*\"[^\"\\]\"")
_PRINTF_ADDR_RE = re.compile(r"printf\s*\(\s*\"[^\"]*\"\s*,[^;]*&\s*\w+")
_SCANF_RE = re.compile(r"scanf\s*\(\s*\"([^\"]*)\"\s*((?:,[^;]*)?)\)\s*;")
_HEAD_RE = re.compile(r"\b(if|while|for)\s*\(")


def _balanced(text: str, open_at: int, opener: str = "(", closer: str = ")") -> int:
    """Index just past the bracket that closes the one at `open_at`, or -1."""
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == opener:
            depth += 1
        elif text[i] == closer:
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def _conditions(code: str) -> list[tuple[str, str, int]]:
    """(keyword, parenthesised condition text, index after the closing paren)."""
    out = []
    for m in _HEAD_RE.finditer(code):
        end = _balanced(code, m.end() - 1)
        if end > 0:
            out.append((m.group(1), code[m.end():end - 1], end))
    return out


def _chained_compare(code: str) -> int:
    plain = _TEMPLATE_RE.sub("T", code)
    return sum(1 for _kw, cond, _end in _conditions(plain) if _CHAIN_RE.search(cond))


def _index_is_bound(code: str) -> int:
    n = 0
    pattern = r"(\w+)\s*\[\s*(?:" + _BOUND_NAMES + r"|\w+\s*\.\s*(?:size|length)\s*\(\s*\))\s*\]"
    for m in re.finditer(pattern, code):
        if not _TYPE_TAIL_RE.search(code[:m.start()]):      # `int a[n];` declares, `a[n]` reads
            n += 1
    return n


def _scanf_without_amp(code: str) -> int:
    n = 0
    for m in _SCANF_RE.finditer(code):
        fmt, rest = m.group(1), m.group(2)
        if "%s" in fmt or "%[" in fmt:
            continue
        args, depth, cur = [], 0, ""
        for ch in rest.lstrip(","):
            depth += ch in "([{"
            depth -= ch in ")]}"
            if ch == "," and depth == 0:
                args.append(cur.strip())
                cur = ""
            else:
                cur += ch
        args.append(cur.strip())
        n += sum(1 for a in args if re.fullmatch(r"[A-Za-z_]\w*", a))
    return n


def _empty_body_statement(code: str) -> int:
    n = 0
    for kw, _cond, end in _conditions(code):
        if re.match(r"\s*;", code[end:]):
            if kw == "while" and re.search(r"\}\s*$", code[:code.rfind(kw, 0, end)]):
                continue                                      # closes a do { } while (...);
            n += 1
    return n


def _loop_var_reused(code: str) -> int:
    n = 0
    for m in re.finditer(r"\bfor\s*\(\s*(\w+)\s*=", code):          # init without a declaration
        var = m.group(1)
        head_end = _balanced(code, code.index("(", m.start()))
        brace = code.find("{", head_end) if head_end > 0 else -1
        if brace < 0 or code[head_end:brace].strip():
            continue
        body_end = _balanced(code, brace, "{", "}")
        if body_end > 0 and re.search(r"\bfor\s*\(\s*" + re.escape(var) + r"\s*=", code[brace:body_end]):
            n += 1
    return n


def _loop_bodies(code: str):
    """(kind, init, cond, body) for each for/while loop whose braces can be matched."""
    for m in re.finditer(r"\b(for|while)\s*\(", code):
        end = _balanced(code, m.end() - 1)
        if end < 0:
            continue
        head = code[m.end():end - 1]
        parts = head.split(";") if m.group(1) == "for" else ["", head, ""]
        if len(parts) != 3:
            continue
        rest = code[end:].lstrip()
        if rest.startswith("{"):
            start = end + (len(code[end:]) - len(rest))
            stop = _balanced(code, start, "{", "}")
            body = code[start:stop] if stop > 0 else rest[:200]
        else:
            body = re.split(r";", rest, maxsplit=1)[0]
        yield m.group(1), parts[0], parts[1], body


def _plus1_index_in_full_loop(code: str) -> int:
    """`a[i + 1]` inside a loop that runs i all the way to n: reads one past the end."""
    n = 0
    for _kind, _init, cond, body in _loop_bodies(code):
        m = re.match(r"\s*(\w+)\s*(<|<=)\s*(.+?)\s*$", cond)
        if not m or re.search(r"-\s*1\s*$|-\s*1\s*\)", m.group(3)) or m.group(2) == "<=" and "-" in m.group(3):
            continue
        if re.search(r"\[\s*" + re.escape(m.group(1)) + r"\s*\+\s*1\s*\]", body):
            n += 1
    return n


def _minus1_index_from_zero(code: str) -> int:
    """`a[i - 1]` inside a loop that starts i at 0: reads before the start."""
    n = 0
    for _kind, init, _cond, body in _loop_bodies(code):
        m = re.search(r"(\w+)\s*=\s*0\s*$", init)
        if m and re.search(r"\[\s*" + re.escape(m.group(1)) + r"\s*-\s*1\s*\]", body):
            n += 1
    return n


def _surface_patterns(source: str) -> dict[str, int]:
    code = _COMMENT_RE.sub("", source)                        # strings kept: prompts and formats need them
    nostr = _strip_noise(source)
    return {
        "chained_compare": _chained_compare(nostr),
        "index_is_bound": _index_is_bound(nostr),
        "scanf_no_amp": _scanf_without_amp(code),
        "no_input_read": int(not _INPUT_RE.search(nostr)),
        "prompt_text": len(_PROMPT_RE.findall(code)),
        "printf_addr_arg": len(_PRINTF_ADDR_RE.findall(code)),
        "int_div_literals": len(_INT_DIV_RE.findall(nostr)),
        "char_vs_string_cmp": len(_CHAR_STR_CMP_RE.findall(code)),
        "empty_body_stmt": _empty_body_statement(nostr),
        "loop_var_reused": _loop_var_reused(nostr),
        "plus1_index_in_full_loop": _plus1_index_in_full_loop(nostr),
        "minus1_index_from_zero": _minus1_index_from_zero(nostr),
    }


def extract_semantics(source: str) -> dict[str, int]:
    """Return the canonical ``semantics`` block for a C/C++ source string.

    An empty/whitespace source returns ``{}`` so the merge leaves the block
    absent (NaN), rather than fabricating a row of zeros.
    """
    if not isinstance(source, str) or not source.strip():
        return {}

    s = _strip_noise(source)

    def count(pattern: str) -> int:
        return len(re.findall(pattern, s))

    def flag(pattern: str) -> int:
        return int(bool(re.search(pattern, s)))

    return {
        "assign_in_cond": flag(
            r"\b(if|while)\s*\([^)]*(?<![=!<>+\-*/%&|^])=(?!=)[^)]*\)"
        ),
        "recursion": _has_recursion(s),
        "increment": count(r"\+\+"),
        "decrement": count(r"(?<!-)\-\-(?!>)"),
        "idx_minus1": flag(r"\[\s*[A-Za-z_]\w*\s*-\s*1\s*\]"),
        "idx_plus1": flag(r"\[\s*[A-Za-z_]\w*\s*\+\s*1\s*\]"),
        "if_gt": flag(r"if\s*\([^)]*(?<![<>=!])>\s*[^=]"),
        "if_ge": flag(r"if\s*\([^)]*>= "),
        "if_lt": flag(r"if\s*\([^)]*(?<![<>=!])<\s*[^=]"),
        "if_le": flag(r"if\s*\([^)]*<= "),
        "loop_lt": flag(r"(for|while)\s*\([^)]*(?<![<>=!])<\s*[^=]"),
        "loop_le": flag(r"(for|while)\s*\([^)]*<= "),
        "init_zero": flag(r"\bint\s+\w+\s*=\s*0\s*;"),
        "return_minus1": flag(r"return\s+[^;]*-\s*1"),
        "base_case": flag(r"if\s*\(\s*\w+\s*(<=?|==)\s*[01]\s*\)"),
        **_surface_patterns(source),
    }
