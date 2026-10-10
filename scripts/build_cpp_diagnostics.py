"""Build the unified C++ diagnostic bank.

This script reads the problem definitions from `scripts/cpp_defs` and merges
them with the first eight problems in `data/cpp_problems`. It writes one
self-contained data file for the seeder. It also writes the reference
solutions, the test files, and the misconception variants.

Output layout:

```
data/cpp_diagnostics/
├── problems.json                 ← 40 problems, test cases and hints
├── manifest.json                 ← counts, checksums, limits
├── solutions/CPnn.cpp            ← reference solution source
├── tests/public/<CPnn>/NN.in     ← visible input
├── tests/public/<CPnn>/NN.out    ← visible expected output
├── tests/hidden/<CPnn>/NN.in     ← hidden and diagnostic input
├── tests/hidden/<CPnn>/NN.out    ← hidden and diagnostic expected output
└── variants/CPnn__CPP-M0X_a.cpp  ← misconception variant
```

Rules:

1. Every expected output comes from a Python model in the definition. The
   model is separate from the C++ reference solution.
2. Every test file is normalized. It uses Unix LF endings. It holds no
   trailing whitespace. It ends with exactly one newline.
3. The file number `NN` is the global order of the test inside its problem.
4. A diagnostic test always lives in the `hidden` partition.
5. The script is deterministic. Two runs produce byte-identical files.

Usage (from the repository root):

    python scripts/build_cpp_diagnostics.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from cpp_defs import ALL_PROBLEMS  # noqa: E402

OUT_DIR = ROOT / "data" / "cpp_diagnostics"
OLD_BANK = ROOT / "data" / "cpp_problems"

TAXONOMY_VERSION = "cpp-taxonomy-0.1"
TIME_LIMIT_MS = 2000
MEMORY_LIMIT_MB = 256
STANDARD = "cpp17"

# The kind letter in a test-case id. V is visible, H is hidden, D is
# diagnostic.
KIND_LETTER = {"public": "V", "hidden": "H", "diagnostic": "D"}

# A definition may name a public case `public` or `visible`. Both names are
# accepted here. Everything downstream uses `public`.
KIND_ALIAS = {"public": "public", "visible": "public",
              "hidden": "hidden", "diagnostic": "diagnostic"}

# The database `test_cases.test_type` enum value for each kind.
KIND_DB_TYPE = {"public": "visible", "hidden": "hidden", "diagnostic": "diagnostic"}

KIND_PARTITION = {"public": "public", "hidden": "hidden", "diagnostic": "hidden"}

DIFFICULTY_ORDER = {"Beginner": 1, "Intermediate": 2}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def normalize(text: str) -> str:
    """Return text with LF endings, no trailing whitespace, one final newline."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_examples(examples: list[dict]) -> str:
    """Return the examples as a markdown block for the problem description."""
    lines = ["", "## Examples", ""]
    for index, example in enumerate(examples, start=1):
        lines.append(f"**Example {index}**")
        lines.append("")
        lines.append("Input:")
        lines.append("")
        lines.append("```text")
        lines.append(example["input"])
        lines.append("```")
        lines.append("")
        lines.append("Output:")
        lines.append("")
        lines.append("```text")
        lines.append(example["output"])
        lines.append("```")
        lines.append("")
        lines.append(example["explanation"])
        lines.append("")
    return "\n".join(lines)


def build_statement_markdown(problem: dict) -> str:
    """Return the full problem description. It holds the statement and the
    examples."""
    parts = [problem["statement_markdown"].strip()]
    parts.append("")
    parts.append("## Input")
    parts.append("")
    parts.append(problem["input_format"].strip())
    parts.append("")
    parts.append("## Output")
    parts.append("")
    parts.append(problem["output_format"].strip())
    parts.append("")
    parts.append("## Constraints")
    parts.append("")
    parts.append("```text")
    parts.append(problem["constraints"].strip())
    parts.append("```")
    parts.append(render_examples(problem["examples"]))
    return normalize("\n".join(parts))


