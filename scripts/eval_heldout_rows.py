"""Score what is served on the held-out problems: the classifier alone AND the full runtime.

Two steps, so that each model is scored with the code it ships with (docs/EVAL_PROTOCOL.md):

    python scripts/eval_heldout_rows.py run --confirm-one-shot --tag audited
    TL_EVAL_REPO=../tl-pr17 python scripts/eval_heldout_rows.py run --confirm-one-shot --tag pr17
    python scripts/eval_heldout_rows.py report --runs audited pr17 --served audited

`run` loads the `execution` model, the rows of the held-out `test` split and the backend's
decision code from one repository (this one, or the checkout named by `TL_EVAL_REPO`), and
writes every row's result to `reports/heldout_runs/<tag>.json` in THIS repository. It appends
one line to `reports/holdout_evaluations.jsonl`: every read of the held-out split is logged.

Each row gets two systems:

- **classifier only**: `ModelClassifier.predict` with its threshold and any per-class bars;
- **full runtime**: `runtime_decision` from `backend.app.diagnosis.xgb_classifier`, the same
  function the backend serves (rules before the classifier, then the missing-feature abstain).
  Code from before that function existed (PR #17, 15 Nov) is scored through its own
  `rule_override` (or `repair_override`) and its own `MAX_MISSING_SHARE`; the run header says
  `legacy` and nothing of the decision order is re-implemented here beyond "a rule hit replaces
  the label".

Rule stages that read the run record get it from `cache/counterfactual/evidence_extra.jsonl`
(the second-set repairs, `cf_extra`, used as `cf_narrow`; the same stand-in PR #17's log used).
That cache is not committed and predates repairs added on 15 Nov; the run header says so.

`report` joins runs on the rows they share, checks the recorded labels agree, and writes
`reports/heldout_eval.{md,json}` and `reports/heldout_predictions.json`: overall, per class with
Wilson intervals, per problem, problem-weighted macro-F1, and everything again without
`tl-progpedia-00000039`, which holds 42% of the rows.

Labels are the rows with `label_source == "human"`, which today includes agent-consensus and
blind-review labels (Gate 1 separates them). Every number is agreement with those labels.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
# Where the data, model and backend code come from. Outputs always land in SCRIPT_ROOT.
ROOT = Path(os.environ.get("TL_EVAL_REPO") or SCRIPT_ROOT).resolve()
for p in (ROOT, ROOT / "scripts", SCRIPT_ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from label_provenance import HUMAN_FLAG_LABEL_ORIGINS, derive_provenance  # noqa: E402
from eval_blind_test import ABSTAIN, OTHER, bootstrap_macro_f1, macro_f1, summarize, wilson  # noqa: E402

DS = ROOT / "data" / "misconception_dataset"
OUT_DS = SCRIPT_ROOT / "data" / "misconception_dataset"
RUNS = OUT_DS / "reports" / "heldout_runs"
EXPOSURE_LOG = OUT_DS / "reports" / "holdout_evaluations.jsonl"
P39 = "tl-progpedia-00000039"

# A single problem contributing more than this share of rows is flagged.
_CONCENTRATION_THRESHOLD = 0.20


def problem_weighted_macro_f1(truth: list[str], pred: list[str], problems: list[str]) -> float:
    """Macro-F1 averaged per problem then averaged across problems (equal problem weight)."""
    by: dict[str, tuple[list[str], list[str]]] = {}
    for t, p, g in zip(truth, pred, problems):
        ts, ps = by.setdefault(g, ([], []))
        ts.append(t)
        ps.append(p)
    scores = [macro_f1(ts, ps) for ts, ps in by.values() if ts]
    scores = [s for s in scores if not math.isnan(s)]
    return round(sum(scores) / len(scores), 3) if scores else math.nan


def concentration_warnings(problems: list[str]) -> list[str]:
    """Return warning strings for problems that supply > _CONCENTRATION_THRESHOLD of rows."""
    total = len(problems)
    if total == 0:
        return []
    counts = Counter(problems)
    return [
        f"WARNING: '{p}' supplies {c}/{total} rows ({c/total:.0%}) — per-problem weighting is recommended"
        for p, c in counts.most_common()
        if c / total > _CONCENTRATION_THRESHOLD
    ]


# ------------------------------------------------------------------ run

def load_rows(split: str, ds: Path = DS) -> list[dict]:
    labels = {}
    for line in (ds / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            labels[r["row_id"]] = r
    in_split = {r["row_id"] for r in csv.DictReader((ds / "splits" / "splits.csv").open(newline="", encoding="utf-8"))
                if r["split"] == split}
    lanes = {}
    for path in sorted((ds / "annotations").glob("tier*.jsonl")):
        for line in path.open(encoding="utf-8"):
            if line.strip():
                lanes[json.loads(line)["row_id"]] = path.name.split("_")[0]
    rows = []
    with (ds / "features" / "features.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        names = header[2:]
        for rec in reader:
            if rec[0] not in in_split:
                continue
            meta = labels[rec[0]]
            feats = {n: (None if v in ("", "nan", "NaN") else float(v)) for n, v in zip(names, rec[2:])}
            rows.append({"row_id": rec[0], "truth": meta["label"], "source": meta["dataset_source"],
                         "problem": meta["problem_id"], "lane": lanes.get(rec[0], "?"),
                         "label_source": meta.get("label_source"), "label_status": meta.get("label_status"),
                         "label_origin": derive_provenance(meta)["label_origin"],
                         "features": feats})
    return rows


def load_run_records(path: Path) -> dict[str, dict]:
    """Row id -> a run record holding the cached second-set repairs as `cf_narrow`."""
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if r.get("cf_extra") is not None:
                out[r["row_id"]] = {"cf_narrow": r["cf_extra"]}
    return out


def runtime_function():
    """(description, decide(clf, features, run_record) -> prediction) from the backend under test."""
    import backend.app.diagnosis.xgb_classifier as xc

    if hasattr(xc, "runtime_decision"):
        return "backend.app.diagnosis.xgb_classifier.runtime_decision", xc.runtime_decision
    from backend.app.analysis import model_runner as mr

    override = getattr(xc, "rule_override", None)
    name = "rule_override" if override else "repair_override"

    def legacy(clf, features, run_record):
        pred = clf.predict(features)
        hit = override(features, run_record) if override else xc.repair_override(features)
        if hit:
            pred = dataclasses.replace(pred, top_label=hit, top_probability=1.0, abstained=False)
        if pred.n_features and pred.n_missing / pred.n_features > mr.MAX_MISSING_SHARE and not pred.abstained:
            pred = dataclasses.replace(pred, abstained=True)
        return pred, ("rule (legacy)" if hit else "model")

    return f"legacy: xgb_classifier.{name}, then the classifier, then model_runner.MAX_MISSING_SHARE", legacy


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def cmd_run(a: argparse.Namespace) -> int:
    if not a.confirm_one_shot:
        print("REFUSED: rerun with --confirm-one-shot (each scoring of a held-out split is logged)")
        return 2
    from backend.app.diagnosis.xgb_classifier import ModelClassifier

    models_dir = Path(a.models_dir) if a.models_dir else DS / "models"
    clf = ModelClassifier.load("execution", models_dir)
    how, decide = runtime_function()
    # Same rows as the old `label_source == "human"` filter; agent-consensus rows are scored (G3 unchanged).
    rows = [r for r in load_rows(a.split) if r["label_origin"] in HUMAN_FLAG_LABEL_ORIGINS]
    rr_path = Path(a.run_records) if a.run_records else next(
        (p for p in (DS / "cache" / "counterfactual" / "evidence_extra.jsonl",
                     SCRIPT_ROOT / "data" / "misconception_dataset" / "cache" / "counterfactual" / "evidence_extra.jsonl")
         if p.exists()), Path("missing"))
    records = load_run_records(rr_path)
    out_rows = []
    for r in rows:
        c = clf.predict(r["features"])
        got = decide(clf, r["features"], records.get(r["row_id"]))
        d, source = got if isinstance(got, tuple) else (got, got.decision_source)
        out_rows.append({
            "row_id": r["row_id"], "problem": r["problem"], "source": r["source"], "lane": r["lane"],
            "truth": r["truth"], "label_source": r["label_source"], "label_status": r["label_status"],
            "classifier": {"label": ABSTAIN if c.abstained else c.top_label, "top_label": c.top_label,
                           "p": c.top_probability},
            "runtime": {"label": ABSTAIN if d.abstained else d.top_label, "decision_source": source,
                        "confidence": d.top_probability},
        })
    model_file = models_dir / "xgb_execution_v1.json"
    head = {
        "tag": a.tag, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "split": a.split,
        "repo_commit": _git("rev-parse", "HEAD"), "repo_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "models_dir": str(models_dir.relative_to(ROOT)) if models_dir.is_relative_to(ROOT) else str(models_dir),
        "model_sha256": hashlib.sha256(model_file.read_bytes()).hexdigest(),
        "temperature": clf.temperature, "threshold": clf.threshold,
        "class_thresholds": getattr(clf, "class_thresholds", None) or {},
        "runtime": how,
        "run_records": f"{rr_path.name}: {len(records)} rows with second-set repairs (cf_extra used as cf_narrow)",
        "n_rows": len(out_rows),
    }
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{a.tag}.json").write_text(json.dumps({"run": head, "rows": out_rows}, indent=1) + "\n",
                                        encoding="utf-8", newline="\n")
    with EXPOSURE_LOG.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"split": f"heldout_rows_{a.split}", "at": head["at"], "n": len(out_rows), "tag": a.tag,
                             "models": {"execution": {"sha256_16": head["model_sha256"][:16]}}}) + "\n")
    print(f"{a.tag}: {len(out_rows)} rows, model {head['model_sha256'][:16]}, runtime {how}")
    print(f"wrote {RUNS / (a.tag + '.json')}")
    return 0


# ------------------------------------------------------------------ report

def per_class(truth: list[str], pred: list[str]) -> dict[str, dict]:
    out = {}
    for c in sorted(set(truth) | {p for p in pred if p != ABSTAIN}):
        tp = sum(1 for t, p in zip(truth, pred) if t == c == p)
        n_t, n_p = truth.count(c), pred.count(c)
        prec, rec = (tp / n_p if n_p else None), (tp / n_t if n_t else None)
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if n_t else None)

        def ci(k, n):
            lo, hi = wilson(k, n)
            return None if n == 0 else [round(lo, 3), round(hi, 3)]
        out[c] = {"support": n_t, "predicted": n_p, "correct": tp,
                  "precision": None if prec is None else round(prec, 3), "precision_ci95": ci(tp, n_p),
                  "recall": None if rec is None else round(rec, 3), "recall_ci95": ci(tp, n_t),
                  "f1": None if f1 is None else round(f1, 3)}
    return out


def per_problem(rows: list[dict], systems: dict[str, list[str]]) -> dict[str, dict]:
    by: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by[r["problem"]].append(i)
    out = {}
    for prob in sorted(by, key=lambda p: (-len(by[p]), p)):
        idx = by[prob]
        out[prob] = {"rows": len(idx), "named_truth": sum(rows[i]["truth"] != OTHER for i in idx), "systems": {
            name: {"flagged": sum(pred[i] not in (OTHER, ABSTAIN) for i in idx),
                   "correct_named": sum(pred[i] == rows[i]["truth"] != OTHER for i in idx)}
            for name, pred in systems.items()}}
    return out


def score_scope(rows: list[dict], systems: dict[str, list[str]]) -> dict:
    truth = [r["truth"] for r in rows]
    groups = [r["problem"] for r in rows]
    res = {}
    for name, pred in systems.items():
        s = summarize(truth, pred)
        s["accuracy"] = round(sum(t == p for t, p in zip(truth, pred)) / len(truth), 3)
        s["macro_f1_ci95_by_problem"] = bootstrap_macro_f1(truth, pred, groups)
        s["macro_f1_problem_weighted"] = problem_weighted_macro_f1(truth, pred, groups)
        s["per_class"] = per_class(truth, pred)
        res[name] = s
    return {"n": len(rows), "problems": len(set(groups)), "truth_counts": dict(Counter(truth)),
            "concentration_warnings": concentration_warnings(groups), "systems": res,
            "per_problem": per_problem(rows, systems)}


def join_runs(runs: list[dict]) -> tuple[list[dict], dict[str, list[str]], dict[str, list[dict]]]:
    """Rows every run scored, in a stable order, and the systems' predictions on them."""
    by_run = [{r["row_id"]: r for r in run["rows"]} for run in runs]
    shared = sorted(set.intersection(*(set(b) for b in by_run)))
    for rid in shared:
        truths = {b[rid]["truth"] for b in by_run}
        if len(truths) != 1:
            raise SystemExit(f"runs disagree on the recorded label of {rid}: {sorted(truths)}")
    rows = [by_run[0][rid] for rid in shared]
    systems: dict[str, list[str]] = {"baseline: always OTHER_ERROR": [OTHER] * len(rows)}
    detail: dict[str, list[dict]] = {}
    for run, b in zip(runs, by_run):
        tag = run["run"]["tag"]
        systems[f"{tag}: classifier only"] = [b[rid]["classifier"]["label"] for rid in shared]
        systems[f"{tag}: full runtime"] = [b[rid]["runtime"]["label"] for rid in shared]
        detail[tag] = [b[rid] for rid in shared]
    return rows, systems, detail


