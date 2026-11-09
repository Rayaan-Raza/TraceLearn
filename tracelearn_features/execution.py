"""Source-pattern, execution-evidence and repair-evidence features (schema 1.2).

Three blocks, none of which reads a label:

- `source`: patterns in the submission's own code (loop shapes, array sizes, integer widths).
- `evidence`: what running it against the problem's tests shows (per-test output diffs,
  sanitizer reports), in the `sandbox_runner` vocabulary.
- `repair`: for each class's inverse edits (`scripts/repair_verify.py`), whether one edit fixes
  the first failing test, or every test. The labelling rule is "the bug whose fix makes the
  first failing test pass", and this measures that directly.

`scripts/counterfactual_evidence.py` produces the run record that `execution_blocks` reads.
Every lane gets the same runner and flags, because a block measured differently per lane
becomes a fingerprint of the lane rather than evidence about the bug.

Size is deliberately absent. `static.*` size features separate the lanes (median 15 lines for
synthetic, 30 for CodeStream, 54 for PROGPedia), and the `execution` model excludes them.
"""
from __future__ import annotations

import math
import re
from typing import Any

_COMMENT = re.compile(r"//.*?$|/\*.*?\*/", re.M | re.S)
_STRING = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_TYPE = r"(?:unsigned\s+|signed\s+|const\s+|static\s+)*(?:long\s+long(?:\s+int)?|long(?:\s+int)?|int|short|char|float|double|size_t|bool)"
NAN = float("nan")

# The classes with inverse edits, in the order the training features were built.
REPAIR_CLASSES = ("LOOP_BOUNDARY", "OFF_BY_ONE", "ARRAY_BOUNDS", "UNINITIALIZED_VAR", "INT_OVERFLOW",
                  "MISSING_BASE_CASE", "ASSIGN_VS_COMPARE", "WRONG_LOOP_DIR", "RANGE_CHECK")
_DIFF_FLAGS = ("is_prefix_of_expected", "expected_is_prefix", "is_suffix_of_expected", "expected_is_suffix", "empty_output",
               "reversed_tokens", "reversed_lines", "same_multiset", "all_deltas_pm1", "negative_where_positive")
_STATUSES = ("wrong", "crash", "timeout", "presentation")


def _balanced_end(text: str, start: int, opener: str = "(", closer: str = ")") -> int:
    depth = 0
    for k in range(start, len(text)):
        if text[k] == opener:
            depth += 1
        elif text[k] == closer:
            depth -= 1
            if depth == 0:
                return k + 1
    return -1


def _loops(code: str):
    """(kind, init, condition, update, body) for each for/while the light parser can read."""
    for m in re.finditer(r"\b(for|while)\s*\(", code):
        end = _balanced_end(code, m.end() - 1)
        if end < 0:
            continue
        head = code[m.end():end - 1]
        parts = head.split(";") if m.group(1) == "for" else ["", head, ""]
        if len(parts) != 3:
            continue
        rest = code[end:]
        ws = len(rest) - len(rest.lstrip())
        if rest.lstrip().startswith("{"):
            stop = _balanced_end(code, end + ws, "{", "}")
            body = code[end + ws:stop] if stop > 0 else rest[:300]
        else:
            body = rest.split(";", 1)[0]
        yield m.group(1), parts[0], parts[1], parts[2], body