def write_examples(problem: dict, cases: list[dict]) -> list[dict]:
    """Return the public examples with their expected output."""
    out = []
    visible = [c for c in cases if c["db_type"] == "visible"]
    for index, example in enumerate(problem["examples"]):
        stdin_text = normalize(example["input"])
        expected = normalize(example["output"])
        out.append({
            "example_number": index + 1,
            "input": stdin_text,
            "expected_output": expected,
            "explanation": example["explanation"],
            "test_case_id": visible[index]["id"] if index < len(visible) else None,
        })
    return out


# ---------------------------------------------------------------------------
# the first eight problems, converted from the original bank
# ---------------------------------------------------------------------------
def load_original_eight() -> list[dict]:
    """Return the first eight bank problems with hints added."""
    if not (OLD_BANK / "problems.json").exists():
        return []
    payload = json.loads((OLD_BANK / "problems.json").read_text(encoding="utf-8"))

    hints = json.loads((OLD_BANK / "variants" / "manifest.json").read_text(encoding="utf-8"))
    # The original manifest holds no hints. Build three template hints from the
    # diagnostic tags of each problem.
    problems = []
    for old in payload["problems"]:
        pid = old["id"]
        cases = []
        for position, tc in enumerate(old["test_cases"], start=1):
            kind = KIND_ALIAS[tc["test_type"]]
            cases.append({
                "id": tc["id"],
                "name": tc["name"],
                "db_type": "visible" if kind == "public" else kind,
                "partition": KIND_PARTITION[kind],
                "stdin": normalize(tc["input_json"]["stdin"]),
                "expected_output": normalize(tc["expected_output_json"]),
                "diagnostic_tag": tc.get("diagnostic_tag"),
                "is_boundary": bool(tc.get("is_boundary", False)),
                "time_limit_ms": tc.get("time_limit_ms") or TIME_LIMIT_MS,
                "memory_limit_mb": tc.get("memory_limit_mb") or MEMORY_LIMIT_MB,
                "sort_order": position,
            })
        solution = (OLD_BANK / old["reference_solution"]).read_text(encoding="utf-8")
        problems.append({
            "id": pid,
            "slug": old["slug"],
            "title": old["title"],
            "statement_markdown": old["description"].strip(),
            "input_format": old.get("input_spec", "").strip(),
            "output_format": old.get("output_spec", "").strip(),
            "constraints": old.get("constraints", "").strip(),
            "examples": _examples_from_cases(cases),
            "primary_misconception_id": old["designed_misconception"],
            "secondary_misconception_ids": old.get("secondary_misconceptions", []),
            "difficulty": "Beginner",
            "primary_topic": old.get("topic", "Diagnostics"),
            "supported_language": "cpp",
            "language_standard": STANDARD,
            "taxonomy_version": TAXONOMY_VERSION,
            "reference_solution_source": normalize(solution),
            "misconception_variant_id": _original_variant(pid),
            "hints": _original_hints(old),
            "test_cases": cases,
        })
    del hints
    return problems


def _examples_from_cases(cases: list[dict]) -> list[dict]:
    """Return two public examples for a converted problem."""
    visible = [c for c in cases if c["db_type"] == "visible"][:2]
    return [{
        "example_number": index + 1,
        "input": c["stdin"],
        "expected_output": c["expected_output"],
        "explanation": "Visible sample case.",
        "test_case_id": c["id"],
    } for index, c in enumerate(visible)]


def _original_variant(pid: str) -> str | None:
    """Return the variant file name for one of the first eight problems."""
    folder = OLD_BANK / "variants"
    if not folder.is_dir():
        return None
    hits = sorted(p.name for p in folder.glob(f"{pid}__CPP-*.cpp"))
    return hits[0] if hits else None


