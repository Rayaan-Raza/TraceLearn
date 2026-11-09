"""Verified single-edit bugs in real accepted CodeNet programs, for the classes real code rarely shows.

    wsl python3 scripts/build_codenet_augment.py --raw-root /mnt/g/TraceLearn/Datasets_RAW

Real failing code almost never contains some misconceptions (in 707 labelled CodeNet failures:
assign-vs-compare 2, wrong loop direction 0, stale exit 3). This adds training examples for them
the way a student would make them: one edit to a real program that solves a training problem.

- Sources: sampled submissions of the TRAINING CodeNet problems (never the held-out ones) that pass
  every reference test (`build_codenet_pool.REFERENCES`).
- One edit per class (operators below). A mutant is kept only if it compiles and fails at least
  one reference test; for STALE_EXIT the failure must be a timeout (the loop never ends), for the
  others it must not be timeout-only. One mutant per source program, at most PER_PROBLEM per
  class and problem, at most PER_CLASS per class.
- Rows: `annotations/tier0d_codenet_mutants.jsonl`, SYNTHETIC, row ids `stu-cn-*`, the code in
  `static.source_code` and the inverse edit in `repair`, like the bank's student-style rows.
- Proofs: `annotations/mutant_proofs/codenet-stu-cn-*.json` (seed and mutant hashes, test counts,
  inverse edit), the provenance the G1 join check accepts for synthetic rows.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import build_codenet_pool as B  # noqa: E402
from sandbox_runner import RunConfig, run_many  # noqa: E402

OUT = B.DS / "annotations" / "tier0d_codenet_mutants.jsonl"
PROOFS = B.DS / "annotations" / "mutant_proofs"
SEED = 20261110
PER_CLASS = 60
PER_PROBLEM = 12

COND = re.compile(r"\b(if|while)\s*\(")


def _paren_span(code: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(code)):
        if code[i] == "(":
            depth += 1
        elif code[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _brace_body(code: str, start: int) -> tuple[int, int] | None:
    i = start
    while i < len(code) and code[i] in " \t\r\n":
        i += 1
    if i >= len(code) or code[i] != "{":
        return None
    depth = 0
    for j in range(i, len(code)):
        if code[j] == "{":
            depth += 1
        elif code[j] == "}":
            depth -= 1
            if depth == 0:
                return i, j
    return None


def m_assign(code: str) -> list[tuple[str, str, str]]:
    """`x == y` inside an if/while condition becomes `x = y`."""
    out = []
    for m in COND.finditer(code):
        o = m.end() - 1
        c = _paren_span(code, o)
        cond = code[o:c + 1]
        k = re.search(r"\b([A-Za-z_]\w*(?:\[[^\]]*\])?)\s*==\s*", cond)
        if k:
            new = cond[:k.start()] + k.group(1) + " = " + cond[k.end():]
            out.append((code[:o] + new + code[c + 1:], cond, new))
    return out


FOR_UP = re.compile(r"for\s*\(\s*((?:int|long long|long|size_t)\s+)?([A-Za-z_]\w*)\s*=\s*0\s*;\s*\2\s*<\s*([^;]+?)\s*;\s*(?:\+\+\2|\2\s*\+\+|\2\s*\+=\s*1)\s*\)")


def m_loop_dir(code: str) -> list[tuple[str, str, str]]:
    """An upward 0..n-1 loop runs downward n-1..0 instead."""
    out = []
    for m in FOR_UP.finditer(code):
        decl, var, bound = m.group(1) or "", m.group(2), m.group(3)
        new = f"for ({decl}{var} = ({bound}) - 1; {var} >= 0; {var}--)"
        out.append((code[:m.start()] + new + code[m.end():], m.group(0), new))
    return out


def m_stale_exit(code: str) -> list[tuple[str, str, str]]:
    """A while loop's update of its own condition variable is dropped."""
    out = []
    for m in re.finditer(r"\bwhile\s*\(", code):
        o = m.end() - 1
        c = _paren_span(code, o)
        if c < 0:
            continue
        names = set(re.findall(r"\b[A-Za-z_]\w*\b", code[o:c + 1])) - {"true", "false", "int", "long"}
        body = _brace_body(code, c + 1)
        if not body:
            continue
        b0, b1 = body
        for v in sorted(names):
            u = re.search(rf"(^|[;{{\s])({re.escape(v)}\s*(?:[-+*/%]=[^;]*|\+\+|--)\s*;|(?:\+\+|--){re.escape(v)}\s*;)",
                          code[b0:b1])
            if u:
                s0, s1 = b0 + u.start(2), b0 + u.end(2)
                out.append((code[:s0] + code[s1:], code[s0:s1], ""))
                break
    return out


