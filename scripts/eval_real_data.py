"""Evaluate the serving model on REAL student code from CodeStream (docs/6-nov.md §9).

    wsl python3 scripts/eval_real_data.py --pool dev_gold --raw /mnt/g/TraceLearn/Datasets_RAW
    wsl python3 scripts/eval_real_data.py --pool test     --raw ... --confirm-test-run

What it does, per pool of held-out problem clusters:

1. Execute every C/C++ submission against the problem's own tests with the
   cheap sandbox config (compile warnings + tests, no sanitizer / Valgrind), so
   the features match what the live server can compute. Cached on disk.
2. Build the feature vector with the same normalize path the dataset used and
   score the SERVING variants (`best`, `common`; never `full`, which fails the
   R4 source-shortcut gate).
3. T3 behaviour: abstain rate, predicted-class histogram, router coverage,
   label stability on consecutive failed attempts of the same student.
4. T2 repair confirmation: for the model's top class, does an automatic repair
   of that class make every test pass? Compared with a prior-matched random
   class and the labeling-function rule on the same rows, with a bootstrap CI
   resampled by problem.

Honest limits (also written into the report):
- T2 measures behavioural fit, not what the student believes. The repair
  operators are the same family that generated the synthetic training rows, so
  a good T2 score is supporting evidence, never accuracy. Human gold (G6) is
  the claim-grade test.
- Problems whose tests disagree with the source judge are excluded
  (`codestream_problem_flags.csv`), as the labeler does.
- The test pool is evaluated ONCE: it needs --confirm-test-run, and every run
  is appended to reports/real_eval_runs.jsonl.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from tracelearn_features.schema import feature_names as schema_feature_names  # noqa: E402

DATASET_DIR = ROOT / "data" / "misconception_dataset"
CACHE_DIR = DATASET_DIR / "cache"
REPORTS = DATASET_DIR / "reports"
SERVING_VARIANTS = ("best", "common")
BOOTSTRAP = 1000
SEED = 20261106


# --------------------------------------------------------------- pure helpers


def flatten_blocks(normalized: dict[str, Any], names: Sequence[str]) -> dict[str, float | None]:
    """Normalized row -> {"block.feature": value} for the feature names a model wants."""
    out: dict[str, float | None] = {}
    for name in names:
        block, _, short = name.partition(".")
        value = (normalized.get(block) or {}).get(short)
        if isinstance(value, bool):
            value = float(value)
        out[name] = value if isinstance(value, (int, float)) and math.isfinite(value) else None
    return out


def bootstrap_ci(by_problem: dict[str, list[float]], rng: random.Random, n: int = BOOTSTRAP) -> tuple[float, float, float]:
    """Mean of a 0/1 outcome with a 95% CI, resampling PROBLEMS (not rows)."""
    problems = sorted(by_problem)
    if not problems:
        return math.nan, math.nan, math.nan

    def rate(sample: list[str]) -> float:
        flat = [v for p in sample for v in by_problem[p]]
        return sum(flat) / len(flat) if flat else math.nan

    point = rate(problems)
    draws = sorted(
        d for d in (rate([rng.choice(problems) for _ in problems]) for _ in range(n)) if not math.isnan(d)
    )
    if not draws:
        return point, math.nan, math.nan
    return point, draws[int(0.025 * (len(draws) - 1))], draws[int(0.975 * (len(draws) - 1))]


def paired_difference_ci(
    a: dict[str, list[float]], b: dict[str, list[float]], rng: random.Random, n: int = BOOTSTRAP
) -> tuple[float, float, float]:
    """mean(a) - mean(b) on the same rows, 95% CI resampling problems. a and b are aligned per problem."""
    problems = sorted(set(a) & set(b))
    if not problems:
        return math.nan, math.nan, math.nan

    def diff(sample: list[str]) -> float:
        fa = [v for p in sample for v in a[p]]
        fb = [v for p in sample for v in b[p]]
        return (sum(fa) / len(fa) - sum(fb) / len(fb)) if fa and fb else math.nan

    point = diff(problems)
    draws = sorted(d for d in (diff([rng.choice(problems) for _ in problems]) for _ in range(n)) if not math.isnan(d))
    if not draws:
        return point, math.nan, math.nan
    return point, draws[int(0.025 * (len(draws) - 1))], draws[int(0.975 * (len(draws) - 1))]


def expected_chance_agreement(labels: Sequence[str]) -> float:
    """Probability two independent draws from this label distribution agree."""
    total = len(labels)
    if not total:
        return math.nan
    return sum((c / total) ** 2 for c in Counter(labels).values())


def consecutive_failed_pairs(rows: Sequence[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Adjacent attempts (same student, same problem) that both fail, in attempt order."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["user_hash"], row["problem_id"])].append(row)
    pairs = []
    for attempts in groups.values():
        attempts.sort(key=lambda r: r["attempt_number"])
        for prev, nxt in zip(attempts, attempts[1:]):
            if nxt["attempt_number"] == prev["attempt_number"] + 1 and prev["branch"] == nxt["branch"] == "failing":
                pairs.append((prev, nxt))
    return pairs


# ------------------------------------------------------------- data loading


def load_pool_map() -> dict[str, tuple[str, str]]:
    with (DATASET_DIR / "splits" / "codestream_clusters.csv").open(encoding="utf-8", newline="") as fh:
        return {r["problem_id"]: (r["problem_cluster"], r["pool"]) for r in csv.DictReader(fh)}


def unreliable_problems() -> set[str]:
    path = DATASET_DIR / "splits" / "codestream_problem_flags.csv"
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["problem_id"] for r in csv.DictReader(fh) if r["flag"] == "tests_unreliable"}


def execute_one(job: tuple[str, str, list[dict]]) -> dict[str, Any]:
    from sandbox_runner import RunConfig, run_submission

    code, lang, tests = job
    cfg = RunConfig(sanitizer_pass=False, valgrind_pass=False, double_run=False)
    try:
        return run_submission(code, lang, tests, cfg)
    except Exception as exc:  # one bad submission must not stop the pool
        return {"error": f"{type(exc).__name__}: {exc}"}


def execute_pool(subs: list[Any], probs: dict[str, Any], cache_path: Path, workers: int) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if cache_path.exists():
        for line in cache_path.open(encoding="utf-8"):
            rec = json.loads(line)
            if "error" not in rec["result"]:
                done[rec["submission_id"]] = rec["result"]
    todo = [s for s in subs if s.submission_id not in done]
    print(f"executing {len(todo)} of {len(subs)} submissions ({len(done)} cached)", flush=True)
    if todo:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        jobs = [(s.code, s.lang, probs[s.problem_id].tests) for s in todo]
        with ProcessPoolExecutor(max_workers=workers) as ex, cache_path.open("a", encoding="utf-8", newline="\n") as out:
            for s, res in zip(todo, ex.map(execute_one, jobs, chunksize=2)):
                if "error" in res:
                    continue
                done[s.submission_id] = res
                out.write(json.dumps({"submission_id": s.submission_id, "result": res}) + "\n")
                out.flush()
    return done


def write_feature_dump(rows: Sequence[dict[str, Any]], path: Path) -> None:
    """Every scored row's full feature vector, for shift and drift analysis (gitignored cache)."""
    names = list(schema_feature_names())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["submission_id", "problem_id", "cluster", "user_hash", "attempt_number", "verdict", "branch", *names])
        for r in rows:
            writer.writerow([r["submission_id"], r["problem_id"], r["cluster"], r["user_hash"], r["attempt_number"],
                             r["verdict"], r["branch"], *["" if r["features"][n] is None else r["features"][n] for n in names]])