_ORIGINAL_HINTS = {
    "CP01": ("Your loop runs one time too many. Check the exit condition on the last pass.",
             "The upper bound of this range is exclusive. The valid integers are 0 to n-1.",
             "Check your comparison operator. An exclusive bound uses `<`, not `<=`."),
    "CP02": ("Your program prints a location. Does the contract ask for a value?",
             "An index reaches a value. The answer is the value itself.",
             "Check the expression in your output statement. Print the value, not the index."),
    "CP03": ("Your function sends the value away. Does the caller receive it?",
             "A function that returns a value uses `return`. Printed text does not reach the caller.",
             "Check the last statement of your function. Write `return`."),
    "CP04": ("Your access uses an index past the end. Is that index valid?",
             "A vector of size N holds the indices 0 to N-1. The index N is one place past the end.",
             "Check your last index. Write `size() - 1`, not `size()`."),
    "CP05": ("Your condition uses one comparison. Does the range need two?",
             "C++ does not chain comparisons as in mathematics. Join two comparisons with `&&`.",
             "Check your condition. Write `1 <= x && x <= 10`."),
    "CP06": ("Your condition changes x. Does it compare instead?",
             "The operator `=` assigns a value. The operator `==` compares two values.",
             "Check the operator in your condition. Write `x == 0`."),
    "CP07": ("Your recursive call does not come nearer to the base case.",
             "A recursive call must change the state. The same argument never terminates.",
             "Check the argument in your call. Pass `n - 1`."),
    "CP08": ("Your loop header has no update. Does the index change?",
             "A loop must advance its index. A missing update keeps the same position forever.",
             "Check the third part of your `for` header. Write `++i`."),
}


def _original_hints(old: dict) -> list[dict]:
    """Return three scaffolding hints for one of the first eight problems."""
    key = old["id"]
    if key not in _ORIGINAL_HINTS:
        return []
    one, two, three = _ORIGINAL_HINTS[key]
    code = old["designed_misconception"]
    return [
        {"order": 1, "hint_text": one, "related_misconception_id": code},
        {"order": 2, "hint_text": two, "related_misconception_id": code},
        {"order": 3, "hint_text": three, "related_misconception_id": code},
    ]


# ---------------------------------------------------------------------------
# new problems
# ---------------------------------------------------------------------------
def build_new_problems() -> list[dict]:
    """Return the problems from the definition modules, with cases expanded."""
    problems = []
    for definition in ALL_PROBLEMS:
        pid = definition["id"]
        counters = {"public": 0, "hidden": 0, "diagnostic": 0}
        cases: list[dict] = []
        for position, case in enumerate(definition["cases"], start=1):
            kind = KIND_ALIAS[case["kind"]]
            counters[kind] += 1
            letter = KIND_LETTER[kind]
            args = {k: v for k, v in case.items()
                    if k not in ("kind", "tag", "boundary")}
            stdin_text = normalize(definition["render"](args))
            expected = normalize(definition["model"](args))
            cases.append({
                "id": f"{pid}-{letter}{counters[kind]}",
                "name": _case_name(kind, case),
                "db_type": KIND_DB_TYPE[kind],
                "partition": KIND_PARTITION[kind],
                "stdin": stdin_text,
                "expected_output": expected,
                "diagnostic_tag": case.get("tag"),
                "diagnostic_trait": definition["misconception"] if case.get("tag") else None,
                "is_boundary": bool(case.get("boundary", False)),
                "time_limit_ms": TIME_LIMIT_MS,
                "memory_limit_mb": MEMORY_LIMIT_MB,
                "sort_order": position,
            })
        variant_source = apply_mutation(definition)
        problems.append({
            "id": pid,
            "slug": definition["slug"],
            "title": definition["title"],
            "statement_markdown": build_statement_markdown(definition),
            "input_format": definition["input_format"].strip(),
            "output_format": definition["output_format"].strip(),
            "constraints": definition["constraints"].strip(),
            "examples": write_examples(definition, cases),
            "primary_misconception_id": definition["misconception"],
            "secondary_misconception_ids": definition.get("secondary", []),
            "difficulty": definition["difficulty"],
            "primary_topic": definition["topic"],
            "supported_language": "cpp",
            "language_standard": STANDARD,
            "taxonomy_version": TAXONOMY_VERSION,
            "reference_solution_source": normalize(definition["solution"]),
            "misconception_variant_id": f"{pid}__{definition['misconception']}_a.cpp",
            "misconception_variant_source": variant_source,
            "hints": definition["hints"],
            "test_cases": cases,
        })
    return problems


