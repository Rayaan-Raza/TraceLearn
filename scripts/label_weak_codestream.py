"""U2/U3/U4 — label CodeStream C/C++ rows (Lane B, owner Umaima).

    python scripts/execute_codestream.py            # U1 first: execution cache
    python scripts/label_weak_codestream.py [--pilot 150] [--workers 2]

Per row (only the ``failing`` branch — compile errors, all-pass and
timeout-without-crash are deterministic pre-branches, §1):

1. run every LF (two-signal conjunctions, ``codestream_lfs``);
2. for every fired class with an inverse operator, try repair-and-rerun
   (``repair_verify``); a unique verified class is ``repair_verified``;
3. otherwise a single fired floor class is a ``weak_rule`` (silver) label;
4. several different classes → ``multi_signal`` review pool (never force-picked);
5. classes 4, 8, 9, 10 → ``discovery`` review pool (human-confirmed only, §13.5);
6. no fire → **unlabeled** (never OTHER_ERROR); a seeded sample goes to the
   OTHER_ERROR human-confirmation pool.

Outputs (data/misconception_dataset/):
  annotations/tier1a_codestream.jsonl            labeled rows (all pools, tagged)
  annotations/review/multi_signal.jsonl          for human promotion or UNCERTAIN
  annotations/review/discovery_candidates.jsonl  classes 4/8/9/10, ranked
  annotations/review/other_error_candidates.jsonl
  annotations/review/lf_audit_sheet.csv          ≥50 fires per LF to audit (blind columns)
  annotations/lf_audits.csv                      audit results → Beta-bound confidence
  reports/u2_labeling_report.md · reports/selection_report.md
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from codestream_common import (  # noqa: E402
    DATASET_DIR, SCHEMA_VERSION, TAXONOMY_VERSION, find_raw, load_problems, load_submissions,
    previous_submission_index, user_hash, write_jsonl,
)
from codestream_lfs import (  # noqa: E402
    DISCOVERY_CLASSES, FLOOR_CLASSES, LF_REGISTRY, SOURCE_CAP, Ctx, confidence, run_lfs,
)
from codestream_static import parse  # noqa: E402
from repair_verify import GENERATORS, verify  # noqa: E402
from sandbox_runner.compare import compare_output  # noqa: E402

ANN = DATASET_DIR / "annotations"
REVIEW = ANN / "review"
REPORTS = DATASET_DIR / "reports"
EXEC_PATH = DATASET_DIR / "cache" / "codestream_exec.jsonl"
AUDITS = ANN / "lf_audits.csv"
SEED = 20261021


# --------------------------------------------------------------- per row --

def refresh_diffs(result: dict, tests: list[dict]) -> dict:
    """Recompute diff evidence from stored stdout when it was kept whole, so
    rows executed by an older sandbox_runner get the newest diff fields."""
    t = result.get("tests") or {}
    for r in t.get("results", []):
        out = r.get("stdout_head")
        if r.get("status") in ("wrong", "presentation") and out is not None \
                and len(out) < 2048 and r["idx"] < len(tests):
            cmp = compare_output(out, tests[r["idx"]]["output"])
            r["diff"] = {k: v for k, v in cmp.items() if k != "status"}
    return result


def decide(code: str, lang: str, tests: list[dict], result: dict, *, cache_dir: str | None = None,
           do_repair: bool = True) -> dict:
    """Return the labeling decision for one executed row."""
    branch = result.get("branch")
    if branch != "failing":
        return {"decision": "pre_branch", "branch": branch, "fires": [], "repairs": []}
    result = refresh_diffs(result, tests)
    prog = parse(code)
    fires = run_lfs(Ctx(code, prog, result, tests))
    classes = sorted({f.cls for f in fires})
    repairs = []
    if do_repair:
        for cls in classes:
            if cls in GENERATORS:
                lines = None
                if cls == "CPP_UNINITIALIZED_VAR":
                    lines = set(next(f.evidence.get("warning_lines", []) for f in fires
                                     if f.cls == cls))
                repairs.append(verify(code, lang, tests, cls, prog=prog, cache_dir=cache_dir,
                                      lines=lines))
    verified = [r["class"] for r in repairs if r["verified"]]
    out = {"branch": branch, "fires": [{"lf": f.lf, "class": f.cls, "evidence": f.evidence}
                                       for f in fires],
           "fired_classes": classes, "firing_count": len(classes), "repairs": repairs,
           "verified_classes": verified}
    if len(verified) == 1:
        cls = verified[0]
        out.update(decision="discovery" if cls in DISCOVERY_CLASSES else "repair_verified",
                   label=cls, secondary=[c for c in classes if c != cls])
    elif len(verified) > 1:
        out.update(decision="multi_signal", label=None, secondary=classes,
                   reason="several inverse operators each fix every test")
    elif len(classes) == 1:
        cls = classes[0]
        out.update(decision="discovery" if cls in DISCOVERY_CLASSES else "weak_rule",
                   label=cls, secondary=[])
    elif len(classes) > 1:
        floor = [c for c in classes if c in FLOOR_CLASSES]
        disc = [c for c in classes if c in DISCOVERY_CLASSES]
        if not floor and disc:
            out.update(decision="discovery", label=None, secondary=classes)
        else:
            out.update(decision="multi_signal", label=None, secondary=classes,
                       reason="LFs for different classes fired")
    else:
        out.update(decision="no_fire", label=None, secondary=[])
    return out


def _decide_job(args):
    code, lang, tests, result, cache_dir = args
    try:
        return decide(code, lang, tests, result, cache_dir=cache_dir)
    except Exception as exc:
        return {"decision": "error", "error": f"{type(exc).__name__}: {exc}", "fires": [],
                "repairs": []}


# ------------------------------------------------------------- audits -----

def load_audits() -> dict:
    """lf_audits.csv rows: key,audited,correct (key = LF name or repair_verified:<CLASS>)."""
    out = {}
    if AUDITS.exists():
        with open(AUDITS, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("key"):
                    out[r["key"]] = (int(r.get("correct") or 0), int(r.get("audited") or 0))
    return out


def ensure_audit_template() -> None:
    if AUDITS.exists():
        return
    AUDITS.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDITS, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["key", "audited", "correct", "auditor", "date", "notes"])
        for k in LF_REGISTRY:
            w.writerow([k, 0, 0, "", "", "fill from review/lf_audit_sheet.csv"])
        for c in sorted(GENERATORS):
            w.writerow([f"repair_verified:{c}", 0, 0, "", "", ""])


# ------------------------------------------------------------- rows -------

def slim_runtime(result: dict) -> dict:
    rt = result.get("runtime") or {}
    san = rt.get("sanitizer") or {}
    vg = rt.get("valgrind") or {}
    return {"any_crash": rt.get("any_crash"), "any_timeout": rt.get("any_timeout"),
            "signals": rt.get("signals"), "stack_overflow": rt.get("stack_overflow"),
            "max_seconds": rt.get("max_seconds"),
            "sanitizer": {"complete": san.get("complete"), "kinds": san.get("kinds"),
                          "reports": (san.get("reports") or [])[:6]},
            "valgrind": {"complete": vg.get("complete"), "kinds": vg.get("kinds"),
                         "uninit": vg.get("uninit"), "error_count": vg.get("error_count")}}


def slim_tests(result: dict) -> dict:
    t = result.get("tests") or {}
    return {"total": t.get("total"), "passed": t.get("passed"),
            "passed_lenient": t.get("passed_lenient"), "first_failed": t.get("first_failed"),
            "status_counts": t.get("status_counts"), "flaky": t.get("flaky"),
            "results": [{k: v for k, v in r.items() if k not in ("stderr_head",)}
                        for r in t.get("results", [])]}


def build_row(n: int, s, prob, pool: str, cluster: str, result: dict, dec: dict, audits: dict,
              prev: str | None, run_id: str) -> dict:
    label = dec.get("label")
    src = {"repair_verified": "repair_verified", "weak_rule": "weak_rule"}.get(dec["decision"])
    conf = None
    audit = None
    if src == "repair_verified":
        conf, k, m = confidence(f"repair_verified:{label}", audits)
        audit = {"key": f"repair_verified:{label}", "correct": k, "audited": m}
    elif src == "weak_rule":
        lf = next(f["lf"] for f in dec["fires"] if f["class"] == label)
        conf, k, m = confidence(lf, audits)
        audit = {"key": lf, "correct": k, "audited": m}
    rep = next((r for r in dec.get("repairs", []) if r.get("verified") and r["class"] == label), None)
    return {
        "row_id": f"cs-{n:06d}",
        "dataset_source": "CODESTREAM",
        "source_record_id": s.source_submission_id,
        "submission_id": s.submission_id,
        "problem_id": s.problem_id,
        "problem_cluster": cluster,
        "split_pool": pool,
        "language": s.lang,
        "label": label,
        "label_source": src,
        "label_confidence": conf,
        "label_status": dec["decision"],
        "secondary_labels": dec.get("secondary", []),
        "verdict": s.verdict,
        "firing_functions": sorted({f["lf"] for f in dec["fires"]}),
        "firing_count": dec.get("firing_count", 0),
        "lf_evidence": dec["fires"],
        "audit": audit,
        "seed_ref": None,
        "mutation_op": None,
        "repair": ({"op": rep["repair"]["op"], "line": rep["repair"]["line"],
                    "before": rep["repair"]["before"][:200], "after": rep["repair"]["after"][:200],
                    "proof": rep["proof"]} if rep else None),
        "repair_tries": [{"class": r["class"], "verified": r["verified"], "tries": len(r["tries"])}
                         for r in dec.get("repairs", [])],
        "verified_by_execution": src == "repair_verified",
        "meta": {"user_id_hash": user_hash(s.user_id), "attempt_index": s.attempt_number,
                 "timestamp": None, "prev_submission_id": prev},
        "static": None,  # filled by tracelearn_features v0 at merge (schema fallback, §5)
        "warnings": (result.get("warnings") or {}).get("count_by_flag"),
        "runtime": slim_runtime(result),
        "tests": slim_tests(result),
        "cpg": None,
        "context": {"source_problem_id": s.source_problem_id, "tests_total": len(prob.tests),
                    "statement_chars": len(prob.statement)},
        "pipeline_run_id": run_id,
        "taxonomy_version": TAXONOMY_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


# ------------------------------------------------------------- main -------

def load_pools() -> dict:
    p = DATASET_DIR / "splits" / "codestream_clusters.csv"
    with open(p, encoding="utf-8") as f:
        return {r["problem_id"]: (r["problem_cluster"], r["pool"]) for r in csv.DictReader(f)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--pilot", type=int, default=0, help="label only N train-side failing rows")
    ap.add_argument("--other-sample", type=int, default=400)
    a = ap.parse_args()

    raw = find_raw(a.raw)
    probs = load_problems(raw)
    subs = load_submissions(raw)
    prev = previous_submission_index(subs)
    pools = load_pools()
    execd = {}
    for line in EXEC_PATH.open(encoding="utf-8"):
        r = json.loads(line)
        execd[r["submission_id"]] = r["result"]
    rows = [s for s in subs if s.submission_id in execd]
    if a.pilot:
        rng = random.Random(SEED)
        cand = [s for s in rows if execd[s.submission_id].get("branch") == "failing"
                and pools[s.problem_id][1] == "train"]
        rng.shuffle(cand)
        rows = cand[:a.pilot]
    print(f"labeling {len(rows)} executed rows", flush=True)
    cache_dir = str(DATASET_DIR / "cache" / "repairs")
    jobs = [(s.code, s.lang, probs[s.problem_id].tests, execd[s.submission_id], cache_dir)
            for s in rows]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        decisions = list(ex.map(_decide_job, jobs, chunksize=4))

    ensure_audit_template()
    audits = load_audits()
    run_id = "run-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + \
        hashlib.sha256(EXEC_PATH.read_bytes()).hexdigest()[:8]
    labeled, multi, disc, nofire = [], [], [], []
    stats = Counter()
    for n, (s, dec) in enumerate(zip(rows, decisions), 1):
        stats[dec["decision"]] += 1
        if dec["decision"] in ("pre_branch", "error"):
            continue
        cluster, pool = pools[s.problem_id]
        row = build_row(n, s, probs[s.problem_id], pool, cluster, execd[s.submission_id], dec,
                        audits, prev.get(s.submission_id), run_id)
        if dec["decision"] in ("repair_verified", "weak_rule"):
            labeled.append(row)
        elif dec["decision"] == "multi_signal":
            multi.append(row)
        elif dec["decision"] == "discovery":
            disc.append(row)
        else:
            nofire.append(row)

    suffix = "_pilot" if a.pilot else ""
    write_jsonl(ANN / f"tier1a_codestream{suffix}.jsonl", labeled)
    write_jsonl(REVIEW / f"multi_signal{suffix}.jsonl", multi)
    # discovery: verified repairs first, then by number of supporting signals
    disc.sort(key=lambda r: (r["repair"] is None, -r["firing_count"], r["row_id"]))
    write_jsonl(REVIEW / f"discovery_candidates{suffix}.jsonl", disc)
    rng = random.Random(SEED)
    other = list(nofire)
    rng.shuffle(other)
    write_jsonl(REVIEW / f"other_error_candidates{suffix}.jsonl", other[:a.other_sample])
    write_audit_sheet(labeled + disc + multi, suffix)
    write_reports(rows, decisions, labeled, multi, disc, nofire, stats, pools, suffix, run_id)
    errors = [d for d in decisions if d["decision"] == "error"]
    if errors:
        print(f"{len(errors)} rows errored, e.g. {errors[0]['error']}")
    return 0


def write_audit_sheet(rows: list[dict], suffix: str) -> None:
    """Up to 60 fires per LF (seeded) for the ≥50-fire precision audit. Columns
    the auditor fills: audit_correct (y/n), audit_true_class, auditor, notes."""
    by_lf = defaultdict(list)
    for r in rows:
        for f in r["lf_evidence"]:
            by_lf[f["lf"]].append((r, f))
    rng = random.Random(SEED)
    path = REVIEW / f"lf_audit_sheet{suffix}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["lf", "fired_class", "row_id", "submission_id", "problem_id", "split_pool",
                    "label_status", "repair_verified", "evidence", "audit_correct",
                    "audit_true_class", "auditor", "notes"])
        for lf in sorted(by_lf):
            items = by_lf[lf]
            rng.shuffle(items)
            for r, f in items[:60]:
                w.writerow([lf, f["class"], r["row_id"], r["submission_id"], r["problem_id"],
                            r["split_pool"], r["label_status"],
                            bool(r["repair"]) and r["label"] == f["class"],
                            json.dumps(f["evidence"])[:300], "", "", "", ""])


def write_reports(rows, decisions, labeled, multi, disc, nofire, stats, pools, suffix, run_id):
    REPORTS.mkdir(parents=True, exist_ok=True)
    cls_pool = Counter()
    for r in labeled:
        cls_pool[(r["label"], r["label_source"], r["split_pool"])] += 1
    lf_fires = Counter()
    lf_verified = Counter()
    for d in decisions:
        for f in d.get("fires", []):
            lf_fires[f["lf"]] += 1
        for r in d.get("repairs", []):
            if r.get("verified"):
                lf_verified[r["class"]] += 1
    disc_cls = Counter()
    for r in disc:
        for c in ([r["label"]] if r["label"] else r["secondary_labels"]):
            disc_cls[(c, "repair" if r["repair"] else "detector")] += 1
    failing = [d for d in decisions if d.get("branch") == "failing"]
    fc = Counter(min(d.get("firing_count", 0), 2) for d in failing)
    L = [f"# U2 labeling report — CodeStream{' (pilot)' if suffix else ''}", "",
         "Generated by `scripts/label_weak_codestream.py`. Do not edit by hand.", "",
         f"- Run: `{run_id}` · rows considered: {len(rows)} · failing branch: {len(failing)}",
         f"- Decisions: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())),
         f"- Firing count over failing rows: 0 → {fc[0]}, 1 → {fc[1]}, 2+ → {fc[2]}", "",
         "## Labeled rows by class, source and pool", "",
         "| Class | repair_verified train | weak_rule train | repair_verified dev/test | weak_rule dev/test | Floor (train, §8) |",
         "|---|---:|---:|---:|---:|---:|"]
    floor = {"CPP_LOOP_BOUNDARY": 100, "CPP_OFF_BY_ONE": 100, "CPP_ARRAY_BOUNDS": 100,
             "CPP_INT_OVERFLOW": 100, "CPP_MISSING_BASE_CASE": 100, "CPP_ASSIGN_VS_COMPARE": 100}
    for c in FLOOR_CLASSES:
        rv_t = cls_pool[(c, "repair_verified", "train")]
        wr_t = cls_pool[(c, "weak_rule", "train")]
        rv_o = cls_pool[(c, "repair_verified", "dev_gold")] + cls_pool[(c, "repair_verified", "test")]
        wr_o = cls_pool[(c, "weak_rule", "dev_gold")] + cls_pool[(c, "weak_rule", "test")]
        L.append(f"| {c} | {rv_t} | {wr_t} | {rv_o} | {wr_o} | {floor[c]} |")
    L += ["", "Rows in dev-gold/test clusters never enter training; they are the gold-form pool.", "",
          "## LF fires and repair verification", "",
          "| LF | Class | Kind | Fires | Repairs verified (class) |", "|---|---|---|---:|---:|"]
    for lf, meta in LF_REGISTRY.items():
        L.append(f"| {lf} | {meta['class']} | {meta['kind']} | {lf_fires[lf]} | {lf_verified[meta['class']]} |")
    L += ["", "## Discovery pool (classes 4, 8, 9, 10 — human confirmation required)", "",
          "| Class | With verified repair | Detector only |", "|---|---:|---:|"]
    for c in DISCOVERY_CLASSES:
        L.append(f"| {c} | {disc_cls[(c, 'repair')]} | {disc_cls[(c, 'detector')]} |")
    L += ["", f"- multi_signal pool: {len(multi)} rows", f"- no LF fired (unlabeled, never OTHER): {len(nofire)} rows",
          "", "## Confidence", "",
          "`label_confidence` = min(0.85, Beta(1,1) posterior lower 80% bound of audited precision)"
          " from `annotations/lf_audits.csv`. Before audits are entered it is 0.2 for every row —"
          " fill the audit sheet (≥50 fires per LF) and re-run to update.", ""]
    (REPORTS / f"u2_labeling_report{suffix}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    write_selection_report(rows, decisions, pools, suffix)


def _psi(a: list[float], b: list[float], bins: int = 10) -> float | None:
    import math
    if len(a) < 5 or len(b) < 5:
        return None
    allv = sorted(a + b)
    edges = [allv[int(len(allv) * i / bins)] for i in range(1, bins)]

    def hist(v):
        h = [0] * bins
        for x in v:
            k = sum(1 for e in edges if x > e)
            h[k] += 1
        return [(c + 0.5) / (len(v) + 0.5 * bins) for c in h]
    ha, hb = hist(a), hist(b)
    return round(sum((x - y) * math.log(x / y) for x, y in zip(ha, hb)), 4)


def _ks(a: list[float], b: list[float]) -> float | None:
    if len(a) < 5 or len(b) < 5:
        return None
    pts = sorted(set(a + b))
    sa, sb = sorted(a), sorted(b)
    import bisect
    return round(max(abs(bisect.bisect_right(sa, x) / len(sa) - bisect.bisect_right(sb, x) / len(sb))
                     for x in pts), 4)


def write_selection_report(rows, decisions, pools, suffix):
    """§9.0-G5: single / multi / none-firing fractions per problem, and KS / PSI
    of simple row descriptors for single-firing rows vs the rest."""
    per_problem = defaultdict(Counter)
    single, rest = defaultdict(list), defaultdict(list)
    for s, d in zip(rows, decisions):
        if d.get("branch") != "failing":
            continue
        fc = d.get("firing_count", 0)
        key = "none" if fc == 0 else ("single" if fc == 1 else "multi")
        per_problem[s.problem_id][key] += 1
        desc = {"code_lines": s.code.count("\n") + 1, "attempt": s.attempt_number}
        tgt = single if fc == 1 else rest
        for k, v in desc.items():
            tgt[k].append(float(v))
    L = [f"# Selection report — CodeStream{' (pilot)' if suffix else ''}", "",
         "Single-firing selection bias check (Master Plan §9.0-G5, §14).", "",
         "| Descriptor | KS single vs rest | PSI single vs rest |", "|---|---:|---:|"]
    for k in ("code_lines", "attempt"):
        L.append(f"| {k} | {_ks(single[k], rest[k])} | {_psi(single[k], rest[k])} |")
    L += ["", "| Problem | Pool | none | single | multi |", "|---|---|---:|---:|---:|"]
    for pid in sorted(per_problem):
        c = per_problem[pid]
        L.append(f"| {pid} | {pools[pid][1]} | {c['none']} | {c['single']} | {c['multi']} |")
    (REPORTS / f"selection_report{suffix}.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
