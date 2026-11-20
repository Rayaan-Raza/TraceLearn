"""Student-style buggy programs for every misconception class, on the product's 40 bank problems.

    wsl python3 scripts/build_bank_synthetic.py [--workers 4] [--per-class 90] [--per-base 2]

The bank is what students attempt, but the hand-written bank rows (`tier0b`, styles A and B) are
thin for some classes (INT_OVERFLOW 2, WRONG_LOOP_DIR 4, ARRAY_BOUNDS 8). This adds rows built on
two further solution styles (`student_specs_c.py`, styles C and D):

1. a style-C or style-D solution must pass every bank test of its problem;
2. one operator per class injects a single bug a beginner makes (table `OPERATORS`);
3. the buggy program is kept only if it compiles and fails at least one test. STALE_EXIT must
   time out, MISSING_BASE_CASE must crash or time out, the others must not fail by timeout only;
4. a program whose code is already in the dataset is skipped.

Output: `annotations/tier0e_bank_student_cd.jsonl` (rows `stu-cpNN-cXX` / `stu-cpNN-dXX`, the
shape of `tier0b`), one proof per row in `annotations/mutant_proofs/bankcd-*.json`, and
`reports/bank_synthetic_report.md`. Selection is a seeded shuffle, so a rerun after any operator
change gives a different (equivalent) sample with different row ids, and the run records keyed by
row id must then be rebuilt. The committed file is the 2026-11-15 run minus `stu-cp26-c01`, removed
when its operator was found to have matched the call `cost_for(` as a `for` loop. Styles A, B and the reference solutions are not used here, so
a benchmark built on those (`scripts/eval_bank_benchmark.py`) shares no solution with these rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_codenet_augment as A  # noqa: E402
from build_student_synthetic import make_row, run_tests  # noqa: E402

DS = ROOT / "data" / "misconception_dataset"
BANK = ROOT / "data" / "cpp_diagnostics" / "problems.json"
OUT = DS / "annotations" / "tier0e_bank_student_cd.jsonl"
PROOFS = DS / "annotations" / "mutant_proofs"
REPORT = DS / "reports" / "bank_synthetic_report.md"
SEED = 20261115
P = "CPP_"
NUM = r"(?:int|long long|long|double|float)"


def norm(code: str) -> str:
    bare = re.sub(r"//[^\n]*|/\*.*?\*/", "", code, flags=re.S)
    return hashlib.md5(re.sub(r"\s+", "", bare).encode()).hexdigest()


# Each operator returns [(buggy code, text before, text after)].

def m_uninit(code: str) -> list[tuple[str, str, str]]:
    """`int total = 0;` loses its initialiser."""
    out = []
    for m in re.finditer(rf"\b({NUM})\s+([A-Za-z_]\w*)\s*=\s*0(?:\.0)?\s*;", code):
        new = f"{m.group(1)} {m.group(2)};"
        out.append((code[:m.start()] + new + code[m.end():], m.group(0), new))
    for m in re.finditer(rf"\b({NUM})\s+((?:[A-Za-z_]\w*\s*,\s*)+)([A-Za-z_]\w*)\s*=\s*0\s*([,;])", code):
        new = f"{m.group(1)} {m.group(2)}{m.group(3)}{m.group(4)}"
        out.append((code[:m.start()] + new + code[m.end():], m.group(0), new))
    return out


def m_overflow(code: str) -> list[tuple[str, str, str]]:
    """Every `long long` becomes `int`."""
    if "long long" not in code:
        return []
    return [(re.sub(r"\blong long\b", "int", code).replace("%lld", "%d"), "long long", "int")]


def m_off_by_one(code: str) -> list[tuple[str, str, str]]:
    """A start value, an index or an `n - 1` slips by one; the loop operator stays right."""
    out = []
    for m in re.finditer(r"for\s*\(\s*((?:int|long long|long|size_t)\s+)?([A-Za-z_]\w*)\s*=\s*([01])\s*;", code):
        new = "1" if m.group(3) == "0" else "0"
        out.append((code[:m.start(3)] + new + code[m.end(3):], m.group(0), f"start {m.group(3)} -> {new}"))
    for m in re.finditer(r"\[\s*([A-Za-z_]\w*)\s*\]", code):
        if m.group(1) in ("i", "j", "k", "idx", "pos", "mid"):
            for d in ("+ 1", "- 1"):
                new = f"[{m.group(1)} {d}]"
                out.append((code[:m.start()] + new + code[m.end():], m.group(0), new))
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*-\s*1\b(?!\s*[\]\d])", code):
        out.append((code[:m.start()] + m.group(1) + code[m.end():], m.group(0), m.group(1)))
    return out


def m_array_bounds(code: str) -> list[tuple[str, str, str]]:
    """A fixed array, or a vector, far smaller than the input needs."""
    out = []
    for m in re.finditer(r"\b(?:int|long long|long|double|char|bool)\s+[A-Za-z_]\w*\s*\[\s*(\d+)\s*\]", code):
        size = int(m.group(1))
        if size >= 8:
            new = str(max(2, size // 50))
            out.append((code[:m.start(1)] + new + code[m.end(1):], m.group(0), f"size {size} -> {new}"))
    for m in re.finditer(r"\bvector\s*<[^>]+>\s*[A-Za-z_]\w*\s*\(\s*([A-Za-z_]\w*)\s*[,)]", code):
        new = f"{m.group(1)} / 4"
        out.append((code[:m.start(1)] + new + code[m.end(1):], m.group(0), f"vector of {new}"))
    return out


def m_missing_base(code: str) -> list[tuple[str, str, str]]:
    """A recursive function loses its first stopping case."""
    out = []
    for f in re.finditer(r"\b(?:int|long long|long|void|bool|double)\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{", code):
        name = f.group(1)
        body = A._brace_body(code, f.end() - 1)
        if not body or name == "main" or not re.search(rf"\b{name}\s*\(", code[body[0] + 1:body[1]]):
            continue
        m = re.search(r"\bif\s*\([^{};]*\)\s*(?:\{\s*return\b[^;]*;\s*\}|return\b[^;]*;)", code[body[0]:body[1]])
        if m:
            s, e = body[0] + m.start(), body[0] + m.end()
            out.append((code[:s] + code[e:], code[s:e], "(base case removed)"))
    return out


def m_range_check(code: str) -> list[tuple[str, str, str]]:
    """A validation edge moves, `&&` and `||` swap, or a range becomes a chained comparison."""
    out = list(A.m_range_check(code))
    for m in re.finditer(r"\bif\s*\(", code):
        o = m.end() - 1
        c = A._paren_span(code, o)
        cond = code[o:c + 1]
        k = re.search(r"&&|\|\|", cond)
        if k and re.search(r"[<>]", cond) and "<<" not in cond:
            new = cond[:k.start()] + ("||" if k.group() == "&&" else "&&") + cond[k.end():]
            out.append((code[:o] + new + code[c + 1:], cond, new))
        k = re.search(r"([A-Za-z_]\w*)\s*(>=|>)\s*(-?\w+)\s*&&\s*\1\s*(<=|<)\s*(-?\w+)", cond)
        if k:
            chained = f"{k.group(3)} {'<=' if k.group(2) == '>=' else '<'} {k.group(1)} {k.group(4)} {k.group(5)}"
            new = cond[:k.start()] + chained + cond[k.end():]
            out.append((code[:o] + new + code[c + 1:], cond, new))
    return out


def m_loop_boundary(code: str) -> list[tuple[str, str, str]]:
    """A `for` or `while` test's `<` becomes `<=` (or the reverse)."""
    out = []
    for m in re.finditer(r"\bfor\s*\(([^;]*);([^;]*);", code):   # \b: `cost_for(` is a call, not a loop
        cond = m.group(2)
        k = re.search(r"\b([A-Za-z_]\w*)\s*(<=|<)\s*", cond)
        if k:
            flipped = cond[:k.start(2)] + ("<" if k.group(2) == "<=" else "<=") + " " + cond[k.end():]
            s = m.start(2)
            out.append((code[:s] + flipped + code[s + len(cond):], cond.strip(), flipped.strip()))
    for m in re.finditer(r"\bwhile\s*\(", code):
        o = m.end() - 1
        c = A._paren_span(code, o)
        cond = code[o:c + 1]
        k = re.search(r"(?<![<>=!])(<=|<)(?![<>=])", cond)
        if k:
            new = cond[:k.start()] + ("<" if k.group(1) == "<=" else "<=") + cond[k.end():]
            out.append((code[:o] + new + code[c + 1:], cond, new))
    return out