def source_features(src: str) -> dict[str, float]:
    """The `source` block. Comments and string contents are ignored, except the format-string check."""
    s = _STRING.sub('""', _COMMENT.sub("", src))
    f: dict[str, float] = {}
    defs = {m.group(1): int(m.group(2)) for m in re.finditer(r"#\s*define\s+(\w+)\s+(\d+)", s)}
    defs.update({m.group(1): int(m.group(2)) for m in re.finditer(r"const\s+\w+\s+(\w+)\s*=\s*(\d+)", s)})
    sizes, vla = [], 0
    for m in re.finditer(_TYPE + r"\s+\**\s*\w+\s*\[\s*([^\]]*)\]", s):
        e = m.group(1).strip()
        if e.isdigit():
            sizes.append(int(e))
        elif e in defs:
            sizes.append(defs[e])
        elif e:
            vla += 1
    f["arr_fixed_n"] = len(sizes)
    f["arr_vla_n"] = vla
    f["arr_fixed_max_log"] = math.log10(max(sizes) + 1) if sizes else NAN
    f["arr_fixed_min_log"] = math.log10(min(sizes) + 1) if sizes else NAN
    f["heap_alloc"] = len(re.findall(r"\b(malloc|calloc|new)\b", s))
    f["uses_ll"] = int(bool(re.search(r"long\s+long|int64_t|__int64", s)))
    f["uses_long"] = int(bool(re.search(r"\blong\b", s)))
    f["uses_double"] = int(bool(re.search(r"\b(double|float)\b", s)))
    f["mult_ident"] = len(re.findall(r"\b[A-Za-z_]\w*(?:\[[^\]]*\])?\s*\*\s*[A-Za-z_(]", s))
    f["mult_assign"] = len(re.findall(r"\*=", s))
    f["pow_call"] = len(re.findall(r"\bpow\s*\(", s))
    f["accum"] = len(re.findall(r"\+=", s))
    f["fmt_ll"] = int("%lld" in src or "%ld" in src)
    n_le = n_ge = n_lt = n_gt = le_arr = lt_m1 = s1_lt = s1_le = s0_le = lp_plus = lp_minus = wrong_idx = stale = desc = 0
    for kind, init, cond, update, body in _loops(s):
        m = re.search(r"(\w+)\s*(<=|>=|<|>|!=)\s*(.+)", cond)
        if m:
            var, op, bound = m.group(1), m.group(2), m.group(3).strip()
            n_le += op == "<="
            n_lt += op == "<"
            n_ge += op == ">="
            n_gt += op == ">"
            start = re.search(r"\b" + re.escape(var) + r"\s*=\s*(\d+)\s*$", init.strip())
            first = start.group(1) if start else None
            if op == "<=" and re.search(r"\b" + re.escape(var) + r"\b\s*\]", body):
                le_arr += 1
            if op == "<" and re.search(r"-\s*1\s*$", bound):
                lt_m1 += 1
            s1_lt += first == "1" and op == "<"
            s1_le += first == "1" and op == "<="
            s0_le += first == "0" and op == "<="
            if re.search(r"\[" + re.escape(var) + r"\s*\+\s*\d+\s*\]", body):
                lp_plus += 1
            if re.search(r"\[" + re.escape(var) + r"\s*-\s*\d+\s*\]", body):
                lp_minus += 1
            if "--" in update or "-=" in update:
                desc += 1
            indices = set(re.findall(r"\[\s*([A-Za-z_]\w*)\s*\]", body))
            if indices and var not in indices:
                wrong_idx += 1
        if kind == "while":
            names = set(re.findall(r"\b[A-Za-z_]\w*\b", cond)) - {"cin", "scanf", "true", "false", "EOF"}
            if names and "scanf" not in cond and "cin" not in cond:
                updated = False
                for x in names:
                    e = re.escape(x)
                    if re.search(r"(\b" + e + r"\b\s*(=[^=]|\+\+|--|[-+*/%]=|>>))|((\+\+|--)\s*" + e + r"\b)|&\s*" + e + r"\b|>>\s*" + e + r"\b", body):
                        updated = True
                        break
                stale += not updated
    f.update(lp_le=n_le, lp_lt=n_lt, lp_ge=n_ge, lp_gt=n_gt, lp_le_idx=le_arr, lp_lt_m1=lt_m1, lp_s1_lt=s1_lt, lp_s1_le=s1_le,
             lp_s0_le=s0_le, lp_idx_plus=lp_plus, lp_idx_minus=lp_minus, lp_wrong_idx=wrong_idx, lp_stale=stale, lp_desc=desc)
    reads = 0
    for m in re.finditer(r"\b" + _TYPE + r"\s+([^;()=\[\]]+);", s):
        for var in re.findall(r"(?:^|,)\s*\*?\s*([A-Za-z_]\w*)\s*(?=,|$)", m.group(1)):
            after = s[m.end():]
            use = re.search(r"\b" + re.escape(var) + r"\b", after)
            if not use:
                continue
            ctx = after[use.start():use.end() + 6]
            if re.match(re.escape(var) + r"\s*(\+=|-=|\*=|/=|\+\+|--)", ctx) or re.match(re.escape(var) + r"\s*[<>!]=?\s*", ctx):
                reads += 1
    f["read_before_write"] = reads
    conds = re.findall(r"\bif\s*\(([^{};]*)\)", s)
    f["if_lit_cmp"] = sum(bool(re.search(r"(<=|>=|<|>|==)\s*-?\d", c)) for c in conds)
    f["if_and"] = sum("&&" in c for c in conds)
    f["if_or"] = sum("||" in c for c in conds)
    f["else_if"] = len(re.findall(r"else\s+if", s))
    f["if_strict"] = sum(bool(re.search(r"(?<![<>=!])[<>](?![=<>])", c)) for c in conds)
    f["if_nonstrict"] = sum(bool(re.search(r"[<>]=", c)) for c in conds)
    f["if_eq"] = sum("==" in c for c in conds)
    f["minus1"] = len(re.findall(r"-\s*1\b", s))
    f["plus1"] = len(re.findall(r"\+\s*1\b", s))
    return f


