"""Generate the C++ misconception diagnostic test cases.

This script writes the test side of the C++ diagnostic bank. It writes no
reference solution. The reference solutions live in `data/cpp_problems/solutions`.

Rules:
1. Every expected output comes from an independent Python model. The model is
   separate from the C++ reference solution. Thus the expected output is not
   circular.
2. Every test file is normalized. It uses Unix `\n` endings, it carries no
   trailing whitespace, and it ends with exactly one newline.
3. Tests are partitioned into `tests/public/` and `tests/hidden/`. Diagnostic
   tests sit in `tests/hidden/`. A student must not see them.
4. The script is deterministic. Two runs produce byte-identical files.

Usage (from the repository root):

    python scripts/build_cpp_tests.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "cpp_problems"

# Sandbox limits that every test case must record. The judge uses these values.
TIME_LIMIT_MS = 2000
MEMORY_LIMIT_MB = 256

# Taxonomy version that this bank targets. See docs/TAXONOMY.md.
TAXONOMY_VERSION = "cpp-taxonomy-0.1"


# ---------------------------------------------------------------------------
# independent expected-output models (one per problem)
# ---------------------------------------------------------------------------
def _m01(args: dict) -> str:
    """Sum of the integers 0 .. n-1. The upper bound is exclusive."""
    n = args["n"]
    return str(sum(range(n)))


def _m02(args: dict) -> str:
    """Largest value in the list. It is not the position of the largest value."""
    vals = args["vals"]
    if not vals:
        return "NONE"
    return str(max(vals))


def _m03(args: dict) -> str:
    """Value received from the return channel of twice(x), plus one."""
    x = args["x"]
    return str(2 * x + 1)


def _m04(args: dict) -> str:
    """Last element of the list. Index size() is never valid."""
    vals = args["vals"]
    if not vals:
        return "EMPTY"
    return str(vals[-1])


def _m05(args: dict) -> str:
    """Mathematical range check 1 <= x <= 10."""
    x = args["x"]
    return "IN" if (1 <= x and x <= 10) else "OUT"


def _m06(args: dict) -> str:
    """Equality test against zero."""
    x = args["x"]
    return "ZERO" if x == 0 else "NONZERO"


def _m07(args: dict) -> str:
    """Factorial of n, computed by recursion."""
    n = args["n"]
    result = 1
    for i in range(2, n + 1):
        result *= i
    return str(result)


def _m08(args: dict) -> str:
    """First position of the target, or NOT FOUND."""
    vals, target = args["vals"], args["target"]
    for i, v in enumerate(vals):
        if v == target:
            return str(i)
    return "NOT FOUND"


# ---------------------------------------------------------------------------
# test-case definitions
# ---------------------------------------------------------------------------
# kind: "public" (the student can see it), "hidden", or "diagnostic".
# A "boundary" flag marks the test that probes a limit of the input range.
PROBLEMS: list[dict] = [
    {
        "id": "CP01",
        "slug": "m01_sum_first_n",
        "title": "Sum First N (Exclusive Bound)",
        "misconception": "CPP-M01",
        "secondary": ["CPP-M08"],
        "model": _m01,
        "statement": (
            "Read one integer n. Print the sum of the integers 0, 1, 2, ... , n-1. "
            "The upper bound n is exclusive. For n = 0 the range is empty and the sum is 0."
        ),
        "input_spec": "One line that holds one integer n.",
        "output_spec": "One line that holds one integer: the sum.",
        "constraints": "0 <= n <= 1000",
        "starter_code": (
            "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
        ),
        "cases": [
            {"kind": "public", "n": 5},
            {"kind": "public", "n": 1},
            {"kind": "public", "n": 0, "boundary": True},
            {"kind": "hidden", "n": 100},
            {"kind": "hidden", "n": 1000},
            {"kind": "hidden", "n": 37},
            {"kind": "diagnostic", "tag": "upper_boundary", "n": 0},
            {"kind": "diagnostic", "tag": "upper_boundary", "n": 1},
            {"kind": "diagnostic", "tag": "upper_boundary", "n": 9},
        ],
    },
    {
        "id": "CP02",
        "slug": "m02_max_value_not_index",
        "title": "Largest Value, Not Position",
        "misconception": "CPP-M02",
        "secondary": ["CPP-M01"],
        "model": _m02,
        "statement": (
            "Read n and then n integers. Print the largest value. "
            "If n = 0, print NONE. Print the value, not its position."
        ),
        "input_spec": "Line 1 holds n. Line 2 holds n integers separated by spaces.",
        "output_spec": "One line that holds the largest value, or NONE.",
        "constraints": "0 <= n <= 1000. Each value is between -1000000 and 1000000.",
        "starter_code": (
            "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
        ),
        "cases": [
            {"kind": "public", "vals": [7, 3, 9]},
            {"kind": "public", "vals": [-5, -9, -2, -4, -8]},
            {"kind": "public", "vals": [4, 4, 4, 4], "boundary": True},
            {"kind": "hidden", "vals": [42]},
            {"kind": "hidden", "vals": [1000000, 999999, 1, -1000000, 7, 0]},
            {"kind": "hidden", "vals": [0] * 7},
            {"kind": "hidden", "vals": [], "boundary": True},
            {"kind": "diagnostic", "tag": "value_not_index", "vals": [7, 3, 9]},
            {"kind": "diagnostic", "tag": "duplicate_values", "vals": [5, 5, 5]},
            {"kind": "diagnostic", "tag": "value_not_index", "vals": [-1, -1]},
        ],
    },
    {
        "id": "CP03",
        "slug": "m03_return_contract",
        "title": "Return, Do Not Print",
        "misconception": "CPP-M03",
        "secondary": [],
        "model": _m03,
        "statement": (
            "Write a function int twice(int x) that returns x * 2. The function "
            "must return the value. It must not print the value. Your main reads "
            "x and prints twice(x) + 1."
        ),
        "input_spec": "One line that holds one integer x.",
        "output_spec": "One line that holds one integer.",
        "constraints": "-1000000 <= x <= 1000000",
        "starter_code": (
            "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
        ),
        "cases": [
            {"kind": "public", "x": 4},
            {"kind": "public", "x": 0, "boundary": True},
            {"kind": "public", "x": 10},
            {"kind": "hidden", "x": 1},
            {"kind": "hidden", "x": 25},
            {"kind": "hidden", "x": -7},
            {"kind": "diagnostic", "tag": "return_channel", "x": 4},
            {"kind": "diagnostic", "tag": "return_channel", "x": 0},
            {"kind": "diagnostic", "tag": "return_channel", "x": 7},
        ],
    },
    {
        "id": "CP04",
        "slug": "m04_last_element",
        "title": "Last Element Of A Vector",
        "misconception": "CPP-M04",
        "secondary": ["CPP-M01"],
        "model": _m04,
        "statement": (
            "Read n and then n integers. Print the last element. "
            "If n = 0, print EMPTY. The index size() is never a valid index."
        ),
        "input_spec": "Line 1 holds n. Line 2 holds n integers separated by spaces.",
        "output_spec": "One line that holds the last element, or EMPTY.",
        "constraints": "0 <= n <= 1000. Each value is between -1000000 and 1000000.",
        "starter_code": (
            "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
        ),
        "cases": [
            {"kind": "public", "vals": [10, 20, 30, 40, 50]},
            {"kind": "public", "vals": [7], "boundary": True},
            {"kind": "public", "vals": [], "boundary": True},
            {"kind": "hidden", "vals": [1, 2, 3, 4]},
            {"kind": "hidden", "vals": [5, 4, 3, 2, 1, 0]},
            {"kind": "hidden", "vals": [-1, -2, -3]},
            {"kind": "diagnostic", "tag": "size_zero", "vals": []},
            {"kind": "diagnostic", "tag": "size_one", "vals": [99]},
            {"kind": "diagnostic", "tag": "last_valid_index", "vals": [10, 20, 30, 40, 50]},
        ],
    },
    {
        "id": "CP05",
        "slug": "m05_range_check",
        "title": "Range Check 1 To 10",
        "misconception": "CPP-M05",
        "secondary": ["CPP-M06"],
        "model": _m05,
        "statement": (
            "Read one integer x. Print IN when x is inside the closed range 1 to 10. "
            "Print OUT otherwise. Use an explicit conjunction of two comparisons."
        ),
        "input_spec": "One line that holds one integer x.",
        "output_spec": "One line that holds IN or OUT.",
        "constraints": "-1000000 <= x <= 1000000",
        "starter_code": (
            "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
        ),
        "cases": [
            {"kind": "public", "x": 5},
            {"kind": "public", "x": 0, "boundary": True},
            {"kind": "public", "x": 10},
            {"kind": "hidden", "x": 1},
            {"kind": "hidden", "x": 11},
            {"kind": "hidden", "x": -5},
            {"kind": "hidden", "x": 100},
            {"kind": "hidden", "x": -1},
            {"kind": "diagnostic", "tag": "lower_bound", "x": 1},
            {"kind": "diagnostic", "tag": "upper_bound", "x": 10},
            {"kind": "diagnostic", "tag": "above_range", "x": 11},
            {"kind": "diagnostic", "tag": "below_range", "x": -5},
        ],
    },
    {
        "id": "CP06",
        "slug": "m06_zero_test",
        "title": "Zero Or Not Zero",
        "misconception": "CPP-M06",
        "secondary": ["CPP-M05"],
        "model": _m06,
        "statement": (
            "Read one integer x. Print ZERO when x equals 0. "
            "Print NONZERO otherwise. Compare the values. Do not assign."
        ),
        "input_spec": "One line that holds one integer x.",
        "output_spec": "One line that holds ZERO or NONZERO.",
        "constraints": "-1000000 <= x <= 1000000",
        "starter_code": (
            "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
        ),
        "cases": [
            {"kind": "public", "x": 0, "boundary": True},
            {"kind": "public", "x": 7},
            {"kind": "public", "x": -3},
            {"kind": "hidden", "x": 1},
            {"kind": "hidden", "x": 0},
            {"kind": "hidden", "x": 42},
            {"kind": "hidden", "x": -1},
            {"kind": "diagnostic", "tag": "zero_input", "x": 0},
            {"kind": "diagnostic", "tag": "nonzero_input", "x": 5},
        ],
    },
    {
        "id": "CP07",
        "slug": "m07_factorial",
        "title": "Factorial By Recursion",
        "misconception": "CPP-M07",
        "secondary": ["CPP-M08"],
        "model": _m07,
        "statement": (
            "Read one integer n. Print n factorial. Use a recursive function "
            "long long factorial(int n). Each recursive call must approach the "
            "base case n <= 1."
        ),
        "input_spec": "One line that holds one integer n.",
        "output_spec": "One line that holds one integer.",
        "constraints": "0 <= n <= 20",
        "starter_code": (
            "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
        ),
        "cases": [
            {"kind": "public", "n": 0, "boundary": True},
            {"kind": "public", "n": 5},
            {"kind": "public", "n": 1, "boundary": True},
            {"kind": "hidden", "n": 10},
            {"kind": "hidden", "n": 20},
            {"kind": "hidden", "n": 3},
            {"kind": "diagnostic", "tag": "base_case", "n": 0},
            {"kind": "diagnostic", "tag": "one_step", "n": 1},
            {"kind": "diagnostic", "tag": "several_steps", "n": 6},
        ],
    },
    {
        "id": "CP08",
        "slug": "m08_search_exit",
        "title": "First Position Of A Target",
        "misconception": "CPP-M08",
        "secondary": ["CPP-M04"],
        "model": _m08,
        "statement": (
            "Read n, then n integers, then one target value t. Print the "
            "0-based position of the first value that equals t. If t is absent, "
            "print NOT FOUND. The search loop must stop when the list ends."
        ),
        "input_spec": (
            "Line 1 holds n. Line 2 holds n integers. Line 3 holds the target t."
        ),
        "output_spec": "One line that holds a position, or NOT FOUND.",
        "constraints": "1 <= n <= 1000. Each value is between -1000000 and 1000000.",
        "starter_code": (
            "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"
        ),
        "cases": [
            {"kind": "public", "vals": [10, 20, 30, 40, 50], "target": 30},
            {"kind": "public", "vals": [1, 2, 3, 4], "target": 9, "boundary": True},
            {"kind": "public", "vals": [8], "target": 8, "boundary": True},
            {"kind": "hidden", "vals": [5, 5, 5, 5, 5], "target": 5},
            {"kind": "hidden", "vals": [1, 2, 3, 4, 5, 6], "target": 6},
            {"kind": "hidden", "vals": [-1, -2, -3], "target": -3},
            {"kind": "hidden", "vals": [7, 8], "target": 100},
            {"kind": "diagnostic", "tag": "immediate_find", "vals": [10, 20, 30, 40, 50], "target": 10},
            {"kind": "diagnostic", "tag": "absent_target", "vals": [10, 20, 30, 40, 50], "target": 99},
            {"kind": "diagnostic", "tag": "last_index", "vals": [1, 2, 3, 4, 5, 6], "target": 6},
        ],
    },
]


# ---------------------------------------------------------------------------
# stdin rendering and normalization
# ---------------------------------------------------------------------------
def render_stdin(problem: dict, args: dict) -> str:
    """Return the stdin text for one test case."""
    pid = problem["id"]
    if pid == "CP01":
        return f"{args['n']}\n"
    if pid == "CP02":
        vals = " ".join(str(v) for v in args["vals"])
        return f"{len(args['vals'])}\n{vals}\n" if vals else "0\n\n"
    if pid == "CP03":
        return f"{args['x']}\n"
    if pid == "CP04":
        vals = " ".join(str(v) for v in args["vals"])
        return f"{len(args['vals'])}\n{vals}\n" if vals else "0\n\n"
    if pid == "CP05":
        return f"{args['x']}\n"
    if pid == "CP06":
        return f"{args['x']}\n"
    if pid == "CP07":
        return f"{args['n']}\n"
    if pid == "CP08":
        vals = " ".join(str(v) for v in args["vals"])
        return f"{len(args['vals'])}\n{vals}\n{args['target']}\n"
    raise ValueError(f"no stdin renderer for {pid}")


def normalize(text: str) -> str:
    """Return text with Unix endings, no trailing whitespace, one final newline."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def case_id(problem_id: str, kind: str, index: int) -> str:
    """Return the test-case id. V is visible, H is hidden, D is diagnostic."""
    letter = {"public": "V", "hidden": "H", "diagnostic": "D"}[kind]
    return f"{problem_id}-{letter}{index}"