def m_loop_boundary(code: str) -> list[tuple[str, str, str]]:
    """`i < n` in a for condition becomes `i <= n` (and `<=` becomes `<`)."""
    out = []
    for m in re.finditer(r"for\s*\(([^;]*);([^;]*);", code):
        cond = m.group(2)
        k = re.search(r"\b([A-Za-z_]\w*)\s*(<=|<)\s*", cond)
        if k:
            op = "<" if k.group(2) == "<=" else "<="
            new = cond[:k.start(2)] + op + " " + cond[k.end():]
            s = m.start(2)
            out.append((code[:s] + new + code[s + len(cond):], cond.strip(), new.strip()))
    return out


def m_range_check(code: str) -> list[tuple[str, str, str]]:
    """An if condition's comparison against a value moves its edge (`>=` <-> `>`, `<=` <-> `<`)."""
    swap = {">=": ">", ">": ">=", "<=": "<", "<": "<="}
    out = []
    for m in re.finditer(r"\bif\s*\(", code):
        o = m.end() - 1
        c = _paren_span(code, o)
        cond = code[o:c + 1]
        k = re.search(r"(?<![<>=!])(>=|<=|>|<)(?![<>=])", cond)
        if k and "<<" not in cond and ">>" not in cond:
            new = cond[:k.start()] + swap[k.group(1)] + cond[k.end():]
            out.append((code[:o] + new + code[c + 1:], cond, new))
    return out


OPERATORS = {
    "CPP_ASSIGN_VS_COMPARE": m_assign,
    "CPP_WRONG_LOOP_DIR": m_loop_dir,
    "CPP_STALE_EXIT": m_stale_exit,
    "CPP_LOOP_BOUNDARY": m_loop_boundary,
    "CPP_RANGE_CHECK": m_range_check,
}
SHORT = {"CPP_ASSIGN_VS_COMPARE": "av", "CPP_WRONG_LOOP_DIR": "wd", "CPP_STALE_EXIT": "se",
         "CPP_LOOP_BOUNDARY": "lb", "CPP_RANGE_CHECK": "rc"}


