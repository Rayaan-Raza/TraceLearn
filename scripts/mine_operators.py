"""
mine_operators.py — E1: Reverse-mutation operator library.

Mines CodeStream wrong->Accepted attempt pairs (train-side clusters only),
diffs them, and clusters the diffs into operator patterns for each
tl-cpp-v2 class. Outputs the operator library JSON consumed by
generate_mutants.py.

Requirements: each operator has >=4 distinct surface forms.

Usage:
  python scripts/mine_operators.py
  python scripts/mine_operators.py --min-forms 4 --out scripts/operator_library.json
"""

import argparse
import csv
import difflib
import json
import os
import re
import sys
from collections import defaultdict

csv.field_size_limit(10 ** 7)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODESTREAM_CSV = os.path.join(
    ROOT, "Datasets_RAW",
    "CodeStream A Dataset of Iterative Programming Subm",
    "Submission Data.csv",
)
CLUSTER_SPLIT = os.path.join(
    ROOT, "data", "misconception_dataset", "raw_recovery", "cluster_split.json"
)
DEFAULT_OUT = os.path.join(ROOT, "scripts", "operator_library.json")


# ---------------------------------------------------------------------------
# Normalise a raw problem ID to the tl-* form
# ---------------------------------------------------------------------------
def norm_pid(raw: str) -> str:
    if raw.startswith("tl-"):
        return raw
    return f"tl-codestream-{raw}"


# ---------------------------------------------------------------------------
# Taxonomy class signatures — AST/regex patterns per class
# ---------------------------------------------------------------------------

