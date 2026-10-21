"""Lane B labeling functions (LFs) for CodeStream (Master Plan §3.2, §3.5, §5-U2).

Every LF is a conjunction of two distinct signals — one static (code shape),
one dynamic (what the run showed) — and returns a ``Fire`` or ``None``.
``LF_REGISTRY`` lists each LF's class and its ``lf_inputs`` (the evidence
fields it reads) so the masked model can blank them (§6, §11).

Classes 4, 8, 9, 10 are *detectors*, not labels: their fires go to the
discovery review pool (§13.5) and never to the OTHER_ERROR pool.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from codestream_static import Program, comparisons, line_of
from repair_verify import (
    FLIP,
    assignments_in_conditions,
    descending_for_loops,
    range_check_conditions,
    recursive_functions,
    stale_while_loops,
)

FLOOR_CLASSES = ["CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS", "CPP_INT_OVERFLOW",
                 "CPP_MISSING_BASE_CASE", "CPP_ASSIGN_VS_COMPARE"]
DISCOVERY_CLASSES = ["CPP_UNINITIALIZED_VAR", "CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK",
                     "CPP_STALE_EXIT"]
ALL_CLASSES = FLOOR_CLASSES[:3] + ["CPP_UNINITIALIZED_VAR"] + FLOOR_CLASSES[3:] + \
    ["CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK", "CPP_STALE_EXIT", "CPP_OTHER_ERROR"]

SOURCE_CAP = 0.85  # CodeStream cap (§3.5)
INT_MAX = 2**31 - 1


@dataclass
class Fire:
    lf: str
    cls: str
    evidence: dict = field(default_factory=dict)


@dataclass
class Ctx:
    code: str
    prog: Program
    result: dict  # sandbox_runner result
    tests: list[dict]  # problem tests (input/output)

    @property
    def failing(self) -> list[dict]:
        t = self.result.get("tests") or {}
        return [r for r in t.get("results", []) if r.get("status") not in ("pass", "skipped")
                and not r.get("flaky")]

    @property
    def diffs(self) -> list[dict]:
        return [r["diff"] for r in self.failing if r.get("diff")]

    @property
    def san_reports(self) -> list[dict]:
        return ((self.result.get("runtime") or {}).get("sanitizer") or {}).get("reports") or []

    @property
    def valgrind(self) -> dict:
        return (self.result.get("runtime") or {}).get("valgrind") or {}

    @property
    def warn_flags(self) -> dict:
        return (self.result.get("warnings") or {}).get("count_by_flag") or {}

    def warn_lines(self, *flags) -> set[int]:
        items = (self.result.get("warnings") or {}).get("items") or []
        return {w["line"] for w in items if w.get("flag") in flags}


# ----------------------------------------------------------- evidence -----

def _ints(s: str) -> list[int]:
    """Whitespace-separated pure integer tokens (not digits inside words)."""
    return [int(x) for x in (s or "").split()[:5000] if re.fullmatch(r"-?\d{1,18}", x)]


def overflow_reports(ctx: Ctx) -> list[dict]:
    out = []
    for r in ctx.san_reports:
        if r["tool"] == "asan" and r["kind"].endswith("buffer-overflow"):
            out.append(r)
        elif r["tool"] == "ubsan" and r["kind"] == "index-out-of-bounds":
            out.append(r)
    return out


def fixed_arrays(prog: Program) -> list[tuple[str, int]]:
    from repair_verify import _size_value
    out = []
    for d in prog.decls:
        if d.array_size_span:
            v = _size_value(prog, d.array_size or "")
            if v:
                out.append((d.var, v))
    return out


def _undersized(ctx: Ctx, rep: dict) -> bool:
    """Does the failing test's input carry a number above the smallest fixed array?"""
    arrs = fixed_arrays(ctx.prog)
    if not arrs:
        return False
    idx = rep.get("test_idx")
    if idx is None or idx >= len(ctx.tests):
        return False
    nums = _ints(ctx.tests[idx]["input"])
    return bool(nums) and max(nums) >= min(v for _, v in arrs)