def write_proofs(rows: list[dict], base: Path) -> int:
    """One execution proof per row in `mutant_proofs/` (`codenet-<row_id>.json`), the provenance
    G1 checks for a SYNTHETIC row whose source_record_id is not a real submission (like the
    bank's `student-*` and `synth2-*` proofs)."""
    for old in PROOFS.glob("codenet-stu-cn-*.json"):
        old.unlink()
    for r in rows:
        sid = r["seed_ref"].split(":", 1)[1]
        seed = (base / sid).read_bytes()
        mutant = r["static"]["source_code"]
        rep = json.loads(r["repair"])
        proof = {
            "run_id": r["row_id"], "seed_submission_id": f"codenet:{sid}", "problem_id": r["problem_id"],
            "operator": r["mutation_op"], "label": r["label"],
            "seed_sha256": hashlib.sha256(seed).hexdigest()[:16],
            "mutant_sha256": hashlib.sha256(mutant.encode("utf-8")).hexdigest(),
            "tests_passed": r["runtime"]["tests_passed"], "tests_total": r["runtime"]["tests_total"],
            "inverse_edit": {**rep, "base_sha256": hashlib.sha256(seed).hexdigest()[:16]},
        }
        (PROOFS / f"codenet-{r['row_id']}.json").write_text(json.dumps(proof, indent=1, ensure_ascii=False) + "\n",
                                                           encoding="utf-8", newline="\n")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--proofs-only", action="store_true", help="rewrite the proofs for the existing rows")
    a = ap.parse_args()
    base = a.raw_root / "Project_CodeNet" / "Project_CodeNet" / "data"
    if a.proofs_only:
        rows = [json.loads(line) for line in OUT.open(encoding="utf-8") if line.strip()]
        print(f"wrote {write_proofs(rows, base)} proofs -> {PROOFS}")
        return 0
    cfg = RunConfig(warnings_pass=False, sanitizer_pass=False, valgrind_pass=False, double_run=False,
                    stop_after_timeouts=1, keep_stdout_bytes=600)
    cache = str(B.DS / "cache" / "codenet_exec" / "runs")
    rng = random.Random(SEED)
    problems = [p for p in sorted(B.REFERENCES) if p not in B.HELDOUT_PROBLEMS]
    # candidates[cls] -> list of (pid, source_record_id, mutant, before, after)
    candidates: dict[str, list] = defaultdict(list)
    for pid in problems:
        tests = json.load(gzip.open(B.TESTS / f"{pid}.json.gz", "rt", encoding="utf-8"))
        files = sorted((base / pid / "C++").glob("*.cpp"))
        random.Random(f"{SEED}-{pid}").shuffle(files)
        subs, seen = [], set()
        for f in files:
            code = f.read_text(encoding="utf-8", errors="replace")
            k = B.norm_key(code)
            if k in seen or len(code) > 6000:
                continue
            seen.add(k)
            subs.append((f"{pid}/C++/{f.name}", code))
            if len(subs) >= B.SAMPLE_PER_PROBLEM:
                break
        runs = list(run_many([(c, "cpp", tests) for _, c in subs], cfg, workers=a.workers, cache_dir=cache))
        correct = [(sid, c) for (sid, c), r in zip(subs, runs) if (r.get("tests") or {}).get("all_passed")]
        jobs, meta = [], []
        for sid, code in correct:
            for cls, op in OPERATORS.items():
                for mutant, before, after in op(code)[:2]:
                    jobs.append((mutant, "cpp", tests))
                    meta.append((cls, sid, mutant, before, after))
        results = list(run_many(jobs, cfg, workers=a.workers, cache_dir=cache))
        kept = Counter()
        for (cls, sid, mutant, before, after), r in zip(meta, results):
            if not (r.get("compile") or {}).get("ok"):
                continue
            t = r.get("tests") or {}
            res = t.get("results") or []
            failing = [x for x in res if x.get("status") not in ("pass", "skipped")]
            if not failing:
                continue
            timeouts = all(x.get("status") == "timeout" for x in failing)
            if (cls == "CPP_STALE_EXIT") != timeouts:
                continue
            candidates[cls].append((pid, sid, mutant, before, after, t.get("passed"), t.get("total")))
            kept[cls] += 1
        print(f"{pid}: {len(correct)} correct of {len(subs)}; verified mutants {dict(kept)}", flush=True)
    rows = []
    for cls, cands in sorted(candidates.items()):
        rng.shuffle(cands)
        used_src, per_problem = set(), Counter()
        n = 0
        for pid, sid, mutant, before, after, passed, total in cands:
            if n >= PER_CLASS or sid in used_src or per_problem[pid] >= PER_PROBLEM:
                continue
            used_src.add(sid)
            per_problem[pid] += 1
            rows.append({
                "row_id": f"stu-cn-{SHORT[cls]}-{n:03d}", "dataset_source": "SYNTHETIC",
                "source_record_id": f"codenet-mutant:{sid}:{SHORT[cls]}", "problem_id": f"tl-codenet-{pid}",
                "problem_cluster": None, "language": "cpp", "label": cls, "label_source": "synthetic",
                "label_confidence": 0.9, "secondary_labels": [], "verdict": None,
                "firing_functions": ["codenet_single_edit"], "seed_ref": f"codenet:{sid}",
                "mutation_op": f"codenet_{cls.lower()}", "verified_by_execution": True,
                "repair": json.dumps({"op": "inverse_edit", "before": after, "after": before}),
                "meta": {"user_id_hash": None, "attempt_index": None, "timestamp": None, "prev_submission_id": None},
                "static": {"source_code": mutant}, "warnings": {"compile_warnings": ""},
                "runtime": {"tests_passed": passed, "tests_failed": (total or 0) - (passed or 0), "tests_total": total,
                            "sanitizer_ok": None},
                "tests": {}, "cpg": {}, "context": {},
                "pipeline_run_id": "build_codenet_augment/1.0.0", "taxonomy_version": "tl-cpp-v2", "schema_version": "1.1",
            })
            n += 1
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    print(f"wrote {len(rows)} rows -> {OUT}: {dict(Counter(r['label'] for r in rows))}")
    print(f"wrote {write_proofs(rows, base)} proofs -> {PROOFS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