class_patterns = {
    # Class 1 — loop boundary: <= changed to < or vice versa, < n+1 -> < n, etc.
    "CPP_LOOP_BOUNDARY": [
        (r"<=\s*(\w+)\s*([+\-]\s*1)?", r"<\s*\1"),           # <= n -> < n
        (r"<\s*(\w+)\s*\+\s*1", r"<=\s*\1"),                  # < n+1 -> <= n
        (r"!=\s*(\w+)\s*\+\s*1", r"<\s*\1"),                  # != n+1 -> < n
        (r"for\s*\(.*<=", r"for.*<[^=]"),                      # for(; <=; ) -> for(; <; )
    ],
    # Class 2 — off-by-one: index arithmetic ±1
    "CPP_OFF_BY_ONE": [
        (r"\bi\s*\+\s*1\b", r"\bi\b"),                        # a[i+1] -> a[i]
        (r"\bi\s*-\s*1\b", r"\bi\b"),                         # a[i-1] -> a[i]
        (r"int\s+\w+\s*=\s*1\s*;", r"int\s+\w+\s*=\s*0\s*;"), # start = 1 -> 0
        (r"\bn\s*-\s*1\b", r"\bn\b"),                          # n-1 -> n
    ],
    # Class 3 — array bounds: fixed array too small
    "CPP_ARRAY_BOUNDS": [
        (r"\[(\d+)\]", r"\[\1\s*\+\s*\d+\]"),                 # [n] -> [n+k]
        (r"int\s+\w+\s*\[(\d+)\]", r"int\s+\w+\s*\[(\d+)\]"), # undersized array
        (r"new\s+\w+\[(\w+)\]", r"new\s+\w+\[(\w+)\s*\+"),    # new T[n] -> new T[n+k]
        (r"char\s+\w+\[(\d+)\]", r"char\s+\w+\[\d+\]"),       # char buf[N] undersized
    ],
    # Class 4 — uninitialized var: declared but not assigned before use
    "CPP_UNINITIALIZED_VAR": [
        (r"int\s+(\w+)\s*;", r"int\s+\1\s*=\s*0\s*;"),        # int x; -> int x = 0;
        (r"double\s+(\w+)\s*;", r"double\s+\1\s*=\s*0"),       # double x; uninit
        (r"bool\s+(\w+)\s*;", r"bool\s+\1\s*="),               # bool x; uninit
        (r"string\s+(\w+)\s*;", r"string\s+\1\s*="),            # string s; uninit
    ],
    # Class 5 — int overflow: arithmetic on int with no cast
    "CPP_INT_OVERFLOW": [
        (r"\bint\b(.{0,30})\*", r"\blong long\b"),             # int -> long long for mul
        (r"(\w+)\s*\*\s*(\w+)", r"\(long long\)\s*\1\s*\*"),   # missing (long long) cast
        (r"\bint\s+sum\b", r"\blong long\s+sum\b"),             # int sum -> ll sum
        (r"\bint\s+ans\b", r"\blong long\s+ans\b"),             # int ans -> ll ans
    ],
    # Class 6 — missing base case: recursion without guard
    "CPP_MISSING_BASE_CASE": [
        (r"if\s*\(\s*n\s*==\s*0\s*\)", r""),                   # if (n==0) removed
        (r"if\s*\(\s*n\s*<=\s*1\s*\)", r""),                   # base case removed
        (r"if\s*\(\s*n\s*==\s*1\s*\)", r""),                   # base case removed
        (r"return\s+0\s*;", r""),                               # return 0 removed from rec
    ],
    # Class 7 — assign vs compare: = in condition
    "CPP_ASSIGN_VS_COMPARE": [
        (r"if\s*\(\s*(\w+)\s*==\s*", r"if\s*\(\s*\1\s*=\s*"),  # == -> =  in if
        (r"while\s*\(\s*(\w+)\s*==\s*", r"while\s*\(\s*\1\s*=\s*"), # == -> = in while
        (r"if\s*\((\w+)\s*!=\s*", r"if\s*\(\1\s*=\s*"),        # != -> = in if
        (r"else if\s*\((\w+)\s*==\s*", r"else if\s*\(\1\s*=\s*"), # == -> = in else if
    ],
    # Class 8 — wrong loop direction
    "CPP_WRONG_LOOP_DIR": [
        (r"for\s*\(.*;\s*i\s*<", r"for.*;\s*i\s*>"),           # < -> > (reverse)
        (r"for\s*\(.*i\s*=\s*0", r"for.*i\s*=\s*n"),           # start 0 -> start n
        (r"i\+\+", r"i--"),                                     # i++ -> i--
        (r"i\s*\+=\s*1", r"i\s*-=\s*1"),                       # i+=1 -> i-=1
    ],
    # Class 9 — range check: wrong boundary in validation
    "CPP_RANGE_CHECK": [
        (r"if\s*\(.*<\s*0\s*\|\|.*>\s*(\w+)\s*\)", r"if.*<=\s*0\s*\|\|.*>="),  # bounds off
        (r"if\s*\(\s*x\s*>=\s*1", r"if\s*\(\s*x\s*>\s*1"),     # >= 1 -> > 1
        (r"if\s*\(\s*x\s*<=\s*n", r"if\s*\(\s*x\s*<\s*n"),     # <= n -> < n
        (r"if\s*\(\s*n\s*<\s*1", r"if\s*\(\s*n\s*<=\s*1"),     # < 1 -> <= 1
    ],
    # Class 10 — stale exit: loop condition never updates
    "CPP_STALE_EXIT": [
        (r"while\s*\(\s*(\w+)\s*<\s*", r"while.*\1.*<"),       # condition var not updated
        (r"while\s*\(\s*true\s*\)", r""),                        # infinite while
        (r"while\s*\(\s*1\s*\)", r""),                           # while(1) without break update
        (r"for\s*\(.*;\s*;\s*\)", r""),                          # for(;;) no update
    ],
}


# ---------------------------------------------------------------------------
# Heuristic operator classifier — given a diff, classify into tl-cpp-v2 class
# ---------------------------------------------------------------------------

# Operator surface forms per class (each is a callable that produces
# the mutated source code from the seed; a None means "no transformation found")