def m_stale_exit(code: str) -> list[tuple[str, str, str]]:
    """A `while` loop's update, or a `for` loop's step, is dropped: the exit condition never changes."""
    out = list(A.m_stale_exit(code))
    step = r"([A-Za-z_]\w*\s*(?:\+\+|--|[-+]=\s*\w+)|(?:\+\+|--)\s*[A-Za-z_]\w*)"
    for m in re.finditer(rf"\bfor\s*\(([^;()]*);([^;()]*);\s*{step}\s*\)", code):
        out.append((code[:m.start(3)] + code[m.end(3):], m.group(0), "(loop step removed)"))
    return out


def m_other(code: str) -> list[tuple[str, str, str]]:
    """Bugs no misconception class explains: extra output text, a wrong formula, a swapped test."""
    out = []
    m = re.search(r'cout\s*<<\s*(?!")', code)
    if m:
        out.append((code[:m.end()] + '"Answer: " << ' + code[m.end():], "cout <<", 'cout << "Answer: " <<'))
    m = re.search(r'printf\s*\(\s*"(%)', code)
    if m:
        out.append((code[:m.start(1)] + "Result = " + code[m.start(1):], 'printf("%', 'printf("Result = %'))
    for m in re.finditer(r"(\+=|-=)\s*([A-Za-z_]\w*(?:\[[^\]]*\])?)\s*;", code):
        out.append((code[:m.start(2)] + m.group(2) + " * 2" + code[m.end(2):], m.group(0), f"{m.group(1)} {m.group(2)} * 2;"))
    for m in re.finditer(r"([A-Za-z_]\w*)\s*%\s*2\s*==\s*0", code):
        new = f"{m.group(1)} % 2 == 1"
        out.append((code[:m.start()] + new + code[m.end():], m.group(0), new))
    for m in re.finditer(r'"(NONE|EMPTY|NOT FOUND|OUT|IN|ZERO|YES|NO|OK)(\\n)?"', code):
        new = '"' + m.group(1).capitalize() + (m.group(2) or "") + '"'
        out.append((code[:m.start()] + new + code[m.end():], m.group(0), new))
    return out