def pm1_evidence(ctx: Ctx, loop_lines: set[int] | None = None) -> dict | None:
    """±1 run evidence: numeric deltas of exactly 1, one element extra/missing
    at either end of a multi-token answer, or an out-of-bounds access exactly
    one past the end (to the right) on a line inside the given loops."""
    for d in ctx.diffs:
        if d.get("numeric_deltas") and d.get("all_deltas_pm1"):
            return {"signal": "numeric_delta_pm1", "deltas": d["numeric_deltas"][:5]}
        if d.get("token_count_delta") in (-1, 1) and max(d.get("expected_tokens") or 0,
                                                          d.get("actual_tokens") or 0) >= 2 and (
                d.get("is_prefix_of_expected") or d.get("expected_is_prefix")
                or d.get("is_suffix_of_expected") or d.get("expected_is_suffix")):
            return {"signal": "one_token_extra_or_missing", "delta": d["token_count_delta"]}
    for r in overflow_reports(ctx):
        if r.get("elements_past_end") == 0 and r.get("direction", "right") in ("right", None) \
                and not _undersized(ctx, r) and (loop_lines is None or r.get("line") in loop_lines):
            return {"signal": "oob_exact_size", "line": r.get("line"), "tool": r["tool"]}
    return None


def _lines_of_loops(prog: Program, loops) -> set[int]:
    out = set()
    for lp in loops:
        out |= set(range(line_of(prog.code, lp.keyword), line_of(prog.code, lp.body.end) + 1))
    return out


def _loop_lines(prog: Program) -> set[int]:
    out = set()
    for lp in prog.loops:
        a = line_of(prog.code, lp.keyword)
        b = line_of(prog.code, lp.body.end)
        out |= set(range(a, b + 1))
    return out


# ----------------------------------------------------------------- LFs -----

def lf_loop_boundary(ctx: Ctx) -> Fire | None:
    """Loop test with a relational operator (<, <=, >, >=, != n+1) ∧ ±1
    divergence or an exact-size out-of-bounds access."""
    static, inclusive = [], []
    for lp in ctx.prog.loops:
        if not lp.cond:
            continue
        ops = [op for op, *_ in comparisons(ctx.prog.text, lp.cond)]
        cond = ctx.prog.text[lp.cond.start:lp.cond.end]
        if any(o in FLIP for o in ops) or re.search(r"(<|!=)\s*\w+\s*\+\s*1\b", cond):
            static.append(lp.line)
        if any(o in ("<=", ">=") for o in ops) or re.search(r"(<|!=)\s*\w+\s*\+\s*1\b", cond):
            inclusive.append(lp)
    if not static:
        return None
    ev = pm1_evidence(ctx, loop_lines=_lines_of_loops(ctx.prog, inclusive))
    if not ev:
        return None
    return Fire("lf_loop_boundary", "CPP_LOOP_BOUNDARY", {"loop_lines": static[:5], **ev})


def lf_off_by_one(ctx: Ctx) -> Fire | None:
    """Index/count arithmetic (a[i±1], start at 1, bound n-1, printed x±1) ∧ ±1 divergence."""
    t = ctx.prog.text
    static = []
    if re.search(r"\[\s*[A-Za-z_]\w*\s*[+-]\s*1\s*\]", t):
        static.append("index_pm1")
    for lp in ctx.prog.loops:
        if lp.kind == "for" and lp.init and re.search(r"=\s*1\s*$", t[lp.init.start:lp.init.end]):
            static.append("init_1")
        if lp.cond and re.search(r"-\s*1\b", t[lp.cond.start:lp.cond.end]):
            static.append("bound_minus_1")
    if re.search(r"(<<|,)\s*[A-Za-z_]\w*\s*[+-]\s*1\b\s*(?:<<|;|\))", t):
        static.append("output_pm1")
    if not static:
        return None
    ev = pm1_evidence(ctx, loop_lines=_lines_of_loops(ctx.prog, ctx.prog.loops))
    if not ev:
        return None
    return Fire("lf_off_by_one", "CPP_OFF_BY_ONE", {"static": sorted(set(static)), **ev})