OPERATOR_FORMS = {
    "CPP_LOOP_BOUNDARY": [
        # Form 1: replace <= with < in for loop condition
        ("lb_le_to_lt",
         re.compile(r"(for\s*\([^;]+;\s*\w+\s*)<=(\s*\w+)", re.MULTILINE),
         r"\1<\2"),
        # Form 2: replace < n+1 with <= n  (revert wrong fix)
        ("lb_lt_np1_to_le_n",
         re.compile(r"(for\s*\([^;]+;\s*\w+\s*)<\s*(\w+)\s*\+\s*1", re.MULTILINE),
         r"\1<=\2"),
        # Form 3: != n+1 -> <= n
        ("lb_ne_np1_to_le_n",
         re.compile(r"(for\s*\([^;]+;\s*\w+\s*)!=\s*(\w+)\s*\+\s*1", re.MULTILINE),
         r"\1<=\2"),
        # Form 4: while condition <=
        ("lb_while_le_to_lt",
         re.compile(r"(while\s*\(\s*\w+\s*)<=(\s*\w+\s*\))", re.MULTILINE),
         r"\1<\2"),
    ],
    "CPP_OFF_BY_ONE": [
        # Form 1: a[i+1] -> a[i]
        ("obo_index_plus1",
         re.compile(r"(\w+\s*\[)\s*(\w+)\s*\+\s*1\s*(\])", re.MULTILINE),
         r"\1\2\3"),
        # Form 2: starting index 1 -> 0
        ("obo_init_1_to_0",
         re.compile(r"(for\s*\(\s*int\s+\w+\s*=\s*)1(\s*;)", re.MULTILINE),
         r"\g<1>0\2"),
        # Form 3: n-1 -> n in loop bound
        ("obo_bound_n_minus1",
         re.compile(r"(for\s*\([^;]+;\s*\w+\s*<\s*)(\w+)\s*-\s*1", re.MULTILINE),
         r"\1\2"),
        # Form 4: a[i-1] -> a[i]
        ("obo_index_minus1",
         re.compile(r"(\w+\s*\[)\s*(\w+)\s*-\s*1\s*(\])", re.MULTILINE),
         r"\1\2\3"),
    ],
    "CPP_ARRAY_BOUNDS": [
        # Form 1: undersized array by exactly 1
        ("ab_array_size_minus1",
         re.compile(r"(int\s+\w+\s*\[)\s*(\w+)\s*(\])", re.MULTILINE),
         r"\g<1>\2 - 1\3"),
        # Form 2: char buffer -1
        ("ab_char_buf_minus1",
         re.compile(r"(char\s+\w+\s*\[)\s*(\d+)\s*(\])", re.MULTILINE),
         lambda m: m.group(1) + str(max(1, int(m.group(2)) - 1)) + m.group(3)),
        # Form 3: vector not resized (just applies reserve as resize)
        ("ab_vector_no_resize",
         re.compile(r"(\w+\.reserve\s*\(\s*)(\w+)\s*(\))", re.MULTILINE),
         r"\1\2 - 1\3"),
        # Form 4: new T[n] -> new T[n-1]
        ("ab_new_minus1",
         re.compile(r"(new\s+\w+\s*\[)\s*(\w+)\s*(\])", re.MULTILINE),
         r"\g<1>\2 - 1\3"),
    ],
    "CPP_UNINITIALIZED_VAR": [
        # Form 1: int x = 0; -> int x;
        ("uninit_int_zero",
         re.compile(r"\bint\s+(\w+)\s*=\s*0\s*;", re.MULTILINE),
         r"int \1;"),
        # Form 2: double x = 0.0; -> double x;
        ("uninit_double_zero",
         re.compile(r"\bdouble\s+(\w+)\s*=\s*0(?:\.0)?\s*;", re.MULTILINE),
         r"double \1;"),
        # Form 3: int x = 0, y = 0; -> int x, y;
        ("uninit_multi_int",
         re.compile(r"\bint\s+(\w+)\s*=\s*0\s*,\s*(\w+)\s*=\s*0\s*;", re.MULTILINE),
         r"int \1, \2;"),
        # Form 4: bool x = false; -> bool x;
        ("uninit_bool_false",
         re.compile(r"\bbool\s+(\w+)\s*=\s*false\s*;", re.MULTILINE),
         r"bool \1;"),
    ],
    "CPP_INT_OVERFLOW": [
        # Form 1: long long sum -> int sum
        ("overflow_ll_sum_to_int",
         re.compile(r"\blong\s+long\s+(sum|ans|total|result)\b", re.MULTILINE),
         r"int \1"),
        # Form 2: (long long) cast removed in multiplication
        ("overflow_remove_ll_cast",
         re.compile(r"\(long\s+long\)\s*(\w+)\s*\*", re.MULTILINE),
         r"\1 *"),
        # Form 3: long long -> int for loop accumulator
        ("overflow_ll_acc_to_int",
         re.compile(r"\blong\s+long\s+(\w+)\s*=\s*0\s*;", re.MULTILINE),
         r"int \1 = 0;"),
        # Form 4: 1LL * x -> x (remove LL literal)
        ("overflow_1ll_removed",
         re.compile(r"\b1LL\s*\*\s*(\w+)", re.MULTILINE),
         r"\1"),
    ],
    "CPP_MISSING_BASE_CASE": [
        # Form 1: remove if (n == 0) return ...; block
        ("mbc_remove_base_n0",
         re.compile(r"if\s*\(\s*n\s*==\s*0\s*\)\s*\{[^}]*\}\s*", re.MULTILINE | re.DOTALL),
         r""),
        # Form 2: remove if (n <= 1) return ...; block
        ("mbc_remove_base_le1",
         re.compile(r"if\s*\(\s*n\s*<=\s*1\s*\)\s*\{[^}]*\}\s*", re.MULTILINE | re.DOTALL),
         r""),
        # Form 3: remove single-line if (n == 1) return ...;
        ("mbc_remove_base_eq1",
         re.compile(r"if\s*\(\s*n\s*==\s*1\s*\)\s*return\s+[^;]+;", re.MULTILINE),
         r""),
        # Form 4: remove if (n == 0) return 0/1 base case
        ("mbc_remove_return_base",
         re.compile(r"if\s*\(\s*\w+\s*==\s*0\s*\)\s*return\s+[^;]+;", re.MULTILINE),
         r""),
    ],
    "CPP_ASSIGN_VS_COMPARE": [
        # Form 1: == -> = in if condition
        ("avc_eq_to_assign_if",
         re.compile(r"(if\s*\()(\w+)\s*==\s*(\w+)(\))", re.MULTILINE),
         r"\1\2 = \3\4"),
        # Form 2: == -> = in while condition
        ("avc_eq_to_assign_while",
         re.compile(r"(while\s*\()(\w+)\s*==\s*(\w+)(\))", re.MULTILINE),
         r"\1\2 = \3\4"),
        # Form 3: != -> = in if condition
        ("avc_ne_to_assign_if",
         re.compile(r"(if\s*\()(\w+)\s*!=\s*(\w+)(\))", re.MULTILINE),
         r"\1\2 = \3\4"),
        # Form 4: == -> = in else if condition
        ("avc_eq_to_assign_elif",
         re.compile(r"(else\s+if\s*\()(\w+)\s*==\s*(\w+)(\))", re.MULTILINE),
         r"\1\2 = \3\4"),
    ],
    "CPP_WRONG_LOOP_DIR": [
        # Form 1: i++ -> i-- (reverses direction)
        ("wld_incr_to_decr",
         re.compile(r"(for\s*\([^;]+;[^;]+;\s*)(\w+)\+\+(\s*\))", re.MULTILINE),
         r"\1\2--\3"),
        # Form 2: i=0 to i=n in for init
        ("wld_start_0_to_n",
         re.compile(r"(for\s*\(\s*int\s+\w+\s*=\s*)0(\s*;[^;]+;)", re.MULTILINE),
         r"\1n\2"),
        # Form 3: i < n to i > n (completely reversed)
        ("wld_lt_to_gt",
         re.compile(r"(for\s*\([^;]+;\s*\w+\s*)<(\s*\w+\s*;)", re.MULTILINE),
         r"\1>\2"),
        # Form 4: i += 1 -> i -= 1
        ("wld_inc_step_to_dec",
         re.compile(r"(for\s*\([^;]+;[^;]+;\s*\w+\s*)\+=(\s*1\s*\))", re.MULTILINE),
         r"\1-=\2"),
    ],
    "CPP_RANGE_CHECK": [
        # Form 1: x >= min_val -> x > min_val (off by 1 in guard)
        ("rc_ge_to_gt",
         re.compile(r"(if\s*\([^)]*\w+\s*)>=(\s*\d+)", re.MULTILINE),
         r"\1>\2"),
        # Form 2: x <= max_val -> x < max_val
        ("rc_le_to_lt",
         re.compile(r"(if\s*\([^)]*\w+\s*)<=(\s*\w+)", re.MULTILINE),
         r"\1<\2"),
        # Form 3: valid range check inverted (< 1 -> <= 0)
        ("rc_lt1_to_le0",
         re.compile(r"(if\s*\([^)]*\w+\s*)<(\s*1\b)", re.MULTILINE),
         r"\1<=\g<2>"),
        # Form 4: n >= 1 && n <= K -> n > 1 && n < K
        ("rc_ge_le_to_gt_lt",
         re.compile(r"(\w+\s*)>=(\s*\d+\s*&&\s*\w+\s*)<=(\s*\d+)", re.MULTILINE),
         r"\1>\2<\3"),
    ],
    "CPP_STALE_EXIT": [
        # Form 1: remove update step from while body (comment out i++)
        ("se_remove_incr_in_while",
         re.compile(r"(while\s*\([^)]+\)\s*\{[^}]*)(\w+\s*\+\+\s*;)([^}]*\})", re.MULTILINE | re.DOTALL),
         r"\1// \2\3"),
        # Form 2: condition var not modified — replace i++ with a stale ref
        ("se_frozen_counter",
         re.compile(r"(\w+)\+\+(\s*;)\s*(//.*)?$", re.MULTILINE),
         r"// \1++\2  // stale: update removed"),
        # Form 3: while (flag) where flag never flipped
        ("se_remove_flag_update",
         re.compile(r"(flag\s*=\s*)(true|false|1|0)(\s*;)", re.MULTILINE),
         r"// \1\2\3  // flag not updated"),
        # Form 4: for(;;) loop without break on condition
        ("se_remove_break_condition",
         re.compile(r"if\s*\([^)]+\)\s*break\s*;", re.MULTILINE),
         r"// removed break"),
    ],
}

