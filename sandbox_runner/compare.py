"""Compare a program's output with the expected output.

``status`` is one of ``pass`` (exact after trimming trailing whitespace on
every line and trailing blank lines), ``presentation`` (same tokens, different
whitespace) or ``wrong``. The extra diff fields are cheap evidence the
labeling functions use (±1 numeric deltas, reversed order, prefix length).
"""

from __future__ import annotations


def _lines(s: str) -> list[str]:
    out = [ln.rstrip() for ln in s.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while out and out[-1] == "":
        out.pop()
    return out


def _num(tok: str):
    try:
        if any(c in tok for c in ".eE"):
            return float(tok)
        return int(tok)
    except ValueError:
        return None


def compare_output(actual: str, expected: str) -> dict:
    a_lines, e_lines = _lines(actual), _lines(expected)
    a_tok, e_tok = actual.split(), expected.split()
    if a_lines == e_lines:
        status = "pass"
    elif a_tok == e_tok:
        status = "presentation"
    else:
        status = "wrong"
    res = {"status": status}
    if status == "pass":
        return res

    # first differing line (1-based)
    first = None
    for i in range(max(len(a_lines), len(e_lines))):
        al = a_lines[i] if i < len(a_lines) else None
        el = e_lines[i] if i < len(e_lines) else None
        if al != el:
            first = i + 1
            break
    res["first_diff_line"] = first
    res["actual_tokens"] = len(a_tok)
    res["expected_tokens"] = len(e_tok)

    prefix = 0
    for x, y in zip(a_tok, e_tok):
        if x != y:
            break
        prefix += 1
    res["prefix_tokens"] = prefix
    res["is_prefix_of_expected"] = len(a_tok) < len(e_tok) and a_tok == e_tok[: len(a_tok)]
    res["expected_is_prefix"] = len(e_tok) < len(a_tok) and e_tok == a_tok[: len(e_tok)]
    res["is_suffix_of_expected"] = 0 < len(a_tok) < len(e_tok) and a_tok == e_tok[-len(a_tok):]
    res["expected_is_suffix"] = 0 < len(e_tok) < len(a_tok) and e_tok == a_tok[-len(e_tok):]
    res["empty_output"] = len(a_tok) == 0
    res["token_count_delta"] = len(a_tok) - len(e_tok)

    # order evidence (class 8)
    res["reversed_tokens"] = len(a_tok) > 1 and a_tok == e_tok[::-1] and a_tok != e_tok
    res["reversed_lines"] = len(a_lines) > 1 and a_lines == e_lines[::-1] and a_lines != e_lines
    res["same_multiset"] = len(a_tok) > 1 and sorted(a_tok) == sorted(e_tok)

    # numeric deltas on aligned tokens (classes 1, 2, 5)
    deltas = []
    if len(a_tok) == len(e_tok):
        for x, y in zip(a_tok, e_tok):
            if x == y:
                continue
            nx, ny = _num(x), _num(y)
            if nx is None or ny is None:
                deltas = None
                break
            deltas.append(nx - ny)
    else:
        deltas = None
    if deltas is not None and deltas:
        res["numeric_deltas"] = deltas[:20]
        res["all_deltas_pm1"] = all(abs(d) == 1 for d in deltas)
        res["max_abs_delta"] = max(abs(d) for d in deltas)
        res["negative_where_positive"] = any(
            _num(x) is not None and _num(y) is not None and _num(x) < 0 <= _num(y)
            for x, y in zip(a_tok, e_tok)
        )
    else:
        res["numeric_deltas"] = None
        res["all_deltas_pm1"] = False
    return res
