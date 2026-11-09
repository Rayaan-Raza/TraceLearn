"""Execution and counterfactual evidence for every labelled row, through ONE runner.

    wsl python3 scripts/counterfactual_evidence.py --raw-root /mnt/g/TraceLearn/Datasets_RAW [--limit N] [--workers 10]

Why: the labelling rule is "the bug whose fix makes the first failing test pass". This script
measures that directly and without reading any label: for each class's inverse operators
(`repair_verify.GENERATORS`) it applies one small edit at a time and records whether the edit
fixes the first failing test, or every test. Those counts do not depend on program size or on
which problem it is, so they carry across unseen problems.

It also gives every lane the same evidence vocabulary. Before this, CodeStream rows ran without
sanitizers, and synthetic programs had only pass/fail totals, so the two could not be compared.

Uninitialised reads are measured without Valgrind: build with `-ftrivial-auto-var-init=zero` and
`=pattern`; if the first failing test's output differs, the program's output depends on an
unset local variable.

Results append to cache/counterfactual/evidence.jsonl, keyed by row id, so a run can resume.
No label, split or model is read to compute evidence; the job list uses labels only to choose
which rows are worth computing (rows with a usable label).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import repair_extra  # noqa: E402
import repair_verify  # noqa: E402

from sandbox_runner import RunConfig, run_submission  # noqa: E402
from sandbox_runner.compare import compare_output  # noqa: E402
from sandbox_runner.config import Limits, normalize_lang  # noqa: E402
from sandbox_runner.process import run_process  # noqa: E402
from sandbox_runner.runner import _compile  # noqa: E402

DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "cache" / "counterfactual" / "evidence.jsonl"
OUT_EXTRA = DS / "cache" / "counterfactual" / "evidence_extra.jsonl"

repair_verify.MAX_CANDIDATES = 16
# Work is bounded by a COUNT of candidate builds per pass, so the same program always gets the same
# record whatever the machine's load. No training row ever needed more than 50 (docs/6-nov.md
# section 19). The wall-clock budget is only a safety net for pathological programs.
MAX_BUILDS = 64
TIME_BUDGET_S = 240.0          # per row; a row that runs out keeps what it measured (budget_hit)
FAST_FLAGS = ["-O1", "-w", "-pipe"]
LIMITS = Limits(time_s=2.0)
BASE_CFG = RunConfig(limits=LIMITS, valgrind_pass=False, sanitizer_max_input_bytes=20_000, slow_pass_skip_timeouts=True,
                     double_run=False, stop_after_timeouts=2, confirm_timeouts=True)
FAST_CFG = RunConfig(limits=LIMITS, sanitizer_pass=False, valgrind_pass=False, double_run=False, stop_after_timeouts=1,
                     confirm_timeouts=True)


def _ended(status: str, out: str) -> tuple[str, str]:
    """A run that did not end normally is one outcome: whether a runaway program is killed by the
    stack limit or by the clock depends on the machine's speed, not on the program."""
    return ("abnormal", "") if status in ("timeout", "crash") else (status, out)


