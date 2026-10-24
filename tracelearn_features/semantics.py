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
    }