def _rate(x: dict) -> str:
    return f"{x['value']} [{x['ci95'][0]}, {x['ci95'][1]}] ({x['k']}/{x['n']})"


def render(rep: dict) -> str:
    L = ["# Held-out problems: classifier only and full runtime", "",
         f"Generated by `scripts/eval_heldout_rows.py report` at {rep['at']}. Do not edit by hand. "
         "Protocol: `docs/EVAL_PROTOCOL.md`.", "",
         f"- **Population:** the development set (`test` split), exposed: scored many times before this report. "
         f"{rep['n_rows']} rows over {rep['problems']} problems, the rows every run below shares "
         f"({', '.join(f'{t}: {n}' for t, n in rep['rows_per_run'].items())}).",
         "- **Labels:** every number is agreement with the recorded labels, not independently established truth. "
         "Label origin of the scored rows (`label_source` / `label_status`): "
         + ", ".join(f"{k} {v}" for k, v in rep["label_provenance"].items()) + ".",
         f"- **Served system:** {rep['served_system']}.", "", "## Runs", "",
         "| Run | Model sha256 (16) | Threshold | Per-class bars | Commit | Decision code | Run-record evidence | Scored at |",
         "|---|---|---|---|---|---|---|---|"]
    for t, h in rep["runs"].items():
        bars = ", ".join(f"{k.removeprefix('CPP_')} {v}" for k, v in h["class_thresholds"].items()) or "none"
        L.append(f"| {t} | `{h['model_sha256'][:16]}` | {h['threshold']} (T {h['temperature']}) | {bars} | "
                 f"`{h['repo_commit'][:7]}`{' (dirty)' if h['repo_dirty'] else ''} | {h['runtime']} | {h['run_records']} | {h['at']} |")
    L.append("")
    for scope, body in rep["scopes"].items():
        L += [f"## {scope} ({body['n']} rows, {body['problems']} problems)", "",
              f"Recorded labels: {dict(sorted(body['truth_counts'].items(), key=lambda kv: -kv[1]))}", ""]
        L += [f"> {w}" for w in body["concentration_warnings"]] + ([""] if body["concentration_warnings"] else [])
        L += ["| System | Macro-F1, problem-weighted | Macro-F1 [95% CI by problem] | Precision when it names a class | "
              "Named-class recall | False alarm on OTHER | Abstain | Accuracy |", "|---|---|---|---|---|---|---|---|"]
        for name, s in body["systems"].items():
            ci = s["macro_f1_ci95_by_problem"]
            L.append(f"| {name} | **{s['macro_f1_problem_weighted']}** | {s['macro_f1']} [{ci[0]}, {ci[1]}] | "
                     f"{_rate(s['precision_when_flagged'])} | {_rate(s['misconception_recall'])} | "
                     f"{_rate(s['false_alarm_rate'])} | {_rate(s['abstain_rate'])} | {s['accuracy']} |")
        L.append("")
        for name, s in body["systems"].items():
            if name.startswith("baseline"):
                continue
            L += [f"Per class, {name}:", "",
                  "| Class | Support | Predicted | Correct | Precision [95% CI] | Recall [95% CI] | F1 |",
                  "|---|---:|---:|---:|---|---|---:|"]
            for c, v in s["per_class"].items():
                pc = f"{v['precision']} {v['precision_ci95']}" if v["precision"] is not None else "–"
                rc = f"{v['recall']} {v['recall_ci95']}" if v["recall"] is not None else "–"
                L.append(f"| {c.removeprefix('CPP_')} | {v['support']} | {v['predicted']} | {v['correct']} | {pc} | {rc} | "
                         f"{'–' if v['f1'] is None else v['f1']} |")
            L.append("")
        names = [n for n in body["systems"] if not n.startswith("baseline")]
        L += ["Per problem: flagged / correct named predictions.", "",
              "| Problem | Rows | Named truth | " + " | ".join(names) + " |", "|---|---:|---:|" + "---:|" * len(names)]
        for prob, v in body["per_problem"].items():
            L.append(f"| {prob} | {v['rows']} | {v['named_truth']} | " + " | ".join(
                f"{v['systems'][n]['flagged']} / {v['systems'][n]['correct_named']}" for n in names) + " |")
        L.append("")
    L += ["## Full runtime: which stage decided", "",
          "| Run | " + " | ".join(rep["decision_sources_order"]) + " |", "|---|" + "---:|" * len(rep["decision_sources_order"])]
    for t, counts in rep["decision_sources"].items():
        L.append(f"| {t} | " + " | ".join(str(counts.get(k, 0)) for k in rep["decision_sources_order"]) + " |")
    L += ["", "## Limitations", ""] + [f"- {x}" for x in rep["limitations"]]
    return "\n".join(L) + "\n"