def feature_row(sub: Any, prob: Any, result: dict[str, Any]) -> dict[str, Any]:
    """The row shape the labeler emits for a CodeStream submission, normalized."""
    from label_weak_codestream import slim_runtime, slim_tests

    from tracelearn_features.normalize import normalize_row

    row = {
        "dataset_source": "CODESTREAM",
        "language": sub.lang,
        "warnings": (result.get("warnings") or {}).get("count_by_flag"),
        "runtime": slim_runtime(result),
        "tests": slim_tests(result),
        "context": {"source_problem_id": sub.source_problem_id, "tests_total": len(prob.tests),
                    "statement_chars": len(prob.statement)},
    }
    return normalize_row(row, code=sub.code)


# ------------------------------------------------------------- repair checks


def _repair_job(job: tuple[str, str, list[dict], str, str, list[dict]]) -> dict[str, Any]:
    """Try the inverse operators of one class on one submission.

    `verified`: some edit makes EVERY test pass (causal proof, rare on real code).
    `partial`: some edit fixes the first failing test without breaking a test
    that passed before (the labeler's first-divergent-test rule, section 3.2).
    """
    from codestream_static import parse
    from repair_verify import verify

    code, lang, tests, cls, cache_dir, orig = job
    try:
        res = verify(code, lang, tests, cls, prog=parse(code), cache_dir=cache_dir, orig_results=orig)
        return {"verified": bool(res["verified"]), "partial": res.get("partial") is not None,
                "tries": len(res["tries"])}
    except Exception as exc:
        return {"verified": False, "partial": False, "error": f"{type(exc).__name__}: {exc}"}


