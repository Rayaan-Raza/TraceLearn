"""One-shot evaluation of the served model on the frozen blind test labels.

    wsl python3 scripts/eval_blind_test.py --confirm-one-shot

The test items are 143 randomly sampled failing submissions of the held-out CodeStream
test clusters, labelled blind (code, failing test and observed output only; no rule or
model output) before the model scored them. `review/blind_labels/test.json` is hashed
into the report so a later edit is visible. The labels are a model-assisted reviewer's,
treated as human on the owner's instruction (2026-11-07); every number below is
agreement with that reviewer, not with an independent person.

Reported for each served variant and for two baselines (always OTHER_ERROR, and the
labeling-function rules):

- false-alarm rate: of the items labelled OTHER_ERROR, how many get a misconception
  name (the plan's open-set target is <= 30%);
- precision when flagged: of the items given a misconception name, how many have that
  label;
- recall: of the items labelled with a misconception, how many get that label;
- abstain rate and macro-F1 (abstention counts as a miss);
- 95% intervals: Wilson for rates, bootstrap over PROBLEMS for macro-F1.

The item set is small (about 20% misconceptions, concentrated in a few problems), so
per-class numbers are shown with their counts and should not be over-read.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DS = ROOT / "data" / "misconception_dataset"
OTHER, ABSTAIN = "CPP_OTHER_ERROR", "ABSTAIN"
SERVED = ("best", "common")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return math.nan, math.nan
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(k: int, n: int) -> dict[str, Any]:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "value": round(k / n, 3) if n else None,
            "ci95": [None if math.isnan(lo) else round(lo, 3), None if math.isnan(hi) else round(hi, 3)]}


def macro_f1(truth: Sequence[str], pred: Sequence[str]) -> float:
    """Macro-F1 over the labels present in `truth`; ABSTAIN is never a correct answer."""
    labels = sorted(set(truth))
    scores = []
    for c in labels:
        tp = sum(1 for t, p in zip(truth, pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(truth, pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(truth, pred) if t == c and p != c)
        scores.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    return sum(scores) / len(scores) if scores else math.nan


def summarize(truth: Sequence[str], pred: Sequence[str]) -> dict[str, Any]:
    is_misc_truth = [t != OTHER for t in truth]
    flagged = [p not in (OTHER, ABSTAIN) for p in pred]
    n_other = sum(1 for m in is_misc_truth if not m)
    n_misc = sum(is_misc_truth)
    per_class = {}
    for c in sorted(set(truth) | {p for p in pred if p != ABSTAIN}):
        tp = sum(1 for t, p in zip(truth, pred) if t == c and p == c)
        n_t = sum(1 for t in truth if t == c)
        n_p = sum(1 for p in pred if p == c)
        per_class[c] = {"support": n_t, "predicted": n_p, "correct": tp,
                        "precision": round(tp / n_p, 3) if n_p else None,
                        "recall": round(tp / n_t, 3) if n_t else None}
    return {
        "n": len(truth), "n_other": n_other, "n_misconception": n_misc,
        "false_alarm_rate": rate(sum(1 for m, f in zip(is_misc_truth, flagged) if not m and f), n_other),
        "precision_when_flagged": rate(sum(1 for t, p, f in zip(truth, pred, flagged) if f and t == p), sum(flagged)),
        "misconception_recall": rate(sum(1 for t, p in zip(truth, pred) if t != OTHER and t == p), n_misc),
        "misconception_detected_any_class": rate(sum(1 for m, f in zip(is_misc_truth, flagged) if m and f), n_misc),
        "abstain_rate": rate(sum(1 for p in pred if p == ABSTAIN), len(pred)),
        "macro_f1": round(macro_f1(truth, pred), 3),
        "per_class": per_class,
    }


def bootstrap_macro_f1(truth: Sequence[str], pred: Sequence[str], groups: Sequence[str],
                       seed: int = 11, n: int = 1000) -> list[float | None]:
    by: dict[str, list[int]] = defaultdict(list)
    for i, g in enumerate(groups):
        by[g].append(i)
    keys = sorted(by)
    rng = random.Random(seed)
    draws = []
    for _ in range(n):
        idx = [i for g in (rng.choice(keys) for _ in keys) for i in by[g]]
        v = macro_f1([truth[i] for i in idx], [pred[i] for i in idx])
        if not math.isnan(v):
            draws.append(v)
    draws.sort()
    if not draws:
        return [None, None]
    return [round(draws[int(0.025 * (len(draws) - 1))], 3), round(draws[int(0.975 * (len(draws) - 1))], 3)]


def model_prediction(label: str, abstained: bool) -> str:
    return ABSTAIN if abstained else label


def run(name: str = "test") -> dict[str, Any]:
    from codestream_common import find_raw, load_problems, load_submissions
    from eval_real_data import _rule_class, feature_row, flatten_blocks
    from repair_verify import GENERATORS

    from backend.app.diagnosis.xgb_classifier import ModelClassifier
    from tracelearn_features.schema import feature_names

    labels_path = DS / "review" / "blind_labels" / f"{name}.json"
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    manifest = json.loads((DS / "cache" / "label_batches" / name / "manifest.json").read_text(encoding="utf-8"))
    executed = {}
    for line in (DS / "cache" / f"label_exec_{name}.jsonl").open(encoding="utf-8"):
        rec = json.loads(line)
        executed[rec["submission_id"]] = rec["result"]

    raw = find_raw("/mnt/g/TraceLearn/Datasets_RAW")
    probs = load_problems(raw)
    subs = {s.submission_id: s for s in load_submissions(raw)}

    items = []
    for m in manifest:
        lab = labels.get(m["item_id"])
        if lab is None or lab["label"] == "UNCERTAIN" or m["submission_id"] not in executed:
            continue
        s = subs[m["submission_id"]]
        feats = flatten_blocks(feature_row(s, probs[s.problem_id], executed[m["submission_id"]]), feature_names())
        rule = _rule_class((s.code, s.lang, probs[s.problem_id].tests, executed[m["submission_id"]]))
        items.append({"item": m["item_id"], "problem": s.problem_id, "truth": lab["label"], "features": feats,
                      "rule": rule if rule in GENERATORS else OTHER})

    truth = [i["truth"] for i in items]
    groups = [i["problem"] for i in items]
    report: dict[str, Any] = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "labels_sha256": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
        "n_items": len(items), "uncertain_dropped": sum(1 for v in labels.values() if v["label"] == "UNCERTAIN"),
        "truth_counts": dict(Counter(truth)), "problems": len(set(groups)),
        "provenance": ("blind labels by a model-assisted reviewer, treated as human on the owner's instruction "
                       "(2026-11-07); agreement with that reviewer, not with an independent person"),
        "systems": {},
    }
    systems: dict[str, list[str]] = {
        "baseline: always OTHER_ERROR": [OTHER] * len(items),
        "baseline: labeling-function rules": [i["rule"] for i in items],
    }
    meta = {}
    for variant in SERVED:
        model = ModelClassifier.load(variant)
        preds = [model.predict(i["features"]) for i in items]
        systems[f"model: {variant}"] = [model_prediction(p.top_label, p.abstained) for p in preds]
        meta[variant] = {"sha256_16": model.model_sha256[:16], "temperature": model.temperature,
                         "threshold": model.threshold}
    report["models"] = meta
    for name, pred in systems.items():
        s = summarize(truth, pred)
        s["macro_f1_ci95_by_problem"] = bootstrap_macro_f1(truth, pred, groups)
        report["systems"][name] = s
    return report


def render(rep: dict[str, Any]) -> str:
    def r(x):
        return f"{x['value']} [{x['ci95'][0]}, {x['ci95'][1]}] ({x['k']}/{x['n']})"

    lines = [
        "# Frozen blind test: served models and baselines", "",
        f"Generated by `scripts/eval_blind_test.py` at {rep['at']}. Do not edit by hand.", "",
        f"- Items: {rep['n_items']} from {rep['problems']} problems · truth: {rep['truth_counts']} · "
        f"UNCERTAIN dropped: {rep['uncertain_dropped']}",
        f"- Labels file sha256: `{rep['labels_sha256']}`",
        f"- Provenance: {rep['provenance']}",
        f"- Models: {rep['models']}", "",
        "| System | False alarm on OTHER (target <= 0.30) | Precision when flagged | Misconception recall | Abstain | Macro-F1 [95% CI by problem] |",
        "|---|---|---|---|---|---|",
    ]
    for name, s in rep["systems"].items():
        lines.append(f"| {name} | {r(s['false_alarm_rate'])} | {r(s['precision_when_flagged'])} | "
                     f"{r(s['misconception_recall'])} | {r(s['abstain_rate'])} | {s['macro_f1']} {s['macro_f1_ci95_by_problem']} |")
    lines += ["", "## Per class", ""]
    for name, s in rep["systems"].items():
        lines += [f"**{name}**", "", "| Class | Support | Predicted | Correct | Precision | Recall |", "|---|---:|---:|---:|---:|---:|"]
        for c, v in s["per_class"].items():
            lines.append(f"| {c} | {v['support']} | {v['predicted']} | {v['correct']} | {v['precision']} | {v['recall']} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirm-one-shot", action="store_true")
    ap.add_argument("--set", default="test", choices=["test", "final"],
                    help="test = development set (already used to design features and gates); final = untouched")
    args = ap.parse_args(argv)
    if not args.confirm_one_shot:
        print("REFUSED: the blind test is scored once per frozen model; rerun with --confirm-one-shot")
        return 2
    rep = run(args.set)
    rep["set"] = args.set
    (DS / "reports" / (f"blind_{args.set}_eval.json")).write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8", newline="\n")
    (DS / "reports" / (f"blind_{args.set}_eval.md")).write_text(render(rep), encoding="utf-8", newline="\n")
    with (DS / "reports" / "holdout_evaluations.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"split": f"blind_{args.set}", "at": rep["at"], "labels_sha256": rep["labels_sha256"][:16],
                             "models": rep["models"]}) + "\n")
    print(render(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