def apply_mutation(definition: dict) -> str | None:
    """Return the mutated source, or None when the definition has no mutation."""
    pairs = definition.get("mutation") or []
    if not pairs:
        return None
    text = definition["solution"]
    for find, replace in pairs:
        if find not in text:
            raise SystemExit(
                f"{definition['id']}: the mutation target is not in the solution:\n{find}")
        text = text.replace(find, replace)
    return text


def _case_name(kind: str, case: dict) -> str:
    """Return a short human-readable test name."""
    label = {"public": "visible", "hidden": "hidden", "diagnostic": "diagnostic"}[kind]
    detail = case.get("tag") or ""
    if not detail:
        args = [k for k in case if k not in ("kind", "tag", "boundary")]
        detail = " ".join(args) if args else "case"
    return f"{label} {detail}"


# ---------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------
def write_bank(problems: list[dict]) -> dict:
    """Write every bank file. Return a summary."""
    if OUT_DIR.exists():
        for child in ("tests", "solutions", "variants"):
            path = OUT_DIR / child
            if path.exists():
                shutil.rmtree(path)

    checksums: dict[str, str] = {}
    variant_count = 0

    for problem in problems:
        pid = problem["id"]

        # reference solution
        sol_dir = OUT_DIR / "solutions"
        sol_dir.mkdir(parents=True, exist_ok=True)
        sol_path = sol_dir / f"{pid}.cpp"
        sol_path.write_text(problem["reference_solution_source"], encoding="utf-8",
                            newline="\n")
        checksums[f"solutions/{pid}.cpp"] = sha256(sol_path)

        # misconception variant
        if problem.get("misconception_variant_source"):
            var_dir = OUT_DIR / "variants"
            var_dir.mkdir(parents=True, exist_ok=True)
            var_path = var_dir / problem["misconception_variant_id"]
            var_path.write_text(problem["misconception_variant_source"],
                                encoding="utf-8", newline="\n")
            checksums[f"variants/{problem['misconception_variant_id']}"] = sha256(var_path)
            variant_count += 1

        # test files
        for case in problem["test_cases"]:
            folder = OUT_DIR / "tests" / case["partition"] / pid
            folder.mkdir(parents=True, exist_ok=True)
            in_path = folder / f"{case['sort_order']:02d}.in"
            out_path = folder / f"{case['sort_order']:02d}.out"
            in_path.write_text(case["stdin"], encoding="utf-8", newline="\n")
            out_path.write_text(case["expected_output"], encoding="utf-8", newline="\n")
            prefix = f"tests/{case['partition']}/{pid}/{case['sort_order']:02d}"
            checksums[f"{prefix}.in"] = sha256(in_path)
            checksums[f"{prefix}.out"] = sha256(out_path)

    manifest = {
        "bank": "cpp_diagnostics",
        "taxonomy_version": TAXONOMY_VERSION,
        "problem_count": len(problems),
        "test_case_count": sum(len(p["test_cases"]) for p in problems),
        "variant_count": variant_count,
        "hint_count": sum(len(p["hints"]) for p in problems),
        "time_limit_ms": TIME_LIMIT_MS,
        "memory_limit_mb": MEMORY_LIMIT_MB,
        "line_endings": "LF",
        "misconceptions": sorted({p["primary_misconception_id"] for p in problems}),
        "checksums": dict(sorted(checksums.items())),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "problems.json").write_text(
        json.dumps({"problems": problems}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    return manifest


def main() -> int:
    problems = build_new_problems()
    converted = load_original_eight()
    all_problems = converted + problems
    manifest = write_bank(all_problems)
    print("C++ diagnostic bank written:")
    print(f"  problems     : {manifest['problem_count']} "
          f"({len(converted)} carried over, {len(problems)} new)")
    print(f"  test cases   : {manifest['test_case_count']}")
    print(f"  variants     : {manifest['variant_count']}")
    print(f"  hints        : {manifest['hint_count']}")
    print(f"  misconceptions: {', '.join(manifest['misconceptions'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