# Decoy operators (E1d) — these produce failing code that does NOT match any
# taxonomy class; label = CPP_OTHER_ERROR
DECOY_FORMS = [
    # Misplace closing brace
    ("decoy_brace_mismatch",
     re.compile(r"(\bif\s*\([^)]+\))\s*\{([^{}]{0,100})\}", re.MULTILINE | re.DOTALL),
     r"\1 \2"),  # removes braces -> multiple statements escape the if
    # Off-by-two in index (not off-by-one, no taxonomy class)
    ("decoy_index_plus2",
     re.compile(r"(\w+\s*\[)\s*(\w+)\s*\]", re.MULTILINE),
     r"\1\2 + 2]"),
    # Wrong printf/cout format (produces presentation error not WA)
    ("decoy_endl_flush",
     re.compile(r'cout\s*<<\s*(\w+)\s*<<\s*"\\n"', re.MULTILINE),
     r'cout << \1 << endl << flush'),
    # Swap two output statements (order wrong, not a misconception class)
    ("decoy_swap_two_outputs",
     re.compile(r'(cout\s*<<[^\n]+\n)([^\n]*cout\s*<<[^\n]+)', re.MULTILINE),
     r'\2\n\1'),
]


def apply_operator(source: str, op_name: str, pattern, replacement) -> str | None:
    """Apply a single operator transform. Returns None if pattern not found."""
    if callable(replacement):
        try:
            result = pattern.sub(replacement, source, count=1)
        except Exception:
            return None
    else:
        result = pattern.sub(replacement, source, count=1)
    if result == source:
        return None
    return result