def lf_array_bounds(ctx: Ctx) -> Fire | None:
    """Fixed-size array ∧ sanitizer OOB that is ≥2 past the end or on an undersized array."""
    arrs = fixed_arrays(ctx.prog)
    if not arrs:
        return None
    for r in overflow_reports(ctx):
        far = (r.get("elements_past_end") or 0) >= 1
        if far or _undersized(ctx, r):
            return Fire("lf_array_bounds", "CPP_ARRAY_BOUNDS",
                        {"arrays": arrs[:5], "tool": r["tool"], "kind": r["kind"],
                         "elements_past_end": r.get("elements_past_end"),
                         "undersized_input": _undersized(ctx, r), "line": r.get("line")})
    return None


def lf_uninit_detector(ctx: Ctx) -> Fire | None:
    """DETECTOR (class 4): -Wmaybe-uninitialized/-Wuninitialized ∧ Valgrind uninit use."""
    w = ctx.warn_flags
    wflag = w.get("-Wmaybe-uninitialized", 0) + w.get("-Wuninitialized", 0)
    vg = ctx.valgrind
    if wflag and vg.get("uninit"):
        return Fire("lf_uninit_detector", "CPP_UNINITIALIZED_VAR",
                    {"warning_lines": sorted(ctx.warn_lines("-Wmaybe-uninitialized", "-Wuninitialized"))[:5],
                     "valgrind_kinds": sorted(k for k in vg.get("kinds", {}) if k.startswith("uninit"))})
    return None


def lf_int_overflow(ctx: Ctx) -> Fire | None:
    """`int` arithmetic ∧ (UBSan signed overflow, or failures only where answers exceed INT_MAX)."""
    if not re.search(r"\bint\b(?!\s+main\b)", ctx.prog.text):
        return None
    if not (ctx.result.get("tests") or {}).get("passed"):
        return None  # overflow bugs pass the small tests and fail only large ones
    if any(r["tool"] == "ubsan" and r["kind"] == "signed-integer-overflow" for r in ctx.san_reports):
        return Fire("lf_int_overflow", "CPP_INT_OVERFLOW", {"signal": "ubsan_signed_overflow"})
    big_fail = 0
    for r in ctx.failing:
        if r["idx"] < len(ctx.tests):
            exp = _ints(ctx.tests[r["idx"]]["output"])
            if exp and max(abs(x) for x in exp) > INT_MAX:
                big_fail += 1
    passing_big = 0
    for r in (ctx.result.get("tests") or {}).get("results", []):
        if r.get("status") == "pass" and r["idx"] < len(ctx.tests):
            exp = _ints(ctx.tests[r["idx"]]["output"])
            if exp and max(abs(x) for x in exp) > INT_MAX:
                passing_big += 1
    if big_fail and big_fail == len(ctx.failing) and not passing_big:
        return Fire("lf_int_overflow", "CPP_INT_OVERFLOW",
                    {"signal": "fails_only_beyond_int_max", "tests": big_fail})
    return None


def lf_missing_base_case(ctx: Ctx) -> Fire | None:
    """Self-recursive function ∧ stack overflow (sanitizer / Valgrind)."""
    rec = recursive_functions(ctx.prog)
    if not rec:
        return None
    rt = ctx.result.get("runtime") or {}
    if rt.get("stack_overflow"):
        return Fire("lf_missing_base_case", "CPP_MISSING_BASE_CASE",
                    {"functions": [f.name for f in rec][:3], "signal": "stack_overflow"})
    return None


def lf_assign_vs_compare(ctx: Ctx) -> Fire | None:
    """-Wparentheses ∧ `=` inside a condition whose variable is read again later."""
    sites = assignments_in_conditions(ctx.prog)
    if not sites:
        return None
    wl = ctx.warn_lines("-Wparentheses")
    for cond, off, var in sites:
        ln = line_of(ctx.prog.code, off)
        if ln not in wl:
            continue
        later = ctx.prog.text[cond.span.end:]
        if var and re.search(r"\b" + re.escape(var) + r"\b", later):
            return Fire("lf_assign_vs_compare", "CPP_ASSIGN_VS_COMPARE",
                        {"line": ln, "var": var, "cond_kind": cond.kind})
    return None