def kind_dir(kind: str) -> str:
    """Return the test folder for a test kind. Diagnostic tests are hidden."""
    return "public" if kind == "public" else "hidden"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def build() -> dict:
    """Write every test file and the problem manifest. Return a summary."""
    problems_payload: list[dict] = []
    test_files: list[dict] = []
    counters: dict[str, dict[str, int]] = {}

    for problem in PROBLEMS:
        pid = problem["id"]
        counters[pid] = {"public": 0, "hidden": 0, "diagnostic": 0}
        cases_payload: list[dict] = []
        sort_order = 0

        for case in problem["cases"]:
            kind = case["kind"]
            counters[pid][kind] += 1
            args = {k: v for k, v in case.items() if k not in ("kind", "tag", "boundary")}
            stdin_text = normalize(render_stdin(problem, args))
            expected = normalize(problem["model"](args))
            index = counters[pid][kind]
            cid = case_id(pid, kind, index)
            sort_order += 1

            folder = OUT_DIR / "tests" / kind_dir(kind) / pid
            folder.mkdir(parents=True, exist_ok=True)
            in_path = folder / f"{index:02d}.in"
            out_path = folder / f"{index:02d}.out"
            in_path.write_bytes(stdin_text.encode("utf-8"))
            out_path.write_bytes(expected.encode("utf-8"))

            test_files.append({
                "test_case_id": cid,
                "problem_id": pid,
                "misconception": problem["misconception"],
                "test_type": kind,
                "partition": kind_dir(kind),
                "boundary": bool(case.get("boundary", False)),
                "diagnostic_tag": case.get("tag"),
                "input_path": str(in_path.relative_to(OUT_DIR)).replace("\\", "/"),
                "expected_path": str(out_path.relative_to(OUT_DIR)).replace("\\", "/"),
                "sha256_input": sha256(in_path),
                "sha256_expected": sha256(out_path),
                "time_limit_ms": TIME_LIMIT_MS,
                "memory_limit_mb": MEMORY_LIMIT_MB,
                "sort_order": sort_order,
            })

            entry: dict = {
                "id": cid,
                "name": _case_name(kind, case),
                "test_type": kind,
                "input_json": {"stdin": stdin_text},
                "expected_output_json": expected,
                "sort_order": sort_order,
                "time_limit_ms": TIME_LIMIT_MS,
                "memory_limit_mb": MEMORY_LIMIT_MB,
            }
            if case.get("tag"):
                entry["diagnostic_tag"] = case["tag"]
            if case.get("boundary"):
                entry["is_boundary"] = True
            cases_payload.append(entry)

        problems_payload.append({
            "id": pid,
            "slug": problem["slug"],
            "title": problem["title"],
            "description": problem["statement"],
            "function_name": "main",
            "concept_tags": ["cpp", "diagnostics", problem["misconception"].lower()],
            "prerequisite_tags": ["cpp17", "stdin-stdout"],
            "starter_code": problem["starter_code"],
            "designed_misconception": problem["misconception"],
            "secondary_misconceptions": problem["secondary"],
            "language": "cpp",
            "language_standard": "cpp17",
            "topic": "Diagnostics",
            "difficulty": "Easy",
            "input_spec": problem["input_spec"],
            "output_spec": problem["output_spec"],
            "constraints": problem["constraints"],
            "reference_solution": f"solutions/{pid}.cpp",
            "taxonomy_version": TAXONOMY_VERSION,
            "test_cases": cases_payload,
        })

    manifest = {
        "bank": "cpp_diagnostics",
        "taxonomy_version": TAXONOMY_VERSION,
        "problem_count": len(problems_payload),
        "test_case_count": len(test_files),
        "time_limit_ms": TIME_LIMIT_MS,
        "memory_limit_mb": MEMORY_LIMIT_MB,
        "line_endings": "LF",
        "tests": test_files,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "problems.json").write_text(
        json.dumps({"problems": problems_payload}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    (OUT_DIR / "tests" / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    return {
        "problems": len(problems_payload),
        "test_cases": len(test_files),
        "public": sum(c["public"] for c in counters.values()),
        "hidden": sum(c["hidden"] for c in counters.values()),
        "diagnostic": sum(c["diagnostic"] for c in counters.values()),
    }


def _case_name(kind: str, case: dict) -> str:
    """Return a short human-readable test name."""
    label = {"public": "visible", "hidden": "hidden", "diagnostic": "diagnostic"}[kind]
    detail = case.get("tag") or ""
    if not detail:
        args = [k for k in case if k not in ("kind", "tag", "boundary")]
        detail = " ".join(args) if args else "case"
    return f"{label} {detail}"


def main() -> int:
    summary = build()
    print("C++ diagnostic tests written:", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