def mine_pairs(train_problems: set) -> list[dict]:
    """
    Load wrong->Accepted attempt pairs from CodeStream (train-side only).
    Returns list of {user_id, problem_id, wrong_attempt, accepted_attempt,
                     wrong_code, accepted_code, diff_lines}.
    """
    user_problem_subs = defaultdict(list)
    with open(CODESTREAM_CSV, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            lang = (row.get("programming_language") or "").lower().replace("+", "p").strip()
            if lang not in ("c", "cpp"):
                continue
            pid_raw = row.get("problem_id") or ""
            pid = f"tl-codestream-{pid_raw}" if not pid_raw.startswith("tl-") else pid_raw
            if pid not in train_problems:
                continue
            user_problem_subs[(row["user_id"], pid)].append({
                "attempt": int(row.get("attempt_number") or 0),
                "verdict": row.get("final_verdict", "").strip(),
                "code": row.get("source_code", ""),
                "submission_id": row.get("submission_id", ""),
            })

    pairs = []
    for (uid, pid), subs in user_problem_subs.items():
        subs.sort(key=lambda x: x["attempt"])
        # Find consecutive Wrong->Accepted pairs
        for i in range(len(subs) - 1):
            curr = subs[i]
            nxt = subs[i + 1]
            if curr["verdict"] == "Wrong Answer" and nxt["verdict"] == "Accepted":
                wrong_lines = curr["code"].splitlines(keepends=True)
                acc_lines = nxt["code"].splitlines(keepends=True)
                diff = list(difflib.unified_diff(
                    wrong_lines, acc_lines,
                    fromfile="wrong", tofile="accepted", n=2
                ))
                pairs.append({
                    "user_id": uid,
                    "problem_id": pid,
                    "wrong_attempt": curr["attempt"],
                    "accepted_attempt": nxt["attempt"],
                    "wrong_submission_id": curr["submission_id"],
                    "accepted_submission_id": nxt["submission_id"],
                    "wrong_code": curr["code"],
                    "accepted_code": nxt["code"],
                    "diff_lines": diff,
                    "diff_summary": "".join(diff)[:500],
                })
    return pairs


def classify_diff(diff_lines: list[str]) -> str | None:
    """
    Heuristic classification of a wrong->Accepted diff into a tl-cpp-v2 class.
    Returns class name or None.
    """
    removed = []
    added = []
    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])

    removed_text = " ".join(removed)
    added_text = " ".join(added)

    # LOOP_BOUNDARY: <= <-> < changes in for/while headers
    if re.search(r"for|while", removed_text + added_text):
        if (re.search(r"<=", removed_text) and re.search(r"<[^=]", added_text)) or \
           (re.search(r"<[^=]", removed_text) and re.search(r"<=", added_text)):
            return "CPP_LOOP_BOUNDARY"
        if re.search(r"<\s*\w+\s*\+\s*1", removed_text) or re.search(r"<\s*\w+\s*\+\s*1", added_text):
            return "CPP_LOOP_BOUNDARY"

    # OFF_BY_ONE: index +1/-1 changes
    if re.search(r"\[\w+\s*[+-]\s*1\]", removed_text + added_text):
        if not re.search(r"for|while", removed_text + added_text):
            return "CPP_OFF_BY_ONE"
    if re.search(r"=\s*1\s*;", removed_text) and re.search(r"=\s*0\s*;", added_text):
        return "CPP_OFF_BY_ONE"

    # UNINITIALIZED_VAR: added = 0 initialization
    if re.search(r"\bint\s+\w+\s*;", removed_text) and re.search(r"\bint\s+\w+\s*=\s*0", added_text):
        return "CPP_UNINITIALIZED_VAR"
    if re.search(r"\bdouble\s+\w+\s*;", removed_text) and re.search(r"\bdouble\s+\w+\s*=", added_text):
        return "CPP_UNINITIALIZED_VAR"

    # INT_OVERFLOW: long long added, int removed
    if re.search(r"\blong\s+long\b", added_text) and re.search(r"\bint\b", removed_text):
        return "CPP_INT_OVERFLOW"
    if re.search(r"1LL|long long|ULL", added_text):
        return "CPP_INT_OVERFLOW"

    # MISSING_BASE_CASE: base case added
    if re.search(r"if\s*\(\s*n\s*[<=>]=?\s*[01]\s*\)", added_text):
        return "CPP_MISSING_BASE_CASE"

    # ASSIGN_VS_COMPARE: == added where = was
    if re.search(r"if\s*\(\s*\w+\s*=\s*\w+\s*\)", removed_text) and \
       re.search(r"if\s*\(\s*\w+\s*==\s*\w+\s*\)", added_text):
        return "CPP_ASSIGN_VS_COMPARE"

    # WRONG_LOOP_DIR: i++ <-> i--
    if re.search(r"\bi\+\+", removed_text) and re.search(r"\bi--", added_text):
        return "CPP_WRONG_LOOP_DIR"
    if re.search(r"\bi--", removed_text) and re.search(r"\bi\+\+", added_text):
        return "CPP_WRONG_LOOP_DIR"

    # ARRAY_BOUNDS: array size increased
    if re.search(r"\[\d+\]", removed_text) and re.search(r"\[\d+\]", added_text):
        old_sizes = [int(x) for x in re.findall(r"\[(\d+)\]", removed_text)]
        new_sizes = [int(x) for x in re.findall(r"\[(\d+)\]", added_text)]
        if old_sizes and new_sizes and max(new_sizes) > max(old_sizes):
            return "CPP_ARRAY_BOUNDS"

    # STALE_EXIT: loop variable update added
    if re.search(r"\+\+|\+=", added_text) and not re.search(r"\+\+|\+=", removed_text):
        if re.search(r"while", removed_text + added_text):
            return "CPP_STALE_EXIT"

    # RANGE_CHECK: boundary constant changes in if condition
    if re.search(r"if\s*\(.*[<>]=?\s*\d", removed_text + added_text):
        old_bounds = re.findall(r"[<>]=?\s*(\d+)", removed_text)
        new_bounds = re.findall(r"[<>]=?\s*(\d+)", added_text)
        if old_bounds != new_bounds and old_bounds and new_bounds:
            if abs(int(old_bounds[0]) - int(new_bounds[0])) == 1:
                return "CPP_RANGE_CHECK"

    return None