class _Work:
    """A temp dir holding the inputs, so each candidate only costs a compile and a run."""

    def __init__(self, tests: list[dict]):
        self.dir = tempfile.mkdtemp(prefix="cf-")
        os.chmod(self.dir, 0o777)
        self.tests = tests
        self.inputs = []
        for i, t in enumerate(tests):
            path = os.path.join(self.dir, f"in{i}.txt")
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(t["input"])
            self.inputs.append(path)

    def build(self, code: str, lang: str, flags: list[str], name: str = "p") -> str | None:
        src = os.path.join(self.dir, f"{name}.{'cpp' if lang == 'cpp' else 'c'}")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)
        os.chmod(src, 0o644)
        out = os.path.join(self.dir, name)
        c = _compile(lang, src, out, flags, self.dir, FAST_CFG, "c" + name)
        if not c["ok"] and lang == "c":
            c = _compile(lang, src, out, [*flags, "-include", "stdbool.h"], self.dir, FAST_CFG, "c" + name)
        return out if c["ok"] else None

    def run(self, binary: str, i: int) -> tuple[str, str]:
        r = run_process([binary], stdin_path=self.inputs[i], workdir=self.dir, timeout_s=LIMITS.time_s, limits=LIMITS,
                        isolate_network=False, tag=f"r{i}")
        if r["timed_out"]:
            # Confirm once at three times the limit, so a slow machine does not turn a slow
            # correct run into a timeout.
            r = run_process([binary], stdin_path=self.inputs[i], workdir=self.dir, timeout_s=LIMITS.time_s * 3,
                            limits=LIMITS, isolate_network=False, tag=f"r{i}c")
        if r["timed_out"]:
            return "timeout", ""
        if r["signal"] is not None:
            return "crash", ""
        return compare_output(r["stdout"], self.tests[i]["output"])["status"], r["stdout"]

    def close(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def _measure(w: _Work, cands: list, lang: str, tests: list[dict], first: int, before: dict, deadline: float, out: dict) -> dict:
    """One class: how many candidate edits exist, compile, fix the first failure, fix everything."""
    rec = {"n": len(cands), "compiled": 0, "fix_first": 0, "fix_first_noreg": 0, "fix_all": 0, "best_gain": 0, "ops": []}
    for rep in cands:
        if time.monotonic() > deadline or out.get("builds", 0) >= MAX_BUILDS:
            out["budget_hit"] = True
            break
        out["builds"] = out.get("builds", 0) + 1
        b = w.build(rep.code, lang, FAST_FLAGS)
        if not b:
            continue
        rec["compiled"] += 1
        if w.run(b, first)[0] != "pass":
            continue
        rec["fix_first"] += 1
        rec["ops"].append(rep.op)
        passed = regress = 0
        timeouts = 0
        for i in range(len(tests)):
            if timeouts:
                st = "skipped"
            elif i == first:
                st = "pass"
            else:
                st = w.run(b, i)[0]
                timeouts += st == "timeout"
            passed += st == "pass"
            regress += before.get(i) == "pass" and st != "pass"
        base_passed = sum(1 for v in before.values() if v == "pass")
        rec["fix_first_noreg"] += regress == 0
        rec["fix_all"] += passed == len(tests)
        rec["best_gain"] = max(rec["best_gain"], (passed - base_passed) / max(len(tests), 1))
        if passed == len(tests):
            break  # one complete repair is the strongest evidence this class can give
    rec["ops"] = rec["ops"][:4]
    return rec


def extra_counterfactuals(code: str, lang: str, tests: list[dict], results: list[dict], deadline: float) -> dict:
    """The second set of edits (`repair_extra`), given the program's already measured test results."""
    before = {r["idx"]: r["status"] for r in results}
    first = next((i for i in sorted(before) if before[i] not in ("pass", "skipped")), None)
    if first is None:
        return {"first": None, "classes": {}}
    try:
        prog = repair_verify.parse(code)
    except Exception:  # noqa: BLE001  a program the light parser cannot read has no candidates
        return {"first": first, "classes": {}, "parse_error": True}
    w = _Work(tests)
    out: dict = {"first": first, "classes": {}, "budget_hit": False}
    try:
        for cls, gen in repair_extra.EXTRA_GENERATORS.items():
            try:
                cands = gen(prog)
            except Exception:  # noqa: BLE001
                cands = []
            out["classes"][cls] = _measure(w, cands, lang, tests, first, before, deadline, out)
    finally:
        w.close()
    return out


def counterfactuals(code: str, lang: str, tests: list[dict], results: list[dict], deadline: float) -> dict:
    """Per class: how many candidate edits exist, compile, fix the first failure, fix everything."""
    before = {r["idx"]: r["status"] for r in results}
    first = next((i for i in sorted(before) if before[i] not in ("pass", "skipped")), None)
    if first is None:
        return {"first": None, "classes": {}, "uninit": None}
    w = _Work(tests)
    try:
        prog = repair_verify.parse(code)
    except Exception:  # noqa: BLE001  a program the light parser cannot read has no candidates
        w.close()
        return {"first": first, "classes": {}, "uninit": None, "parse_error": True}
    out: dict = {"first": first, "classes": {}, "budget_hit": False}
    try:
        for cls in repair_verify.GENERATORS:
            try:
                cands = repair_verify.candidates(code, cls, prog)
            except Exception:  # noqa: BLE001
                cands = []
            out["classes"][cls] = _measure(w, cands, lang, tests, first, before, deadline, out)
        # Does the first failing test's output depend on an unset local variable?
        z = w.build(code, lang, [*FAST_FLAGS, "-ftrivial-auto-var-init=zero"], "z")
        q = w.build(code, lang, [*FAST_FLAGS, "-ftrivial-auto-var-init=pattern"], "q")
        if z and q and time.monotonic() < deadline:
            sz, oz = w.run(z, first)
            sq, oq = w.run(q, first)
            out["uninit"] = {"zero_status": sz, "pattern_status": sq,
                             "differs": _ended(sz, oz) != _ended(sq, oq), "zero_fixes": sz == "pass"}
        else:
            out["uninit"] = None
    finally:
        w.close()
    return out


def slim_tests(t: dict | None) -> dict | None:
    if not t:
        return t
    t = dict(t)
    t["results"] = [{k: v for k, v in r.items() if k not in ("stderr_head", "stdout_head")} | {"stdout_head": (r.get("stdout_head") or "")[:200]}
                    for r in t.get("results") or []]
    return t


def extra_evidence_for(job: dict) -> dict:
    t0 = time.monotonic()
    rec = {"row_id": job["row_id"]}
    try:
        rec["cf_extra"] = extra_counterfactuals(job["code"], normalize_lang(job["lang"]), job["tests"], job["results"], t0 + TIME_BUDGET_S)
    except Exception as exc:  # noqa: BLE001  one bad row must not kill a bulk run
        rec["error"] = f"{type(exc).__name__}: {exc}"
    rec["seconds"] = round(time.monotonic() - t0, 2)
    return rec


def evidence_for(job: dict) -> dict:
    t0 = time.monotonic()
    rid, code, lang, tests = job["row_id"], job["code"], normalize_lang(job["lang"]), job["tests"]
    try:
        base = run_submission(code, lang, tests, BASE_CFG)
        rec = {"row_id": rid, "compiled": bool((base.get("compile") or {}).get("ok")), "n_tests": len(tests),
               "warnings": (base.get("warnings") or {}).get("count_by_flag"), "tests": slim_tests(base.get("tests")),
               "runtime": base.get("runtime"), "branch": base.get("branch")}
        rt = rec["runtime"]
        if isinstance(rt, dict) and isinstance(rt.get("sanitizer"), dict):
            s = rt["sanitizer"]
            rt["sanitizer"] = {k: s.get(k) for k in ("complete", "kinds", "reports", "tests_run")}
            s2 = rt["sanitizer"]
            s2["reports"] = (s2.get("reports") or [])[:6]
        if rec["compiled"] and rec["tests"]:
            rec["cf"] = counterfactuals(code, lang, tests, rec["tests"]["results"], t0 + TIME_BUDGET_S)
    except Exception as exc:  # noqa: BLE001  one bad row must not kill a bulk run
        rec = {"row_id": rid, "error": f"{type(exc).__name__}: {exc}"}
    rec["seconds"] = round(time.monotonic() - t0, 2)
    return rec


# ------------------------------------------------------------------------- jobs


def _synth2_tests() -> dict[str, list[str]]:
    out = {}
    for path in sorted((DS / "synth_v2").glob("agent_*.json")):
        for p in json.loads(path.read_text(encoding="utf-8")).get("problems", []):
            out[p["id"]] = p
    return out


def _reference_outputs(problem: dict, workdir: str) -> list[dict] | None:
    tests = [x for x in problem["tests"] if isinstance(x, str)]
    w = _Work([{"input": s, "output": ""} for s in tests])
    try:
        b = w.build(problem["reference"], "cpp", ["-O1", "-w"])
        if not b:
            return None
        rows = []
        for i, s in enumerate(tests):
            st, _ = "", ""
            r = run_process([b], stdin_path=w.inputs[i], workdir=w.dir, timeout_s=2.0, limits=LIMITS, isolate_network=False, tag=f"ref{i}")
            if r["timed_out"] or r["signal"] is not None or r["rc"] != 0:
                return None
            rows.append({"input": s, "output": r["stdout"]})
        return rows
    finally:
        w.close()


def build_jobs(raw_root: Path, include: tuple[str, ...]) -> tuple[list[dict], Counter]:
    """(jobs, skipped) for every row with a usable label. Code resolves exactly as the merge does."""
    import merge_dataset as M
    from codestream_common import load_problems
    from progpedia_oracle_tests import load_tests

    rows = []
    for path in sorted((DS / "annotations").glob("tier*.jsonl")):
        for line in path.open(encoding="utf-8"):
            if line.strip():
                rows.append(json.loads(line))
    rows, _ = M.apply_review_decisions(rows, DS / "annotations" / "label_review_decisions.jsonl")
    index_csv = ROOT / "data" / "Data_from_Datasets" / "intermediate" / "normalized" / "submissions" / "submissions.csv"
    index = M.load_index(index_csv)
    if (DS / "annotations" / "codenet_index.csv").exists():
        index.update(M.load_index(DS / "annotations" / "codenet_index.csv"))
    ref = M.prefetch_csv_refs(rows, index, raw_root)
    cs = load_problems(raw_root)
    bank = {f"bank-{p['id']}" if not str(p["id"]).startswith("bank-") else p["id"]: p
            for p in _load_bank()}
    synth2 = _synth2_tests()
    tests_of: dict[str, list[dict] | None] = {}
    jobs, skipped = [], Counter()
    for r in rows:
        rid = r["row_id"]
        real = r["dataset_source"] != "SYNTHETIC"
        if real and r.get("label_source") != "human":
            skipped["real_not_human_labelled"] += 1
            continue
        if not real and not rid.startswith(include):
            skipped["synthetic_other_family"] += 1
            continue
        if real:
            rr = dict(r)
            rr["source_code_path"] = index.get(r.get("source_record_id") or "") or r.get("source_code_path")
            code = M.resolve_code(rr, raw_root, ref_index=ref)
        else:
            code = (r.get("static") or {}).get("source_code")
        if not code:
            skipped["no_code"] += 1
            continue
        pid = r["problem_id"]
        if pid not in tests_of:
            tests_of[pid] = _tests_for(pid, cs, bank, synth2, load_tests)
        tests = tests_of[pid]
        if not tests:
            skipped[f"no_tests:{pid.split('-')[1] if '-' in pid else pid}"] += 1
            continue
        jobs.append({"row_id": rid, "code": code, "lang": r.get("language") or "cpp", "tests": tests, "label": r["label"],
                     "problem": pid, "source": r["dataset_source"]})
    return jobs, skipped


def _load_bank() -> list[dict]:
    data = json.loads((ROOT / "data" / "cpp_diagnostics" / "problems.json").read_text(encoding="utf-8"))
    return data["problems"] if isinstance(data, dict) and "problems" in data else data


def _tests_for(pid: str, cs, bank, synth2, load_tests):
    if pid.startswith("tl-codestream-"):
        key = pid
        prob = cs.get(key) or cs.get(pid.replace("tl-codestream-", ""))
        return [{"input": t["input"], "output": t["output"]} for t in prob.tests] if prob and prob.tests else None
    if pid.startswith("tl-progpedia-"):
        return load_tests(pid)
    if pid.startswith("synth2-"):
        p = synth2.get(pid[len("synth2-"):])
        return _reference_outputs(p, "") if p else None
    if pid.startswith("tl-codenet-"):
        import gzip
        path = DS / "oracle_tests" / "codenet" / f"{pid[len('tl-codenet-'):]}.json.gz"
        return json.load(gzip.open(path, "rt", encoding="utf-8")) if path.exists() else None
    if pid.startswith("bank-"):
        p = bank.get(pid)
        return [{"input": t["stdin"], "output": t["expected_output"]} for t in p["test_cases"]] if p else None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="stratified pilot: at most this many rows")
    ap.add_argument("--only-problems", default="", help="comma list of problem ids (pilot on training problems)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--extra", action="store_true", help="only the second set of edits, reusing the stored test results")
    ap.add_argument("--redo-timing", action="store_true",
                    help="first drop stored records whose result could depend on machine speed (a timeout, or an "
                         "uninit comparison that ended abnormally), so they are measured again deterministically")
    a = ap.parse_args()
    a.out = a.out or (OUT_EXTRA if a.extra else OUT)
    if a.redo_timing and a.out.exists():
        kept, dropped = [], 0
        for line in a.out.open(encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            statuses = {t.get("status") for t in ((r.get("tests") or {}).get("results") or [])}
            un = ((r.get("cf") or {}).get("uninit") or {})
            timing = ("timeout" in statuses
                      or bool({un.get("zero_status"), un.get("pattern_status")} & {"timeout", "crash"})
                      or bool((r.get("cf") or {}).get("budget_hit")))
            if timing:
                dropped += 1
            else:
                kept.append(line if line.endswith("\n") else line + "\n")
        a.out.with_suffix(".jsonl.bak").write_text(a.out.read_text(encoding="utf-8"), encoding="utf-8")
        a.out.write_text("".join(kept), encoding="utf-8", newline="\n")
        print(f"redo-timing: dropped {dropped} record(s) to re-measure (backup {a.out.with_suffix('.jsonl.bak').name})", flush=True)
    work = extra_evidence_for if a.extra else evidence_for
    jobs, skipped = build_jobs(a.raw_root, ("stu-",))
    print("jobs", len(jobs), "skipped", dict(skipped), flush=True)
    if a.extra:
        base = {}
        for line in OUT.open(encoding="utf-8"):
            r = json.loads(line)
            if r.get("compiled") and r.get("tests"):
                base[r["row_id"]] = r["tests"]["results"]
        jobs = [{**j, "results": base[j["row_id"]]} for j in jobs if j["row_id"] in base]
    if a.only_problems:
        keep = set(a.only_problems.split(","))
        jobs = [j for j in jobs if j["problem"] in keep or j["source"] == "SYNTHETIC"]
    done = set()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.out.exists():
        done = {json.loads(line)["row_id"] for line in a.out.open(encoding="utf-8") if line.strip()}
    jobs = [j for j in jobs if j["row_id"] not in done]
    if a.limit:
        import random
        rng = random.Random(7)
        rng.shuffle(jobs)
        pos = [j for j in jobs if j["label"] != "CPP_OTHER_ERROR" and j["source"] != "SYNTHETIC"]
        neg = [j for j in jobs if j["label"] == "CPP_OTHER_ERROR" and j["source"] != "SYNTHETIC"]
        syn = [j for j in jobs if j["source"] == "SYNTHETIC"]
        jobs = pos[: a.limit // 2] + neg[: a.limit // 3] + syn[: a.limit // 6]
    # cheap first: short test lists finish sooner, so progress shows early
    jobs.sort(key=lambda j: sum(len(t["input"]) for t in j["tests"]))
    print("to run", len(jobs), Counter(j["source"] for j in jobs), flush=True)
    t0 = time.monotonic()
    with a.out.open("a", encoding="utf-8", newline="\n") as fh, ProcessPoolExecutor(max_workers=a.workers) as ex:
        futures = [ex.submit(work, j) for j in jobs]
        for n, fut in enumerate(as_completed(futures), 1):
            fh.write(json.dumps(fut.result()) + "\n")
            fh.flush()
            if n % 25 == 0 or n == len(jobs):
                print(f"{n}/{len(jobs)} {time.monotonic() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
