"""`tracelearn_features` v0 extractor — the Week-0 fixed interface (§5, §6).

Design rules enforced here and by tests/test_extract_features.py:

- Returns every schema block, in schema order (row shape §6).
- `static` is always computed from `source`; malformed `source` degrades to
  zeros, never raises.
- Omitted evidence ⇒ the whole block is NaN with its `available` gate False —
  never 0 (§6 null policy: null/NaN = "source cannot provide it").
- Malformed evidence degrades to NaN for the fields it should have filled;
  this function never raises, so a lane can't be blocked by a parser bug.
- `meta` is never produced; lanes copy it verbatim from their rows.

Version pin: the signature is documented verbatim in FEATURE_SCHEMA.md and
does not change until the post-G3 migration window (R1).
"""

from __future__ import annotations

import math
import re
from typing import Any

from tracelearn_features.schema import FEATURE_BLOCKS, WARNING_FLAG_OF
from tracelearn_features.semantics import extract_semantics

_NAN = float("nan")


def _nan_block(block: str) -> dict[str, Any]:
    """A full schema block of NaN with the availability gate False.

    Missing bools are NaN too (not None, never False): in the float32 matrix
    NaN means "source cannot provide it" — a missing `asan_error=False` would
    silently claim "ran, no error" (§6 null policy).
    """
    feats: dict[str, Any] = {}
    for short in FEATURE_BLOCKS[block]:
        if short == "available":
            feats[short] = False
        else:
            feats[short] = _NAN
    return feats


def _int_nan() -> float:
    """NaN in the place of a nullable int (CSV/float matrix reads it as NaN)."""
    return _NAN


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and not math.isnan(value):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        f = float(value)
        return None if math.isnan(f) else f
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and math.isnan(value):
            return None
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "yes", "1"):
            return True
        if low in ("false", "no", "0"):
            return False
    return None


# --------------------------------------------------------------------- static

_C_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_TOKEN_RE = re.compile(r"[A-Za-z_]\w+|\d+\.?\d*|[{}()\[\];,]|[+\-*/%<>=!&|^~?:]+|\S")
_NUMERIC_RE = re.compile(r"\b\d+\.?\d*\b")
_STRING_RE = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'")


def _compute_static(source: str, language: str) -> dict[str, Any]:
    out = _nan_block("static")
    try:
        text = source if isinstance(source, str) else ""
        lines = text.split("\n")
        stripped = _C_COMMENT_RE.sub("", text)
        code_lines = [ln for ln in lines if ln.strip()]
        # comment-only lines: blank after removing comments
        comment_only = sum(
            1
            for ln in lines
            if ln.strip() and not _C_COMMENT_RE.sub("", ln).strip()
        )
        tokens = _TOKEN_RE.findall(stripped)
        unique = len(set(tokens))
        max_indent = 0
        for ln in lines:
            lead = len(ln) - len(ln.lstrip(" \t"))
            if ln.strip():
                max_indent = max(max_indent, lead)
        nonblank = [ln for ln in code_lines if _C_COMMENT_RE.sub("", ln).strip()]
        lengths = [len(ln) for ln in nonblank] or [0]

        def count(pattern: str) -> int:
            return len(re.findall(pattern, stripped))

        out["loc"] = len(lines) if text else 0
        out["sloc"] = len(nonblank)
        out["comment_lines"] = comment_only
        out["max_indent_depth"] = max_indent
        out["function_count"] = count(r"\b[A-Za-z_]\w*\s*\([^;]*\)\s*\{")
        out["loop_count"] = count(r"\b(for|while|do)\b")
        out["if_count"] = count(r"\bif\s*\(")
        out["switch_count"] = count(r"\bswitch\s*\(")
        out["return_count"] = count(r"\breturn\b")
        out["array_decl_count"] = count(r"\w+\s+\w+\s*\[\s*\d*\s*\]")
        out["string_literal_count"] = len(_STRING_RE.findall(stripped))
        out["numeric_literal_count"] = len(_NUMERIC_RE.findall(stripped))
        out["token_count"] = len(tokens)
        out["unique_token_ratio"] = (unique / len(tokens)) if tokens else 0.0
        out["avg_line_length"] = sum(lengths) / len(lengths)
        out["max_line_length"] = max(len(ln) for ln in lines) if lines else 0
        out["include_count"] = count(r"^\s*#\s*include\b") or len(
            re.findall(r"^\s*#\s*include\b", text, re.MULTILINE)
        )
        low = stripped.lower()
        out["uses_stdio"] = bool(
            re.search(
                r"<stdio\.h>|<cstdio>|<iostream>|<bits/stdc\+\+\.h>", low
            )
        )
        out["uses_malloc_free"] = bool(re.search(r"\b(malloc|calloc|realloc|free)\s*\(", low))
        out["uses_vector"] = bool(re.search(r"\bstd\s*::\s*vector\b|\bvector\s*<", low))
        if language.lower() in ("java", "python", "c", "cpp", "c++"):
            pass  # language accepted as-is; static extraction is C-family tuned
    except Exception:
        # degrade to zeros rather than raise (§5: lanes are never blocked)
        for short, ftype in FEATURE_BLOCKS["static"].items():
            out[short] = 0.0 if ftype == "float" else (0 if ftype == "int" else False)
    return out


