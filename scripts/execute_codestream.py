"""U1 — execute every C/C++ CodeStream submission against its own tests.

    python scripts/execute_codestream.py [--raw DIR] [--workers N] [--limit N]
    python scripts/execute_codestream.py --report-only

Writes one result per submission to
  data/misconception_dataset/cache/codestream_exec.jsonl   (gitignored, re-creatable)
and the U1 gate report to
  data/misconception_dataset/reports/u1_executor_report.md

U1 criteria (Master Plan §5): ≥95% of Accepted compile · ≥98% of compiled
Accepted pass all tests · ≥95% of Wrong Answer fail ≥1 test · sanitizer and
Valgrind passes complete on ≥90% of compilable submissions. On a miss the
report lists 10 divergent rows for the investigation the gate requires.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codestream_common import DATASET_DIR, find_raw, load_problems, load_submissions  # noqa: E402
from sandbox_runner import RunConfig, run_many  # noqa: E402

CACHE = DATASET_DIR / "cache"
EXEC_PATH = CACHE / "codestream_exec.jsonl"
REPORT = DATASET_DIR / "reports" / "u1_executor_report.md"


def slim(res: dict) -> dict:
    """Drop bulky text the labeling stage never reads."""
    res = dict(res)
    comp = dict(res.get("compile") or {})
    comp["stderr_head"] = (comp.get("stderr_head") or "")[:600]
    res["compile"] = comp
    return res


def execute(raw, workers: int, limit: int | None, rerun_c_compile_errors: bool = False) -> None:
    probs = load_problems(raw)
    subs = load_submissions(raw)
    if limit:
        subs = subs[:limit]
    done = {}
    if EXEC_PATH.exists():
        for line in EXEC_PATH.open(encoding="utf-8"):
            r = json.loads(line)
            if "error" in r.get("result", {}):
                continue
            if rerun_c_compile_errors and r["lang"] == "c" and not r["result"]["compile"]["ok"]:
                continue  # re-run under the current sandbox version (C stdbool fallback)
            done[r["submission_id"]] = r
        # rewrite the file so it holds exactly one current record per row
        tmp = EXEC_PATH.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for r in done.values():
                f.write(json.dumps(r) + "\n")
        tmp.replace(EXEC_PATH)
    todo = [s for s in subs if s.submission_id not in done]
    print(f"{len(subs)} C/C++ submissions, {len(done)} already executed, {len(todo)} to run",
          flush=True)
    cfg = RunConfig()
    jobs = [(s.code, s.lang, probs[s.problem_id].tests) for s in todo]
    CACHE.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with EXEC_PATH.open("a", encoding="utf-8") as out:
        for i, (s, res) in enumerate(zip(todo, run_many(jobs, cfg, workers=workers,
                                                         cache_dir=str(CACHE / "runs")))):
            out.write(json.dumps({"submission_id": s.submission_id, "verdict": s.verdict,
                                  "lang": s.lang, "result": slim(res)}) + "\n")
            out.flush()
            if (i + 1) % 50 == 0:
                rate = (i + 1) / (time.time() - t0)
                print(f"  {i + 1}/{len(todo)}  {rate:.2f}/s  eta {(len(todo) - i - 1) / rate / 60:.1f} min",
                      flush=True)


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "n/a"


def load_exec() -> dict[str, dict]:
    out = {}
    if EXEC_PATH.exists():
        for line in EXEC_PATH.open(encoding="utf-8"):
            r = json.loads(line)
            out[r["submission_id"]] = r
    return out


def u1_metrics(rows: list[dict]) -> dict:
    acc = [r for r in rows if r["verdict"] == "Accepted"]
    acc_comp = [r for r in acc if r["result"].get("compile", {}).get("ok")]
    acc_pass = [r for r in acc_comp if (r["result"].get("tests") or {}).get("all_passed")]
    acc_pass_lenient = [r for r in acc_comp if (t := r["result"].get("tests") or {})
                        and t.get("total") and t.get("passed_lenient") == t.get("total")]
    wa = [r for r in rows if r["verdict"] == "Wrong Answer"]
    wa_comp = [r for r in wa if r["result"].get("compile", {}).get("ok")]
    wa_fail = [r for r in wa_comp if not (r["result"].get("tests") or {}).get("all_passed")]
    comp = [r for r in rows if r["result"].get("compile", {}).get("ok")]
    san_ok = [r for r in comp if ((r["result"].get("runtime") or {}).get("sanitizer") or {}).get("complete")]
    vg_ok = [r for r in comp if ((r["result"].get("runtime") or {}).get("valgrind") or {}).get("complete")]
    return {
        "accepted": len(acc), "accepted_compiled": len(acc_comp),
        "accepted_all_pass": len(acc_pass), "accepted_all_pass_lenient": len(acc_pass_lenient),
        "wa": len(wa), "wa_compiled": len(wa_comp), "wa_fail": len(wa_fail),
        "compiled": len(comp), "sanitizer_complete": len(san_ok), "valgrind_complete": len(vg_ok),
        "lists": {"acc_not_compiled": [r for r in acc if r not in acc_comp],
                  "acc_not_pass": [r for r in acc_comp if r not in acc_pass],
                  "wa_pass": [r for r in wa_comp if r not in wa_fail]},
    }


def report(raw) -> None:
    ex = load_exec()
    subs = {s.submission_id: s for s in load_submissions(raw)}
    rows = [ex[k] for k in subs if k in ex]
    m = u1_metrics(rows)
    checks = [
        ("Accepted compile", m["accepted_compiled"], m["accepted"], 0.95),
        ("Compiled Accepted pass all tests", m["accepted_all_pass"], m["accepted_compiled"], 0.98),
        ("Wrong Answer fail >=1 test", m["wa_fail"], m["wa_compiled"], 0.95),
        ("Sanitizer pass complete (compilable)", m["sanitizer_complete"], m["compiled"], 0.90),
        ("Valgrind pass complete (compilable)", m["valgrind_complete"], m["compiled"], 0.90),
    ]
    by_verdict = Counter()
    branch = Counter()
    for r in rows:
        res = r["result"]
        branch[(r["verdict"], res.get("branch", "error" if "error" in res else "?"))] += 1
        by_verdict[r["verdict"]] += 1
    lines = ["# U1 executor report — CodeStream C/C++", "",
             "Generated by `scripts/execute_codestream.py`. Do not edit by hand.", "",
             f"- Executed: {len(rows)} of {len(subs)} C/C++ submissions",
             f"- sandbox_runner {rows[0]['result'].get('sandbox_version') if rows else '?'} · "
             f"config `{rows[0]['result'].get('config_fingerprint') if rows else '?'}` · "
             f"backend `{rows[0]['result'].get('backend') if rows else '?'}`",
             f"- Toolchain: `{rows[0]['result'].get('toolchain') if rows else '?'}`", "",
             "## Gate U1", "", "| Check | Count | Rate | Target | Result |", "|---|---:|---:|---:|---|"]
    all_ok = True
    for name, a, b, tgt in checks:
        ok = b > 0 and a / b >= tgt
        all_ok &= ok
        lines.append(f"| {name} | {a}/{b} | {pct(a, b)} | ≥{int(tgt * 100)}% | {'PASS' if ok else 'FAIL'} |")
    lines.append(f"| *(lenient: Accepted pass incl. presentation)* | {m['accepted_all_pass_lenient']}/{m['accepted_compiled']} | {pct(m['accepted_all_pass_lenient'], m['accepted_compiled'])} | — | info |")
    lines += ["", f"**U1 overall: {'PASS' if all_ok else 'FAIL — see divergence investigation'}**", "",
              "## Branch by source verdict", "", "| Source verdict | compile_error | all_pass | timeout_only | failing | error |",
              "|---|---:|---:|---:|---:|---:|"]
    for v in sorted(by_verdict, key=lambda x: -by_verdict[x]):
        lines.append(f"| {v} | " + " | ".join(str(branch[(v, b)]) for b in
                     ("compile_error", "all_pass", "timeout_only", "failing", "error")) + " |")
    lines += ["", "## Divergence investigation (up to 10 rows per list)", ""]
    for key, title in (("acc_not_compiled", "Accepted but does not compile here"),
                       ("acc_not_pass", "Accepted, compiles, fails a test here"),
                       ("wa_pass", "Wrong Answer but passes every test here")):
        lst = m["lists"][key]
        lines.append(f"### {title} — {len(lst)} rows")
        lines.append("")
        for r in lst[:10]:
            res = r["result"]
            s = subs[r["submission_id"]]
            if key == "acc_not_compiled":
                errs = (res.get("compile") or {}).get("errors") or []
                why = errs[0]["message"][:140] if errs else (res.get("compile") or {}).get("stderr_head", "")[:140]
            else:
                t = res.get("tests") or {}
                why = f"passed {t.get('passed')}/{t.get('total')} · statuses {t.get('status_counts')}"
            lines.append(f"- `{r['submission_id'][-24:]}` {s.source_problem_id} {s.lang}: {why}")
        lines.append("")
    # ---- per-problem agreement with the source judge ------------------------
    per = {}
    for r in rows:
        s = subs[r["submission_id"]]
        d = per.setdefault(s.problem_id, Counter())
        res = r["result"]
        if r["verdict"] == "Accepted" and res.get("compile", {}).get("ok"):
            d["acc"] += 1
            d["acc_pass"] += int(bool((res.get("tests") or {}).get("all_passed")))
        if r["verdict"] == "Wrong Answer" and res.get("compile", {}).get("ok"):
            d["wa"] += 1
            d["wa_pass"] += int(bool((res.get("tests") or {}).get("all_passed")))
    flagged = {p for p, d in per.items() if d["acc"] >= 3 and d["acc_pass"] / d["acc"] < 0.9}
    lines += ["## Problems whose embedded tests disagree with the source judge", "",
              "A problem is flagged when <90% of its compiled Accepted submissions pass its embedded "
              "tests here (≥3 Accepted). Its failing rows are excluded from labeling: a failure there "
              "may not be a student error.", "",
              "| Problem | Accepted pass here | WA pass here | Flag |", "|---|---:|---:|---|"]
    for p in sorted(per):
        d = per[p]
        if d["acc"] and (d["acc_pass"] < d["acc"] or d["wa_pass"]):
            lines.append(f"| {p} | {d['acc_pass']}/{d['acc']} | {d['wa_pass']}/{d['wa']} | "
                         f"{'tests_unreliable' if p in flagged else ''} |")
    rest = [r for r in rows if subs[r["submission_id"]].problem_id not in flagged]
    m2 = u1_metrics(rest)
    lines += ["", f"Secondary view excluding flagged problems ({len(flagged)}): compiled Accepted pass "
              f"{m2['accepted_all_pass']}/{m2['accepted_compiled']} ({pct(m2['accepted_all_pass'], m2['accepted_compiled'])}); "
              f"WA fail {m2['wa_fail']}/{m2['wa_compiled']} ({pct(m2['wa_fail'], m2['wa_compiled'])}).",
              "The primary gate above is reported unfiltered.", "",
              "Note: for 1,263 of 3,396 rows the source `verdict_sequence_trace` has a different length "
              "than the embedded test list, so the judge ran tests we do not have. That explains most "
              "Wrong Answer rows that pass here.", ""]
    flag_path = DATASET_DIR / "splits" / "codestream_problem_flags.csv"
    with open(flag_path, "w", encoding="utf-8", newline="") as f:
        f.write("problem_id,accepted_compiled,accepted_pass_here,flag\n")
        for p in sorted(per):
            d = per[p]
            f.write(f"{p},{d['acc']},{d['acc_pass']},{'tests_unreliable' if p in flagged else ''}\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--rerun-c-compile-errors", action="store_true")
    a = ap.parse_args()
    raw = find_raw(a.raw)
    if not a.report_only:
        execute(raw, a.workers or 2, a.limit, a.rerun_c_compile_errors)
    report(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
