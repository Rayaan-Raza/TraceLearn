"""A balanced benchmark on the product's 40 bank problems: build it, run it, score the system.

    wsl python3 scripts/eval_bank_benchmark.py build   [--per-class 40] [--per-problem 3]
    wsl python3 scripts/eval_bank_benchmark.py records [--workers 2]     # slow; resumable
    wsl python3 scripts/eval_bank_benchmark.py score   [--models-dir DIR] [--hold-out-styles]

Why: the held-out real problems have 0-4 rows for several classes, so they cannot say how the
system does on each misconception. The bank is what students attempt, so this measures every
class there.

build    One single-edit bug per class (`build_bank_synthetic.OPERATORS`) in the bank solutions the
         TRAINING rows were not built from differently: styles A and B (`student_specs_a/b.py`) and
         each problem's reference solution. Kept only if the solution passes every bank test, the
         buggy program fails one, and its code is not a dataset row. `benchmark.jsonl`.
records  Each program through the live path (`build_run_record` + `code_features`): the features
         and the narrow-repair evidence a real submission gets. `records.jsonl`.
score    Repair-first rule, narrow repairs, then the model with its bars. Per class precision,
         recall and F1. `--hold-out-styles` also retrains the execution model twice, each time
         without the bank training rows of one solution style, and scores that style's programs:
         the number to quote, because the served model has seen styles A and B with other bugs.

Files live in `cache/bank_benchmark/` (not committed: regenerable). Read the scores as an upper
estimate: every bug is one clean edit to a correct solution, which is tidier than real attempts.
Give WSL a memory limit for `records`; a runaway student loop can exhaust it otherwise.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DS = ROOT / "data" / "misconception_dataset"
HOME = DS / "cache" / "bank_benchmark"
BENCH, RECORDS = HOME / "benchmark.jsonl", HOME / "records.jsonl"
BANK = ROOT / "data" / "cpp_diagnostics" / "problems.json"
OTHER = "CPP_OTHER_ERROR"
SEED = 20261114
MAX_MISSING_SHARE = 0.25


def _bank() -> list[dict]:
    data = json.loads(BANK.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data["problems"]


# ------------------------------------------------------------------ build

def _run(args):
    from build_student_synthetic import run_tests
    key, code, tests = args
    try:
        return key, run_tests(code, tests)
    except Exception as exc:  # noqa: BLE001
        return key, {"compiled": False, "error": str(exc)}


def build(per_class: int, per_problem: int, workers: int) -> int:
    import build_bank_synthetic as G
    import student_specs_a
    import student_specs_b

    specs = {**student_specs_a.SPECS, **student_specs_b.SPECS}
    tests, bases = {}, {}
    for p in _bank():
        tests[p["id"]] = [{"stdin": t["stdin"], "expected_output": t["expected_output"]} for t in p["test_cases"]]
        bases[(p["id"], "R")] = p["reference_solution_source"]
        for style in ("A", "B"):
            if style in specs.get(p["id"], {}):
                bases[(p["id"], style)] = specs[p["id"]][style]
    with ProcessPoolExecutor(workers) as ex:
        good = {k for k, r in ex.map(_run, [(k, c, tests[k[0]]) for k, c in bases.items()])
                if r.get("compiled") and r.get("passed") == r.get("total")}
    seen = G.known_code()
    cands = []
    for pid, style in sorted(good):
        for label, op in G.OPERATORS.items():
            try:
                muts = op(bases[(pid, style)])
            except Exception:  # noqa: BLE001
                muts = []
            for i, (code, before, after) in enumerate(muts[:G.PER_OPERATOR]):
                h = G.norm(code)
                if h not in seen and code != bases[(pid, style)] and G.label_possible(label, bases[(pid, style)]):
                    seen.add(h)
                    cands.append(((pid, style, label, i), code, before, after))
    with ProcessPoolExecutor(workers) as ex:
        res = dict(ex.map(_run, [(c[0], c[1], tests[c[0][0]]) for c in cands]))
    ok = [c for c in cands if res[c[0]].get("compiled") and res[c[0]].get("passed") != res[c[0]].get("total")
          and G.failure_fits(c[0][2], res[c[0]].get("statuses") or [])]
    random.Random(SEED).shuffle(ok)
    kept, n_class, n_cp = [], Counter(), Counter()
    for styles in (("A", "B"), ("R",)):   # student styles first, reference solutions fill the gaps
        for (pid, style, label, i), code, before, after in ok:
            if style in styles and n_class[label] < per_class and n_cp[(label, pid)] < per_problem:
                n_class[label] += 1
                n_cp[(label, pid)] += 1
                kept.append({"id": f"bk-{pid.lower()}-{style.lower()}-{label[4:].lower()}-{i}", "problem": pid, "base": style,
                             "label": label, "code": code, "before": before[:200], "after": after[:200]})
    HOME.mkdir(parents=True, exist_ok=True)
    BENCH.write_text("".join(json.dumps(k) + "\n" for k in kept), encoding="utf-8", newline="\n")
    print(f"solutions {len(bases)} (passing {len(good)}), candidates {len(cands)}, verified {len(ok)}, kept {len(kept)}")
    print({k[4:]: v for k, v in sorted(n_class.items())})
    return 0


# ---------------------------------------------------------------- records

def _record(args):
    os.environ.setdefault("SANDBOX_MODE", "none")
    from backend.app.analysis.model_runner import code_features, compiler_warnings
    from backend.app.analysis.run_record import build_run_record

    g, tests = args
    rr = build_run_record(g["code"], tests)
    slim = None
    if rr:
        cf = rr.get("cf") or {}
        slim = {"seconds": rr.get("seconds"), "tests": {k: (rr.get("tests") or {}).get(k) for k in ("passed", "total")},
                "cf_narrow": rr.get("cf_narrow"), "budget_hit": cf.get("budget_hit")}
    return {"id": g["id"], "problem": g["problem"], "base": g["base"], "label": g["label"],
            "features": code_features(g["code"], "cpp", compiler_warnings(g["code"]), rr), "record": slim}


def records(workers: int) -> int:
    tests = {p["id"]: [{"input": t["stdin"], "output": t["expected_output"]} for t in p["test_cases"]] for p in _bank()}
    done = {json.loads(line)["id"] for line in RECORDS.open(encoding="utf-8")} if RECORDS.exists() else set()
    todo = [g for g in (json.loads(line) for line in BENCH.open(encoding="utf-8")) if g["id"] not in done]
    print(f"to run {len(todo)}, done {len(done)}", flush=True)
    with ProcessPoolExecutor(workers) as ex, RECORDS.open("a", encoding="utf-8", newline="\n") as fh:
        for n, fut in enumerate(as_completed([ex.submit(_record, (g, tests[g["problem"]])) for g in todo]), 1):
            fh.write(json.dumps(fut.result()) + "\n")
            fh.flush()
            if n % 20 == 0 or n == len(todo):
                print(f"{n}/{len(todo)}", flush=True)
    return 0


# ------------------------------------------------------------------ score

def _table(pairs: list[tuple[str | None, str]], title: str) -> list[str]:
    from tune_class_thresholds import f1_of, macro_f1
    named = [(a, b) for a, b in pairs if a not in (None, OTHER)]
    other = sum(b == OTHER for _, b in pairs)
    right = sum(a == b for a, b in named)
    lines = [f"### {title}", "",
             f"{len(pairs)} programs. Accuracy {sum(a == b for a, b in pairs) / len(pairs):.3f}, macro-F1 {macro_f1(pairs):.3f}, "
             f"precision when it names a class {right}/{len(named)} = {right / max(len(named), 1):.3f}, "
             f"recall {right / max(sum(b != OTHER for _, b in pairs), 1):.3f}, "
             f"false alarms on OTHER_ERROR {sum(b == OTHER for _, b in named)}/{other}, "
             f"abstained {sum(a is None for a, _ in pairs) / len(pairs):.3f}.", "",
             "| Class | Programs | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|"]
    for c in sorted({b for _, b in pairs}):
        pr, rc, f1, n = f1_of(pairs, c)
        lines.append(f"| {c[4:]} | {n} | {pr:.2f} | {rc:.2f} | {f1:.2f} |")
    return lines + [""]


def _system(model, probs, row) -> str | None:
    import numpy as np

    from backend.app.diagnosis.applicability import move_ruled_out_mass, ruled_out
    from backend.app.diagnosis.xgb_classifier import decide, rule_override

    override = rule_override(row["features"], row["record"])
    if override:
        return override
    feats = row["features"]
    if sum(feats.get(f) is None for f in model.features) / len(model.features) > MAX_MISSING_SHARE:
        return None
    p = move_ruled_out_mass(np.asarray(probs, dtype=float), model.classes, ruled_out(feats))
    idx, abstained = decide(p, model.classes, model.threshold, model.class_thresholds)
    return None if abstained else model.classes[idx]


def score(models_dir: Path, hold_out_styles: bool, report: Path | None) -> int:
    import numpy as np

    from backend.app.diagnosis.xgb_classifier import ModelClassifier, rescale

    rows = [json.loads(line) for line in RECORDS.open(encoding="utf-8")]
    model = ModelClassifier.load("execution", models_dir)
    X = np.array([[r["features"].get(f) if r["features"].get(f) is not None else math.nan for f in model.features] for r in rows], dtype=float)
    served = rescale(model._raw(X.astype(np.float32)), model.temperature)
    try:
        shown = Path(models_dir).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        shown = Path(models_dir).name
    lines = ["# Bank benchmark", "", "Generated by `scripts/eval_bank_benchmark.py score`. Do not edit by hand.", "",
             f"Model `{shown}` (execution, sha256 {model.model_sha256[:12]}, threshold {model.threshold}, "
             f"bars {model.class_thresholds}).", "",
             "Every bug is one clean edit to a correct bank solution, so these are upper estimates.", ""]
    lines += _table([(_system(model, served[i], r), r["label"]) for i, r in enumerate(rows)], "Served system, all programs")
    ref = [i for i, r in enumerate(rows) if r["base"] == "R"]
    if ref:
        lines += _table([(_system(model, served[i], rows[i]), rows[i]["label"]) for i in ref],
                        "Served system, programs built on reference solutions (not a training style)")
    if hold_out_styles:
        import pandas as pd
        import train_xgb_misconception as T

        profile = (json.loads((models_dir / "metrics_v1.json").read_text(encoding="utf-8")).get("profile") or {}).get("name", "plain")
        T.set_profile(profile)
        meta = {}
        for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                meta[r["row_id"]] = r
        with (DS / "splits" / "splits.csv").open(newline="", encoding="utf-8") as fh:
            split = {r["row_id"]: r["split"] for r in csv.DictReader(fh)}
        train = []
        with (DS / "features" / "features.csv").open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            col = {f: i for i, f in enumerate(header)}
            for rec in reader:
                rid, m = rec[0], meta[rec[0]]
                if split[rid] not in ("train", "dev_gold") or not T.plain_row_selected(rid, m):
                    continue
                train.append((rid, rec[1], [float(rec[col[f]]) if rec[col[f]] not in ("", "nan", "NaN") else math.nan
                                            for f in model.features]))
        pairs = []
        for style in ("A", "B"):
            keep = [t for t in train if not (t[0].startswith("stu-cp") and (meta[t[0]].get("seed_ref") or "").endswith(":" + style))]
            test = [i for i, r in enumerate(rows) if r["base"] == style]
            frame = pd.DataFrame({"label": [meta[t[0]]["label"] for t in keep],
                                  "label_confidence": [float(meta[t[0]].get("label_confidence") or 0.6) for t in keep],
                                  "dataset_source": [meta[t[0]]["dataset_source"] for t in keep]})
            w, _ = T.compute_weights(frame, 1.0)
            probs = rescale(T._fit_predict(np.array([t[2] for t in keep]), np.array([model.classes.index(t[1]) for t in keep]),
                                           w, X[test], 7, len(model.classes)), model.temperature)
            pairs += [(_system(model, probs[j], rows[i]), rows[i]["label"]) for j, i in enumerate(test)]
        lines += _table(pairs, "Solution style held out of training (the number to quote)")
    text = "\n".join(lines)
    print(text)
    if report:
        report.write_text(text + "\n", encoding="utf-8", newline="\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--per-class", type=int, default=40)
    b.add_argument("--per-problem", type=int, default=3)
    b.add_argument("--workers", type=int, default=4)
    r = sub.add_parser("records")
    r.add_argument("--workers", type=int, default=2)
    s = sub.add_parser("score")
    s.add_argument("--models-dir", type=Path, default=DS / "models")
    s.add_argument("--hold-out-styles", action="store_true")
    s.add_argument("--report", type=Path, default=None, help="also write the tables to this markdown file")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        return build(a.per_class, a.per_problem, a.workers)
    if a.cmd == "records":
        return records(a.workers)
    return score(a.models_dir, a.hold_out_styles, a.report)


if __name__ == "__main__":
    raise SystemExit(main())