def evidence_features(tests: dict[str, Any] | None, runtime: dict[str, Any] | None) -> dict[str, float]:
    """The `evidence` block, from `sandbox_runner` test results and runtime reports."""
    tests = tests or {}
    rt = runtime or {}
    f: dict[str, float] = {}
    results = [x for x in (tests.get("results") or []) if isinstance(x, dict)]
    if results:
        n = len(results)
        fails = [x for x in results if x.get("status") != "pass"]
        first = fails[0] if fails else {}
        d = first.get("diff") or {}
        f.update(n=n, pass_frac=1 - len(fails) / n, ff_frac=(results.index(first) / n if fails else NAN))
        for st in _STATUSES:
            f[f"ff_{st}"] = int(first.get("status") == st)
            f[f"fr_{st}"] = sum(x.get("status") == st for x in fails) / max(len(fails), 1)
        actual, expected = d.get("actual_tokens"), d.get("expected_tokens")
        f["tok_delta"] = d.get("token_count_delta", NAN) if d else NAN
        f["tok_ratio"] = (actual / expected) if d and expected else NAN
        f["prefix_frac"] = (d.get("prefix_tokens", 0) / expected) if d and expected else NAN
        f["exp_tok_log"] = math.log10(expected + 1) if d and expected else NAN
        for k in _DIFF_FLAGS:
            f[k] = int(bool(d.get(k))) if d else NAN
        largest = d.get("max_abs_delta")
        f["maxd_log"] = math.log10(abs(largest) + 1) if largest is not None else NAN
        deltas = d.get("numeric_deltas")
        f["nd_frac"] = (len(deltas) / expected) if deltas and expected else NAN
        f["sign_delta"] = (1 if deltas[0] > 0 else -1) if deltas else NAN
        if fails:
            diffs = [x.get("diff") or {} for x in fails]
            f["fr_pm1"] = sum(bool(z.get("all_deltas_pm1")) for z in diffs) / len(fails)
            f["fr_neg"] = sum(bool(z.get("negative_where_positive")) for z in diffs) / len(fails)
            f["fr_empty"] = sum(bool(z.get("empty_output")) for z in diffs) / len(fails)
    san = rt.get("sanitizer") or {}
    if san.get("complete") or san.get("reports"):
        kinds = san.get("kinds") or {}
        reports = [x for x in (san.get("reports") or []) if isinstance(x, dict)]
        ks = " ".join(kinds)
        f.update(sa_avail=1, sa_oob=int("index-out-of-bounds" in ks), sa_stack=int("stack-buffer" in ks), sa_heap=int("heap-buffer" in ks),
                 sa_global=int("global-buffer" in ks), sa_signed=int("signed" in ks), sa_shift=int("shift" in ks),
                 sa_div=int("divide" in ks or "division" in ks), sa_null=int("null" in ks or "SEGV" in ks), sa_so=int("stack-overflow" in ks),
                 sa_uaf=int("use-after" in ks), sa_vla=int("vla" in ks or "dynamic-stack" in ks), sa_n=len(kinds))
        past = [x.get("elements_past_end") for x in reports if x.get("elements_past_end") is not None]
        f["sa_past_min"] = min(past) if past else NAN
        f["sa_past_max_log"] = math.log10(abs(max(past)) + 1) if past else NAN
        idx = [x.get("index") for x in reports if x.get("index") is not None]
        f["sa_neg_idx"] = int(any(i < 0 for i in idx)) if idx else NAN
        f["sa_left"] = int(any(x.get("direction") == "left" for x in reports))
        f["sa_write"] = int(any(x.get("access") == "WRITE" for x in reports))
    if "stack_overflow" in rt:
        f["rt_so"] = int(bool(rt.get("stack_overflow")))
    return f


def repair_features(cf: dict[str, Any] | None) -> dict[str, float]:
    """The `repair` block. Counts are capped; a program's candidate count is left out because it measures program shape."""
    cf = cf or {}
    f: dict[str, float] = {}
    classes = cf.get("classes") or {}
    if classes:
        n_all = n_first = 0
        for name in REPAIR_CLASSES:
            v = classes.get("CPP_" + name)
            if not v:
                continue
            key = name.lower()
            f[f"{key}_fix_first"] = min(v["fix_first"], 3)
            f[f"{key}_noreg"] = min(v["fix_first_noreg"], 3)
            f[f"{key}_fix_all"] = min(v["fix_all"], 1)
            f[f"{key}_gain"] = v["best_gain"]
            f[f"{key}_tried"] = float(v["compiled"] > 0)
            n_all += v["fix_all"] > 0
            n_first += v["fix_first"] > 0
        f["n_fix_all"] = n_all
        f["n_fix_first"] = n_first
    uninit = cf.get("uninit")
    if uninit:
        f["uninit_differs"] = float(uninit["differs"])
        f["uninit_zero_fixes"] = float(uninit["zero_fixes"])
    return f


def execution_blocks(record: dict[str, Any] | None) -> dict[str, dict[str, float]]:
    """`evidence` and `repair` blocks from one run record; empty when the program did not compile and run.

    Missing values are left out, so they become NaN downstream rather than a fabricated zero.
    """
    if not record or "error" in record or not record.get("compiled"):
        return {}
    keep = lambda block: {k: v for k, v in block.items() if not (isinstance(v, float) and math.isnan(v))}  # noqa: E731
    return {"evidence": keep(evidence_features(record.get("tests"), record.get("runtime"))),
            "repair": keep(repair_features(record.get("cf")))}