def lf_wrong_loop_dir_detector(ctx: Ctx) -> Fire | None:
    """DETECTOR (class 8): descending for-loop ∧ reversed / permuted output."""
    loops = descending_for_loops(ctx.prog)
    if not loops:
        return None
    for d in ctx.diffs:
        if d.get("reversed_tokens") or d.get("reversed_lines"):
            return Fire("lf_wrong_loop_dir_detector", "CPP_WRONG_LOOP_DIR",
                        {"signal": "reversed_output", "loop_lines": [l.line for l, *_ in loops][:3]})
    for d in ctx.diffs:
        if d.get("same_multiset"):
            return Fire("lf_wrong_loop_dir_detector", "CPP_WRONG_LOOP_DIR",
                        {"signal": "permuted_output", "loop_lines": [l.line for l, *_ in loops][:3]})
    return None


def lf_range_check_detector(ctx: Ctx) -> Fire | None:
    """DETECTOR (class 9): range-validation `if` ∧ a failing test whose input
    sits on that condition's boundary literal (±1)."""
    conds = range_check_conditions(ctx.prog)
    if not conds:
        return None
    # literals compared against an index / loop variable (j >= 0, i < n) are
    # index guards, not input validation
    idx_vars = {lp.var for lp in ctx.prog.loops if lp.var}
    idx_vars |= set(re.findall(r"\[\s*([A-Za-z_]\w*)", ctx.prog.text))
    lits = set()
    pair = re.compile(r"([A-Za-z_]\w*)\s*(?:<=|>=|<|>|==|!=)\s*(-?\d+)\b|(-?\d+)\s*(?:<=|>=|<|>|==|!=)\s*([A-Za-z_]\w*)")
    for c, _ in conds:
        for m in pair.finditer(ctx.prog.text[c.span.start:c.span.end]):
            var, lit = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
            if var not in idx_vars:
                lits.add(int(lit))
    if not lits:
        return None
    t = ctx.result.get("tests") or {}
    if not t.get("passed"):
        return None  # boundary bugs leave the ordinary tests passing
    for r in ctx.failing:
        if r["idx"] < len(ctx.tests):
            nums = set(_ints(ctx.tests[r["idx"]]["input"]))
            hit = {x for x in nums for b in lits if abs(x - b) <= 1}
            if hit:
                return Fire("lf_range_check_detector", "CPP_RANGE_CHECK",
                            {"boundary_literals": sorted(lits)[:6], "inputs_on_boundary": sorted(hit)[:6],
                             "cond_lines": [c.line for c, _ in conds][:3]})
    return None


def lf_stale_exit_detector(ctx: Ctx) -> Fire | None:
    """DETECTOR (class 10): while-condition variables never written in the body
    ∧ a timeout or wrong answer."""
    loops = stale_while_loops(ctx.prog)
    if not loops:
        return None
    if ctx.failing:
        return Fire("lf_stale_exit_detector", "CPP_STALE_EXIT",
                    {"loop_lines": [l.line for l, _ in loops][:3],
                     "cond_vars": loops[0][1][:5],
                     "statuses": sorted({r["status"] for r in ctx.failing})})
    return None


LFS = [lf_loop_boundary, lf_off_by_one, lf_array_bounds, lf_uninit_detector, lf_int_overflow,
       lf_missing_base_case, lf_assign_vs_compare, lf_wrong_loop_dir_detector,
       lf_range_check_detector, lf_stale_exit_detector]