def _rule_class(job: tuple[str, str, list[dict], dict]) -> str | None:
    """Labeling-function baseline: the class with most LF fires (ties alphabetical)."""
    from codestream_lfs import Ctx, run_lfs
    from codestream_static import parse

    code, _lang, tests, result = job
    try:
        fires = run_lfs(Ctx(code, parse(code), result, tests))
    except Exception:
        return None
    counts = Counter(f.cls for f in fires)
    if not counts:
        return None
    best = max(counts.values())
    return sorted(c for c, n in counts.items() if n == best)[0]


def training_prior(generators: Sequence[str]) -> tuple[list[str], list[float]]:
    counts: Counter[str] = Counter()
    with (DATASET_DIR / "annotations" / "labels.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                label = json.loads(line)["label"]
                if label in generators:
                    counts[label] += 1
    classes = sorted(counts)
    total = sum(counts.values())
    return classes, [counts[c] / total for c in classes]


# ------------------------------------------------------------------- driver


def run(args: argparse.Namespace) -> dict[str, Any] | None:
    from codestream_common import find_raw, load_problems, load_submissions, user_hash
    from repair_verify import GENERATORS

    from backend.app.diagnosis.xgb_classifier import ModelClassifier

    raw = find_raw(args.raw)
    probs = load_problems(raw)
    pool_map = load_pool_map()
    bad = unreliable_problems()
    subs = [s for s in load_submissions(raw)
            if s.problem_id in pool_map and pool_map[s.problem_id][1] == args.pool and s.problem_id not in bad]
    if args.limit:
        subs = subs[: args.limit]
    print(f"pool {args.pool}: {len(subs)} C/C++ submissions, {len({s.problem_id for s in subs})} problems "
          f"(excluded unreliable problems: {sorted(bad) or 'none'})", flush=True)

    exec_path = CACHE_DIR / f"real_eval_exec_{args.pool}.jsonl"
    results = execute_pool(subs, probs, exec_path, args.workers)

    models = {v: ModelClassifier.load(v) for v in SERVING_VARIANTS}
    rows: list[dict[str, Any]] = []
    for s in subs:
        res = results.get(s.submission_id)
        if res is None:
            continue
        norm = feature_row(s, probs[s.problem_id], res)
        all_features = flatten_blocks(norm, schema_feature_names())
        row: dict[str, Any] = {
            "submission_id": s.submission_id, "problem_id": s.problem_id,
            "cluster": pool_map[s.problem_id][0], "user_hash": user_hash(s.user_id),
            "attempt_number": s.attempt_number, "verdict": s.verdict, "branch": res.get("branch"),
            "lang": s.lang, "code": s.code, "result": res, "tests": probs[s.problem_id].tests,
            "features": all_features,
        }
        if res.get("branch") == "failing":
            for name, model in models.items():
                pred = model.predict(all_features)  # whole vector: the applicability rules read more than this variant uses
                row[name] = {"label": pred.top_label, "p": pred.top_probability, "abstained": pred.abstained,
                             "n_missing": pred.n_missing, "n_features": pred.n_features}
        rows.append(row)

    write_feature_dump(rows, CACHE_DIR / f"real_eval_features_{args.pool}.csv")
    if args.features_only:
        return None
    failing = [r for r in rows if r["branch"] == "failing"]
    report: dict[str, Any] = {
        "pool": args.pool, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "purpose": ("DEVELOPMENT run on dev-gold clusters: debugging the evaluation, not a result"
                    if args.pool == "dev_gold" else "held-out evaluation"),
        "n_submissions": len(rows), "n_problems": len({r["problem_id"] for r in rows}),
        "n_users": len({r["user_hash"] for r in rows}),
        "router": dict(Counter(r["branch"] for r in rows)),
        "accepted_routed_to_model": sum(1 for r in rows if r["verdict"] == "Accepted" and r["branch"] == "failing"),
        "accepted_total": sum(1 for r in rows if r["verdict"] == "Accepted"),
        "models": {v: {"sha256_16": m.model_sha256[:16], "threshold": m.threshold} for v, m in models.items()},
        "variants": {},
    }

    rng = random.Random(SEED)
    generators = sorted(GENERATORS)
    prior_classes, prior_p = training_prior(generators)
    cache_dir = str(CACHE_DIR / "repairs")
    for variant in SERVING_VARIANTS:
        report["variants"][variant] = behaviour_and_repairs(
            variant, failing, args, rng, generators, prior_classes, prior_p, cache_dir
        )
    return report


def behaviour_and_repairs(variant, failing, args, rng, generators, prior_classes, prior_p, cache_dir) -> dict[str, Any]:
    preds = [r[variant] for r in failing]
    kept = [p for p in preds if not p["abstained"]]
    out: dict[str, Any] = {
        "n_failing": len(failing),
        "abstain_rate": round(1 - len(kept) / len(preds), 3) if preds else None,
        "other_error_rate": round(sum(1 for p in kept if p["label"] == "CPP_OTHER_ERROR") / len(kept), 3) if kept else None,
        "class_histogram": dict(Counter(p["label"] for p in kept)),
        "mean_missing_features": round(sum(p["n_missing"] for p in preds) / len(preds), 2) if preds else None,
        "mean_top_probability": round(sum(p["p"] for p in preds) / len(preds), 3) if preds else None,
    }
    per_problem: dict[str, Counter] = defaultdict(Counter)
    for r in failing:
        per_problem[r["problem_id"]]["abstained" if r[variant]["abstained"] else r[variant]["label"]] += 1
    out["per_problem"] = {k: dict(v) for k, v in sorted(per_problem.items())}
    pairs = [(a, b) for a, b in consecutive_failed_pairs(failing) if not a[variant]["abstained"] and not b[variant]["abstained"]]
    if pairs:
        agree = sum(a[variant]["label"] == b[variant]["label"] for a, b in pairs) / len(pairs)
        out["stability"] = {"pairs": len(pairs), "same_label": round(agree, 3),
                            "chance": round(expected_chance_agreement([p["label"] for p in kept]), 3)}

    # ---- T2: repair confirmation on the rows the model labelled with a repairable class
    cands = [r for r in failing if not r[variant]["abstained"] and r[variant]["label"] in generators]
    out["t2_evaluated"] = len(cands)
    out["t2_coverage_of_failing"] = round(len(cands) / len(failing), 3) if failing else None
    if args.skip_repairs or not cands:
        return out

    def job(r: dict[str, Any], cls: str) -> tuple:
        return (r["code"], r["lang"], r["tests"], cls, cache_dir, (r["result"].get("tests") or {}).get("results", []))

    rand_cls = [rng.choices(prior_classes, prior_p)[0] for _ in cands]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        model_res = list(ex.map(_repair_job, [job(r, r[variant]["label"]) for r in cands], chunksize=2))
        rand_res = list(ex.map(_repair_job, [job(r, c) for r, c in zip(cands, rand_cls)], chunksize=2))
        rule_classes = list(ex.map(_rule_class, [(r["code"], r["lang"], r["tests"], r["result"]) for r in cands], chunksize=4))
        rule_idx = [i for i, c in enumerate(rule_classes) if c in generators]
        rule_res = dict(zip(rule_idx, ex.map(_repair_job, [job(cands[i], rule_classes[i]) for i in rule_idx], chunksize=2)))
        ceiling = None
        if args.ceiling:
            ceiling = [any(x["verified"] or x["partial"] for x in ex.map(_repair_job, [job(r, c) for c in generators]))
                       for r in cands]

    def by_problem(outcomes: dict[int, bool]) -> dict[str, list[float]]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for i, ok in outcomes.items():
            grouped[cands[i]["problem_id"]].append(1.0 if ok else 0.0)
        return grouped

    out["errors"] = sum(1 for x in model_res + rand_res if "error" in x)
    for key, label in (("verified", "t2_full"), ("partial", "t2_partial")):
        model_by = by_problem({i: x[key] for i, x in enumerate(model_res)})
        rand_by = by_problem({i: x[key] for i, x in enumerate(rand_res)})
        block = {
            "model": _ci(*bootstrap_ci(model_by, rng)),
            "random_prior": _ci(*bootstrap_ci(rand_by, rng)),
            "model_minus_random": _ci(*paired_difference_ci(model_by, rand_by, rng)),
            "model_hits": int(sum(x[key] for x in model_res)), "random_hits": int(sum(x[key] for x in rand_res)),
            "rows": len(cands),
        }
        if rule_res:
            rule_by = by_problem({i: x[key] for i, x in rule_res.items()})
            same = by_problem({i: model_res[i][key] for i in rule_res})
            block["rule"] = _ci(*bootstrap_ci(rule_by, rng))
            block["rule_rows"] = len(rule_res)
            block["model_minus_rule_same_rows"] = _ci(*paired_difference_ci(same, rule_by, rng))
        out[label] = block
    if ceiling is not None:
        out["coverage_ceiling_any_class_repairs_or_partial"] = round(sum(ceiling) / len(ceiling), 3)
    return out


def _ci(point: float, lo: float, hi: float) -> dict[str, float | None]:
    def r(x: float) -> float | None:
        return None if math.isnan(x) else round(x, 3)

    return {"value": r(point), "ci95_low": r(lo), "ci95_high": r(hi)}


def render_markdown(rep: dict[str, Any]) -> str:
    lines = [
        f"# Real-data evaluation: CodeStream pool `{rep['pool']}`", "",
        f"_{rep['purpose']}._ Generated by `scripts/eval_real_data.py` at {rep['at']}. Do not edit by hand.", "",
        f"- Submissions: {rep['n_submissions']} · problems: {rep['n_problems']} · students: {rep['n_users']}",
        f"- Router branches: {rep['router']}",
        f"- Accepted rows that execution routes to the model (should be ~0): "
        f"{rep['accepted_routed_to_model']} of {rep['accepted_total']}",
        "- Limits: T2 measures whether an automatic repair of the predicted class fixes every test. The repair operators "
        "belong to the same family that generated the synthetic training rows, so this supports, but does not replace, "
        "human-labelled gold (G6). It is not accuracy.", "",
    ]
    for variant, v in rep["variants"].items():
        m = rep["models"][variant]
        lines += [f"## Variant `{variant}` (sha256 {m['sha256_16']}, abstain threshold {m['threshold']})", "",
                  f"- Failing submissions scored: {v['n_failing']} · abstain rate: {v['abstain_rate']} · "
                  f"OTHER_ERROR share of confident: {v['other_error_rate']} · mean missing features: {v['mean_missing_features']}",
                  f"- Predicted classes (confident only): {v['class_histogram']}"]
        if "stability" in v:
            s = v["stability"]
            lines.append(f"- Label stability on consecutive failed attempts: {s['same_label']} over {s['pairs']} pairs "
                         f"(chance {s['chance']})")
        lines.append(f"- Mean top probability on real failing rows: {v['mean_top_probability']}")
        for prob_id, hist in v["per_problem"].items():
            lines.append(f"  - {prob_id}: {hist}")
        lines.append(f"- Rows with a repairable predicted class: {v['t2_evaluated']} ({v['t2_coverage_of_failing']} of failing)")
        for key, title in (("t2_full", "every test passes after a repair of the predicted class"),
                           ("t2_partial", "a repair of the predicted class fixes the first failing test, no regressions")):
            if key not in v:
                continue
            t = v[key]

            def f(c):
                return f"{c['value']} [{c['ci95_low']}, {c['ci95_high']}]"

            lines += ["", f"**T2, {title}** ({t['model_hits']} of {t['rows']} model rows; "
                          f"{t['random_hits']} random-class rows)", "",
                      "| arm | rate [95% CI, by problem] |", "|---|---|",
                      f"| model top class | {f(t['model'])} |",
                      f"| prior-matched random class | {f(t['random_prior'])} |",
                      f"| model minus random (same rows) | {f(t['model_minus_random'])} |"]
            if "rule" in t:
                lines += [f"| labeling-function rule ({t['rule_rows']} rows) | {f(t['rule'])} |",
                          f"| model minus rule (same rows) | {f(t['model_minus_rule_same_rows'])} |"]
        if "coverage_ceiling_any_class_repairs_or_partial" in v:
            lines.append(f"- Ceiling, any class fully or partially repairs: {v['coverage_ceiling_any_class_repairs_or_partial']}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool", choices=("dev_gold", "test", "train"), required=True)
    ap.add_argument("--raw", default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None, help="first N submissions only (smoke test)")
    ap.add_argument("--skip-repairs", action="store_true")
    ap.add_argument("--ceiling", action="store_true", help="also try every class (slow)")
    ap.add_argument("--confirm-test-run", action="store_true")
    ap.add_argument("--features-only", action="store_true",
                    help="execute/score and write the feature dump only; leave the reports untouched")
    args = ap.parse_args(argv)
    if args.pool == "train" and not args.features_only:
        print("REFUSED: the train pool is not an evaluation pool; use --features-only to dump its features")
        return 2
    if args.pool == "test" and not args.confirm_test_run:
        print("REFUSED: the test pool is evaluated once; rerun with --confirm-test-run after the model is frozen")
        return 2
    report = run(args)
    if report is None:
        print(f"wrote feature dump for pool {args.pool}")
        return 0
    REPORTS.mkdir(exist_ok=True)
    stem = f"real_eval_{args.pool}"
    (REPORTS / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    (REPORTS / f"{stem}.md").write_text(render_markdown(report) + "\n", encoding="utf-8", newline="\n")
    with (REPORTS / "real_eval_runs.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"pool": args.pool, "at": report["at"], "limit": args.limit,
                             "models": report["models"],
                             "sha": hashlib.sha256(json.dumps(report["variants"], sort_keys=True).encode()).hexdigest()[:12]}) + "\n")
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