OPERATORS = {
    P + "LOOP_BOUNDARY": m_loop_boundary, P + "OFF_BY_ONE": m_off_by_one, P + "ARRAY_BOUNDS": m_array_bounds,
    P + "UNINITIALIZED_VAR": m_uninit, P + "INT_OVERFLOW": m_overflow, P + "MISSING_BASE_CASE": m_missing_base,
    P + "ASSIGN_VS_COMPARE": A.m_assign, P + "WRONG_LOOP_DIR": A.m_loop_dir, P + "RANGE_CHECK": m_range_check,
    P + "STALE_EXIT": m_stale_exit, P + "OTHER_ERROR": m_other,
}
PER_OPERATOR = 6


LOOP_LABELS = (P + "LOOP_BOUNDARY", P + "STALE_EXIT", P + "WRONG_LOOP_DIR")


def label_possible(label: str, code: str) -> bool:
    """A loop misconception needs a loop: guards against an operator matching a look-alike."""
    return label not in LOOP_LABELS or bool(re.search(r"\b(?:for|while)\s*\(", code))


def failure_fits(label: str, statuses: list[str]) -> bool:
    if label == P + "STALE_EXIT":
        return "timeout" in statuses
    if label == P + "MISSING_BASE_CASE":
        return bool({"crash", "timeout"} & set(statuses))
    return not all(s in ("pass", "timeout") for s in statuses)


def _job(args):
    key, code, tests = args
    try:
        return key, run_tests(code, tests)
    except Exception as exc:  # noqa: BLE001
        return key, {"compiled": False, "error": str(exc)}


def load_bank() -> dict[str, list[dict[str, str]]]:
    data = json.loads(BANK.read_text(encoding="utf-8"))
    problems = data if isinstance(data, list) else data["problems"]
    return {p["id"]: [{"stdin": t["stdin"], "expected_output": t["expected_output"]} for t in p["test_cases"]]
            for p in problems}