# ------------------------------------------------------------------- warnings

def _compute_warnings(evidence: Any) -> dict[str, Any]:
    out = _nan_block("warnings")
    if evidence is None:
        return out
    try:
        if not isinstance(evidence, (list, tuple)):
            raise TypeError("warnings evidence must be a list")
        out["available"] = True
        counts: dict[str, int] = {}
        other = 0
        total = 0
        flag_to_id = {flag: name for name, flag in WARNING_FLAG_OF.items()}
        for item in evidence:
            if isinstance(item, dict):
                flag = str(item.get("flag") or item.get("warning") or "")
                n = _as_int(item.get("count")) or 0
            elif isinstance(item, str):
                flag, n = item, 1
            else:
                continue
            if n <= 0:
                continue
            total += n
            wid = flag_to_id.get(flag)
            if wid is None:
                other += n
            else:
                short = wid.split(".", 1)[1]
                counts[short] = counts.get(short, 0) + n
        out["total"] = total
        out["other"] = other
        for short in FEATURE_BLOCKS["warnings"]:
            if short in ("available", "total", "other"):
                continue
            out[short] = counts.get(short, 0)
    except Exception:
        return _nan_block("warnings")
    return out


# -------------------------------------------------------------------- runtime

_ASAN_PATTERNS = {
    "asan_heap_buffer_overflow": r"heap-buffer-overflow",
    "asan_stack_buffer_overflow": r"stack-buffer-overflow",
}


def _compute_runtime(evidence: Any) -> dict[str, Any]:
    out = _nan_block("runtime")
    if evidence is None:
        return out
    try:
        if not isinstance(evidence, dict):
            raise TypeError("runtime evidence must be a dict")
        out["available"] = True
        crashed = _as_bool(evidence.get("crashed"))
        timed_out = _as_bool(evidence.get("timed_out"))
        out["crashed"] = crashed if crashed is not None else False
        out["timed_out"] = timed_out if timed_out is not None else False
        sig = _as_int(evidence.get("signal"))
        out["signal"] = sig if sig is not None else _NAN
        code = _as_int(evidence.get("exit_code"))
        out["exit_code"] = code if code is not None else _NAN
        dur = _as_float(evidence.get("duration_s"))
        out["duration_s"] = dur if dur is not None else _NAN

        asan = evidence.get("asan_reports") or []
        ubsan = evidence.get("ubsan_reports") or []
        valgrind = evidence.get("valgrind_reports") or []
        asan_text = " ".join(asan) if isinstance(asan, (list, tuple)) else str(asan)
        ubsan_text = " ".join(ubsan) if isinstance(ubsan, (list, tuple)) else str(ubsan)
        vg_text = " ".join(valgrind) if isinstance(valgrind, (list, tuple)) else str(valgrind)

        out["asan_error"] = bool(asan_text.strip())
        for short, pattern in _ASAN_PATTERNS.items():
            out[short] = bool(re.search(pattern, asan_text, re.IGNORECASE))
        out["ubsan_error"] = bool(ubsan_text.strip())
        out["ubsan_signed_overflow"] = bool(
            re.search(r"signed integer overflow|signed overflow", ubsan_text, re.IGNORECASE)
        )
        # DEADLYSIGNAL is printed for ANY fatal signal (SEGV, ABRT, ...) —
        # matching it here would make every null deref look like class-6
        # evidence. Only the explicit stack-overflow report counts.
        out["stack_overflow"] = bool(
            re.search(r"stack[- ]overflow", asan_text, re.IGNORECASE)
        ) or bool(re.search(r"stack[- ]overflow", vg_text, re.IGNORECASE))
        out["valgrind_error"] = bool(vg_text.strip())
        out["valgrind_uninit_value"] = bool(
            re.search(
                r"uninitiali[sz]ed|depends on uninitiali[sz]ed value",
                vg_text,
                re.IGNORECASE,
            )
        )
    except Exception:
        return _nan_block("runtime")
    return out


# ---------------------------------------------------------------------- tests