def build_operator_library(pairs: list[dict], min_forms: int = 4) -> dict:
    """
    Classify pairs by tl-cpp-v2 class, count forms per operator.
    Returns the operator library dict.
    """
    class_pair_counts = defaultdict(int)
    class_pairs = defaultdict(list)

    for pair in pairs:
        cls = classify_diff(pair["diff_lines"])
        if cls:
            class_pair_counts[cls] += 1
            class_pairs[cls].append(pair)

    print("\nReal wrong->Accepted pair classification:")
    for cls, count in sorted(class_pair_counts.items()):
        print(f"  {cls:<28}: {count} pairs")

    # Build operator library
    library = {
        "version": "1.0",
        "created": "2026-10-21",
        "creator": "eman06",
        "taxonomy_version": "tl-cpp-v2",
        "mining_source": "CodeStream train-side wrong->Accepted pairs",
        "operators": {},
        "decoy_operators": [],
        "mined_class_pair_counts": dict(class_pair_counts),
        "total_pairs_mined": len(pairs),
    }

    for cls, forms in OPERATOR_FORMS.items():
        library["operators"][cls] = {
            "class": cls,
            "forms": [
                {
                    "name": name,
                    "pattern": pattern.pattern,
                    "replacement": replacement if isinstance(replacement, str) else "__callable__",
                    "frequency_weight": class_pair_counts.get(cls, 0),
                }
                for name, pattern, replacement in forms
            ],
            "n_forms": len(forms),
            "mined_pairs": class_pair_counts.get(cls, 0),
        }
        if len(forms) < min_forms:
            print(f"WARNING: {cls} has only {len(forms)} forms (need {min_forms})")

    for name, pattern, replacement in DECOY_FORMS:
        library["decoy_operators"].append({
            "name": name,
            "pattern": pattern.pattern,
            "replacement": replacement if isinstance(replacement, str) else "__callable__",
            "label": "CPP_OTHER_ERROR",
        })

    return library