# lf_inputs registry (§6): evidence fields each LF reads. Feature names follow
# the sandbox_runner result paths; Rayaan maps them onto FEATURE_SCHEMA names.
LF_REGISTRY = {
    "lf_loop_boundary": {"class": "CPP_LOOP_BOUNDARY", "kind": "label",
                         "lf_inputs": ["static.loop_cmp_le_ge", "static.loop_bound_plus1",
                                       "tests.diff.numeric_deltas", "tests.diff.token_count_delta",
                                       "runtime.sanitizer.elements_past_end"]},
    "lf_off_by_one": {"class": "CPP_OFF_BY_ONE", "kind": "label",
                      "lf_inputs": ["static.index_pm1", "static.loop_init_1", "static.bound_minus_1",
                                    "static.output_pm1", "tests.diff.numeric_deltas",
                                    "tests.diff.token_count_delta", "runtime.sanitizer.elements_past_end"]},
    "lf_array_bounds": {"class": "CPP_ARRAY_BOUNDS", "kind": "label",
                        "lf_inputs": ["static.fixed_array_size", "runtime.sanitizer.asan_overflow",
                                      "runtime.sanitizer.ubsan_index_oob",
                                      "runtime.sanitizer.elements_past_end"]},
    "lf_uninit_detector": {"class": "CPP_UNINITIALIZED_VAR", "kind": "detector",
                           "lf_inputs": ["warnings.-Wmaybe-uninitialized", "warnings.-Wuninitialized",
                                         "runtime.valgrind.uninit"]},
    "lf_int_overflow": {"class": "CPP_INT_OVERFLOW", "kind": "label",
                        "lf_inputs": ["static.int_decl", "runtime.sanitizer.ubsan_signed_overflow",
                                      "tests.expected_beyond_int_max"]},
    "lf_missing_base_case": {"class": "CPP_MISSING_BASE_CASE", "kind": "label",
                             "lf_inputs": ["static.self_recursion", "runtime.stack_overflow"]},
    "lf_assign_vs_compare": {"class": "CPP_ASSIGN_VS_COMPARE", "kind": "label",
                             "lf_inputs": ["warnings.-Wparentheses", "static.assign_in_condition",
                                           "static.assigned_var_reused"]},
    "lf_wrong_loop_dir_detector": {"class": "CPP_WRONG_LOOP_DIR", "kind": "detector",
                                   "lf_inputs": ["static.descending_for", "tests.diff.reversed_tokens",
                                                 "tests.diff.reversed_lines", "tests.diff.same_multiset"]},
    "lf_range_check_detector": {"class": "CPP_RANGE_CHECK", "kind": "detector",
                                "lf_inputs": ["static.range_if", "tests.boundary_input_fail"]},
    "lf_stale_exit_detector": {"class": "CPP_STALE_EXIT", "kind": "detector",
                               "lf_inputs": ["static.stale_while", "tests.failing"]},
}


def run_lfs(ctx: Ctx) -> list[Fire]:
    out = []
    for lf in LFS:
        try:
            f = lf(ctx)
        except Exception as exc:  # an LF bug must not drop the row silently
            f = None
            ctx.result.setdefault("_lf_errors", []).append(f"{lf.__name__}: {exc}")
        if f:
            out.append(f)
    return out


# ------------------------------------------------------- confidence (§3.5) --

def beta_lower(k: int, n: int, q: float = 0.2) -> float:
    """Lower 80% bound (the 20th percentile) of the Beta(1+k, 1+n-k) posterior.

    For integer parameters the Beta CDF is a binomial tail:
    I_x(a, b) = P[Binomial(a+b-1, x) >= a]. Solved by bisection.
    """
    a, b = 1 + k, 1 + (n - k)
    m = a + b - 1

    def cdf(x):
        return sum(math.comb(m, j) * x**j * (1 - x) ** (m - j) for j in range(a, m + 1))

    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if cdf(mid) < q:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)


def confidence(key: str, audits: dict, cap: float = SOURCE_CAP) -> tuple[float, int, int]:
    """(label_confidence, audited_correct, audited_n) for an LF or repair key."""
    k, n = audits.get(key, (0, 0))
    return min(cap, beta_lower(k, n)), k, n