def _compute_tests(evidence: Any) -> dict[str, Any]:
    out = _nan_block("tests")
    if evidence is None:
        return out
    try:
        if not isinstance(evidence, dict):
            raise TypeError("tests evidence must be a dict")
        out["available"] = True
        results = evidence.get("results")
        if not isinstance(results, (list, tuple)):
            total = _as_int(evidence.get("total"))
            passed = _as_int(evidence.get("passed"))
            out["total"] = total if total is not None else _NAN
            out["passed"] = passed if passed is not None else _NAN
            failed = _as_int(evidence.get("failed"))
            out["failed"] = failed if failed is not None else _NAN
            if total:
                out["pass_rate"] = (passed or 0) / total
            return out

        total = len(results)
        passed = 0
        failed = 0
        wa = 0
        re_count = 0
        to = 0
        first_fail = -1
        diff: float = _NAN
        boundary = 0
        for idx, res in enumerate(results):
            ok = _as_bool(res.get("ok")) if isinstance(res, dict) else None
            if ok:
                passed += 1
                continue
            failed += 1
            if first_fail < 0:
                first_fail = idx
                expected = res.get("expected") if isinstance(res, dict) else None
                actual = res.get("actual") if isinstance(res, dict) else None
                exp_f = _as_float(expected)
                act_f = _as_float(actual)
                if exp_f is not None and act_f is not None:
                    diff = act_f - exp_f
                else:
                    diff = _NAN
                if _as_bool(res.get("boundary")):
                    boundary += 1
            else:
                if isinstance(res, dict) and _as_bool(res.get("boundary")):
                    boundary += 1
            kind = (res.get("kind") or res.get("reason")) if isinstance(res, dict) else None
            if kind == "timeout":
                to += 1
            elif kind in ("crash", "runtime_error"):
                re_count += 1
            else:
                wa += 1

        out["total"] = total
        out["passed"] = passed
        out["failed"] = failed
        out["pass_rate"] = (passed / total) if total else 0.0
        out["wrong_answer_count"] = wa
        out["runtime_error_count"] = re_count
        out["timeout_count"] = to
        out["first_fail_index"] = first_fail if first_fail >= 0 else _NAN
        out["first_fail_numeric_diff"] = diff
        out["boundary_fail_count"] = boundary
    except Exception:
        return _nan_block("tests")
    return out


# ------------------------------------------------------------------------- cpg

_CPG_INT_FIELDS = (
    "node_count",
    "edge_count",
    "max_depth",
    "function_count",
    "loop_count",
    "assign_in_condition_count",
    "assign_feeds_output_count",
    "unguarded_recursion_count",
    "array_write_oob_count",
    "use_before_init_count",
    "decrement_in_loop_count",
    "loop_cond_var_unassigned_count",
    "comparison_count",
)


def _compute_cpg(evidence: Any) -> dict[str, Any]:
    out = _nan_block("cpg")
    if evidence is None:
        return out
    try:
        if not isinstance(evidence, dict):
            raise TypeError("cpg evidence must be a dict")
        out["available"] = True
        for short in _CPG_INT_FIELDS:
            value = _as_int(evidence.get(short))
            out[short] = value if value is not None else _NAN
        sim = _as_float(evidence.get("ast_ref_similarity"))
        out["ast_ref_similarity"] = sim if sim is not None else _NAN
    except Exception:
        return _nan_block("cpg")
    return out


# ----------------------------------------------------------------- semantics


def _compute_semantics(source: str) -> dict[str, Any]:
    out = _nan_block("semantics")
    if not isinstance(source, str) or not source.strip():
        return out
    try:
        vals = extract_semantics(source)
        if vals:
            for short in FEATURE_BLOCKS["semantics"]:
                v = vals.get(short)
                out[short] = int(v) if v is not None else _NAN
    except Exception:
        return _nan_block("semantics")
    return out


# -------------------------------------------------------------------- context

def _compute_context(evidence: Any) -> dict[str, Any]:
    out = _nan_block("context")
    if evidence is None:
        return out
    try:
        if not isinstance(evidence, dict):
            raise TypeError("context evidence must be a dict")
        out["available"] = True
        statement = evidence.get("statement")
        out["statement_length"] = (
            len(statement) if isinstance(statement, str) else _NAN
        )
        count = _as_int(evidence.get("sample_test_count"))
        out["sample_test_count"] = count if count is not None else _NAN
        present = _as_bool(evidence.get("sample_tests_present"))
        if present is None:
            present = bool(count) if count is not None else False
        out["sample_tests_present"] = present
        constraints = _as_bool(evidence.get("has_constraints"))
        out["constraints_present"] = constraints if constraints is not None else False
        difficulty = _as_float(evidence.get("difficulty"))
        out["difficulty"] = difficulty if difficulty is not None else _NAN
        tags = evidence.get("concept_tags")
        n_tags = len(tags) if isinstance(tags, (list, tuple)) else _as_int(tags)
        out["concept_tag_count"] = n_tags if n_tags is not None else _NAN
        subs = _as_int(evidence.get("cpp_submission_count"))
        out["cpp_submission_count"] = subs if subs is not None else _NAN
    except Exception:
        return _nan_block("context")
    return out


# ------------------------------------------------------------------ interface

def extract_features(
    source: str,
    language: str = "cpp",
    *,
    warnings: list[dict] | None = None,
    runtime: dict | None = None,
    tests: dict | None = None,
    cpg: dict | None = None,
    context: dict | None = None,
) -> dict[str, dict[str, float | None]]:
    """v0 interface — pinned in FEATURE_SCHEMA.md; do not change pre-G3.

    Returns nested feature blocks keyed by block name (row shape §6).
    """
    return {
        "static": _compute_static(source, language),
        "warnings": _compute_warnings(warnings),
        "runtime": _compute_runtime(runtime),
        "tests": _compute_tests(tests),
        "cpg": _compute_cpg(cpg),
        "semantics": _compute_semantics(source),
        "context": _compute_context(context),
    }