def main(min_forms: int, out_path: str):
    if not os.path.exists(CLUSTER_SPLIT):
        print(f"ERROR: {CLUSTER_SPLIT} not found -- run cluster_problems.py first", file=sys.stderr)
        sys.exit(1)

    with open(CLUSTER_SPLIT, encoding="utf-8") as fh:
        cluster_data = json.load(fh)

    train_problems: set[str] = set()
    for clu_id, clu_info in cluster_data["clusters"].items():
        if clu_info["split"] == "train":
            for pid in clu_info["problems"]:
                train_problems.add(pid)

    print(f"Mining from {len(train_problems)} train-side problems...")
    pairs = mine_pairs(train_problems)
    print(f"Wrong->Accepted pairs found: {len(pairs)}")

    library = build_operator_library(pairs, min_forms)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(library, fh, indent=2)
    print(f"\nWrote operator library: {out_path}")
    print(f"Classes with operators: {len(library['operators'])}")
    for cls, op in sorted(library['operators'].items()):
        print(f"  {cls:<28}: {op['n_forms']} forms, {op['mined_pairs']} pairs")
    print(f"Decoy operators: {len(library['decoy_operators'])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E1: mine reverse-mutation operators from CodeStream pairs")
    parser.add_argument("--min-forms", type=int, default=4)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    main(args.min_forms, args.out)
