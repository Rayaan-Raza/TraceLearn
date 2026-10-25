"""Source-level proxy for CPG (Code Property Graph) features.

Computes a subset of the canonical ``cpg`` schema block from C/C++ source
using regex heuristics — no compiler or graph tool required. Intended for
SYNTHETIC and CODESTREAM rows where lane-supplied CPG evidence is absent.

Fields this module can fill (rest remain NaN per §6 null policy):
  function_count          — function definition count
  loop_count              — for/while statement count
  assign_in_condition_count — assignment-as-truth-value occurrences
  comparison_count        — comparison operator count (==, !=, <, >, <=, >=)
  decrement_in_loop_count — decrement operators (-- / -=1) in loop bodies
  unguarded_recursion_count — self-recursive calls lacking an early-exit guard

Fields left NaN (require graph analysis):
  node_count, edge_count, max_depth, ast_ref_similarity,
  array_write_oob_count, use_before_init_count,
  loop_cond_var_unassigned_count, assign_feeds_output_count
"""

from __future__ import annotations

import re

_COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_FUNC_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\([^;{}()]*\)\s*\{")
_LOOP_RE = re.compile(r"\b(for|while)\s*\(")

# Simple brace-body extractor (handles one nesting level per call)
def _body(source: str, open_pos: int) -> str:
    depth, i = 0, open_pos
    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[open_pos:i + 1]
        i += 1
    return source[open_pos:]


def _strip_noise(source: str) -> str:
    return _STRING_RE.sub('""', _COMMENT_RE.sub("", source))


def extract_cpg_source(source: str) -> dict[str, int]:
    """Return fillable CPG fields for *source*.

    Returns ``{}`` for empty/whitespace source so the caller can leave the
    block NaN rather than fabricating zeros.
    """
    if not isinstance(source, str) or not source.strip():
        return {}

    s = _strip_noise(source)

    # function_count: definitions (name followed by param list and body open)
    function_count = len(_FUNC_RE.findall(s))

    # loop_count
    loop_count = len(_LOOP_RE.findall(s))

    # assign_in_condition_count — flag(1) or count for each if/while with assign
    assign_in_cond = len(re.findall(
        r"\b(if|while)\s*\([^)]*(?<![=!<>+\-*/%&|^])=(?!=)[^)]*\)", s
    ))

    # comparison_count — all six comparison operators
    comparison_count = len(re.findall(r"==|!=|<=|>=|(?<![<>!])>(?!=)|(?<![<>!])<(?!=)", s))

    # decrement_in_loop_count: look for `--` inside loop bodies
    # _LOOP_RE does not consume `{`, so find first `{` after the loop header
    decrement_in_loop = 0
    for m in _LOOP_RE.finditer(s):
        brace = s.find("{", m.end())
        if brace == -1:
            continue
        body = _body(s, brace)
        decrement_in_loop += len(re.findall(r"(?<!-)\-\-(?!>)", body))

    # unguarded_recursion_count: recursive calls without an immediate base-case guard
    # _FUNC_RE consumes the `{`, so back up one character to find it
    unguarded = 0
    for m in _FUNC_RE.finditer(s):
        name = m.group(1)
        brace = m.end() - 1  # pattern ends with \{, so last char of match is {
        body = _body(s, brace)
        recursive_calls = re.findall(r"\b" + re.escape(name) + r"\s*\(", body)
        if not recursive_calls:
            continue
        # "unguarded" = recursive call exists but no base-case if before it
        has_base_guard = bool(re.search(
            r"if\s*\(\s*\w+\s*(<=?|==|>=?)\s*[01]\s*\)", body
        ))
        unguarded += 0 if has_base_guard else len(recursive_calls)

    return {
        "function_count": function_count,
        "loop_count": loop_count,
        "assign_in_condition_count": assign_in_cond,
        "comparison_count": comparison_count,
        "decrement_in_loop_count": decrement_in_loop,
        "unguarded_recursion_count": unguarded,
    }