def known_code() -> set[str]:
    seen = set()
    path = DS / "annotations" / "labels.jsonl"
    if path.is_file():
        for line in path.open(encoding="utf-8"):
            if line.strip():
                static = json.loads(line).get("static")
                if isinstance(static, dict) and static.get("source_code"):
                    seen.add(norm(static["source_code"]))
    return seen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--per-class", type=int, default=90)
    ap.add_argument("--per-base", type=int, default=2, help="rows per class and solution")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    from student_specs_c import SPECS_CD

    tests = load_bank()
    bases = {(pid, key): code for pid, spec in SPECS_CD.items() for key, code in spec.items()}
    with ProcessPoolExecutor(args.workers) as ex:
        good = {k for k, r in ex.map(_job, [(k, c, tests[k[0]]) for k, c in bases.items()])
                if r.get("compiled") and r.get("passed") == r.get("total")}
    print(f"solutions {len(bases)}, passing every test {len(good)}", flush=True)

    seen = known_code() if args.out == OUT else set()
    cands = []
    for pid, key in sorted(good):
        for label, op in OPERATORS.items():
            try:
                muts = op(bases[(pid, key)])
            except Exception:  # noqa: BLE001
                muts = []
            for code, before, after in muts[:PER_OPERATOR]:
                h = norm(code)
                if h in seen or code == bases[(pid, key)] or not label_possible(label, bases[(pid, key)]):
                    continue
                seen.add(h)
                cands.append(((pid, key, label, len(cands)), code, before, after))
    with ProcessPoolExecutor(args.workers) as ex:
        results = dict(ex.map(_job, [(c[0], c[1], tests[c[0][0]]) for c in cands]))

    verified = []
    for key, code, before, after in cands:
        r = results[key]
        if r.get("compiled") and r.get("passed") != r.get("total") and failure_fits(key[2], r.get("statuses") or []):
            verified.append((key, code, before, after, r))
    random.Random(SEED).shuffle(verified)
    per_class, per_base, rows, index = Counter(), Counter(), [], Counter()
    for (pid, base_key, label, _), code, before, after, r in verified:
        if per_class[label] >= args.per_class or per_base[(label, pid, base_key)] >= args.per_base:
            continue
        per_class[label] += 1
        per_base[(label, pid, base_key)] += 1
        idx = index[(pid, base_key)]
        index[(pid, base_key)] += 1
        row = make_row(pid, base_key, idx, label, f"{before} -> {after}"[:160], code, bases[(pid, base_key)], before, after, r)
        row["pipeline_run_id"] = "build_bank_synthetic/1.0.0"
        row["firing_functions"] = ["bank_class_operator"]
        rows.append(row)
    rows.sort(key=lambda r: r["row_id"])

    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    if args.out == OUT:
        PROOFS.mkdir(parents=True, exist_ok=True)
        for old in PROOFS.glob("bankcd-*.json"):
            old.unlink()
        for r in rows:
            proof = {"run_id": r["row_id"], "seed_submission_id": r["seed_ref"], "problem_id": r["problem_id"],
                     "operator": r["mutation_op"], "label": r["label"], "seed_sha256": r["repair"]["base_sha256"],
                     "mutant_sha256": r["static"]["source_code_sha256"],
                     "tests_passed": r["runtime"]["tests_passed"], "tests_total": r["runtime"]["tests_total"],
                     "inverse_edit": r["repair"]}
            (PROOFS / f"bankcd-{r['row_id']}.json").write_text(json.dumps(proof, indent=1) + "\n", encoding="utf-8", newline="\n")
        by_label = Counter(r["label"] for r in rows)
        spread = {c: len({r["problem_id"] for r in rows if r["label"] == c}) for c in by_label}
        lines = ["# Bank synthetic rows, styles C and D", "", "Generated by `scripts/build_bank_synthetic.py`. Do not edit by hand.", "",
                 f"- Solutions checked: {len(bases)}; passing every bank test: {len(good)}.",
                 f"- Buggy candidates run: {len(cands)}; verified: {len(verified)}; rows kept: {len(rows)}.", "",
                 "| Label | Rows | Bank problems |", "|---|---:|---:|"]
        lines += [f"| {k} | {v} | {spread[k]} |" for k, v in sorted(by_label.items())]
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"candidates {len(cands)}, verified {len(verified)}, kept {len(rows)}: "
          f"{dict(sorted(Counter(r['label'][4:] for r in rows).items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