def cmd_report(a: argparse.Namespace) -> int:
    runs = [json.loads((RUNS / f"{t}.json").read_text(encoding="utf-8")) for t in a.runs]
    rows, systems, detail = join_runs(runs)
    if a.served not in a.runs:
        raise SystemExit(f"--served {a.served!r} is not one of the runs")
    keep_without = [i for i, r in enumerate(rows) if r["problem"] != P39]
    scopes = {"All rows": score_scope(rows, systems),
              f"Without {P39}": score_scope([rows[i] for i in keep_without],
                                            {k: [v[i] for i in keep_without] for k, v in systems.items()})}
    all_rows = scopes["All rows"]
    only_other = sum(1 for v in all_rows["per_problem"].values() if v["named_truth"] == 0)
    floor = all_rows["systems"]["baseline: always OTHER_ERROR"]["macro_f1_problem_weighted"]
    sources = {t: Counter(r["runtime"]["decision_source"] for r in d) for t, d in detail.items()}
    order = sorted({k for c in sources.values() for k in c}, key=lambda k: (k != "model", k))
    rep = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "population": "development set (test split), exposed",
        "n_rows": len(rows), "problems": len({r["problem"] for r in rows}),
        "rows_per_run": {run["run"]["tag"]: run["run"]["n_rows"] for run in runs},
        "label_provenance": dict(Counter(f"{r['label_source']}/{r['label_status'] or 'none'}" for r in rows).most_common()),
        "served_system": f"{a.served}: full runtime",
        "runs": {run["run"]["tag"]: run["run"] for run in runs},
        "models": {run["run"]["tag"]: {"sha256_16": run["run"]["model_sha256"][:16]} for run in runs},
        "scopes": scopes,
        "decision_sources": {t: dict(c) for t, c in sources.items()}, "decision_sources_order": order,
        "limitations": [
            f"Problem-weighted macro-F1 has a floor here: {only_other} of {all_rows['problems']} problems have no "
            "named-class row, and on such a problem a system that never names a class scores 1.0. That is why "
            f"always-OTHER reaches {floor}. Compare systems with each other and with that floor, not with zero.",
            "The development set has been scored many times and choices were made with it "
            "(EVAL_PROTOCOL section 8); these numbers are development evidence, not an independent test.",
            "Labels are mostly agent consensus and blind review, treated as human; agreement with them is "
            "not accuracy against independent human truth.",
            "Several classes have under 10 held-out rows and two have none; their per-class figures are not "
            "estimates of anything (see the support column).",
            "Rule stages that read the run record use the 9 Nov second-set cache as their evidence; repairs "
            "added after it (for_add_missing_step, range_test_swap_and_or, for_run_downward) never fire here, "
            "so a run whose code has them is slightly under-counted.",
            "A legacy run reports 1.0 for a rule decision (the code before decision_source); its labels, "
            "not its confidences, are scored.",
        ],
    }
    rep_dir = OUT_DS / "reports"
    (rep_dir / "heldout_eval.json").write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8", newline="\n")
    names = [n for n in systems if not n.startswith("baseline")]
    (rep_dir / "heldout_predictions.json").write_text(json.dumps({
        "split": "test", "served_system": rep["served_system"],
        "columns": ["row_id", "source", "truth", "problem"] + names,
        "rows": [[r["row_id"], r["source"], r["truth"], r["problem"]] + [systems[n][i] for n in names]
                 for i, r in enumerate(rows)],
        "detail": {t: [{"row_id": d["row_id"], "decision_source": d["runtime"]["decision_source"],
                        "confidence": d["runtime"]["confidence"], "classifier_p": d["classifier"]["p"]} for d in ds]
                   for t, ds in detail.items()},
    }) + "\n", encoding="utf-8", newline="\n")
    text = render(rep)
    (rep_dir / "heldout_eval.md").write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="score one model with its own repository's code")
    r.add_argument("--confirm-one-shot", action="store_true")
    r.add_argument("--tag", required=True, help="name of this run, e.g. audited or pr17")
    r.add_argument("--split", default="test")
    r.add_argument("--models-dir", help="default: <repo>/data/misconception_dataset/models")
    r.add_argument("--run-records", help="default: the repo's cache/counterfactual/evidence_extra.jsonl")
    p = sub.add_parser("report", help="join runs on their shared rows and write the committed report")
    p.add_argument("--runs", nargs="+", required=True)
    p.add_argument("--served", required=True, help="the run whose full runtime is what main serves")
    a = ap.parse_args(argv)
    return cmd_run(a) if a.cmd == "run" else cmd_report(a)


if __name__ == "__main__":
    raise SystemExit(main())
