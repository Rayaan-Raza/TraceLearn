"""Score the served models on every row of the held-out `test` split (whole unseen problems).

    wsl python3 scripts/eval_heldout_rows.py --confirm-one-shot

`test` holds the CodeStream blind-labelled problems and the PROGPedia problems listed in
`splits/progpedia_holdout.csv`; no row of those problems (and no synthetic mutant seeded from
them) reaches training. Labels are the agent-consensus / blind labels the owner approved
(`label_source = human`), so every number is agreement with those annotators.

Features come from `features/features.csv`; the model, its calibration and the applicability
rules are exactly what the backend serves. Reported per source and overall, with the
always-OTHER baseline: false alarm on OTHER rows, precision when flagged, misconception recall,
abstain rate, accuracy, macro-F1 (abstention counts as a miss), Wilson 95% intervals, and a
problem-level bootstrap interval for macro-F1. Writes reports/heldout_eval.{json,md} and
reports/heldout_predictions.json (for the confusion matrix) and appends to
reports/holdout_evaluations.jsonl.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from eval_blind_test import ABSTAIN, OTHER, bootstrap_macro_f1, summarize  # noqa: E402

from backend.app.diagnosis.xgb_classifier import ModelClassifier  # noqa: E402

DS = ROOT / "data" / "misconception_dataset"


def load_rows(split: str) -> list[dict]:
    labels = {}
    for line in (DS / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            labels[r["row_id"]] = r
    in_split = {r["row_id"] for r in csv.DictReader((DS / "splits" / "splits.csv").open(newline="", encoding="utf-8"))
                if r["split"] == split}
    rows = []
    with (DS / "features" / "features.csv").open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        names = header[2:]
        for rec in reader:
            if rec[0] not in in_split:
                continue
            meta = labels[rec[0]]
            feats = {n: (None if v in ("", "nan", "NaN") else float(v)) for n, v in zip(names, rec[2:])}
            rows.append({"row_id": rec[0], "truth": meta["label"], "source": meta["dataset_source"],
                         "problem": meta["problem_id"], "label_source": meta.get("label_source"), "features": feats})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-one-shot", action="store_true")
    ap.add_argument("--split", default="test")
    args = ap.parse_args()
    if not args.confirm_one_shot:
        print("REFUSED: rerun with --confirm-one-shot (each scoring of a held-out split is logged)")
        return 2
    rows = [r for r in load_rows(args.split) if r["label_source"] == "human"]
    models = {v: ModelClassifier.load(v) for v in ("best", "common", "execution")}
    systems = {"baseline: always OTHER_ERROR": [OTHER] * len(rows)}
    for v, m in models.items():
        preds = [m.predict(r["features"]) for r in rows]
        systems[f"model: {v}"] = [ABSTAIN if p.abstained else p.top_label for p in preds]
        if v == "execution":
            # The same model without its abstain threshold: the operating point the selection experiment compared.
            systems["model: execution, no abstain"] = [p.top_label for p in preds]
    rep = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "split": args.split,
           "n_rows": len(rows), "truth_counts": dict(Counter(r["truth"] for r in rows)),
           "problems": len({r["problem"] for r in rows}),
           "models": {v: {"sha256_16": m.model_sha256[:16], "temperature": m.temperature, "threshold": m.threshold}
                      for v, m in models.items()},
           "scopes": {}}
    scopes = {"all": list(range(len(rows)))}
    for src in sorted({r["source"] for r in rows}):
        scopes[src] = [i for i, r in enumerate(rows) if r["source"] == src]
    for scope, idx in scopes.items():
        truth = [rows[i]["truth"] for i in idx]
        groups = [rows[i]["problem"] for i in idx]
        res = {}
        for name, pred in systems.items():
            sub = [pred[i] for i in idx]
            s = summarize(truth, sub)
            s["accuracy"] = round(sum(t == p for t, p in zip(truth, sub)) / len(truth), 3)
            s["macro_f1_ci95_by_problem"] = bootstrap_macro_f1(truth, sub, groups)
            res[name] = s
        rep["scopes"][scope] = {"n": len(idx), "truth_counts": dict(Counter(truth)),
                                "problems": len(set(groups)), "systems": res}
    lanes = {}
    for path in sorted((DS / "annotations").glob("tier*.jsonl")):
        for line in path.open(encoding="utf-8"):
            if line.strip():
                lanes[json.loads(line)["row_id"]] = path.name.split("_")[0]
    by_lane = {}
    for lane in sorted({lanes[r["row_id"]] for r in rows}):
        idx = [i for i, r in enumerate(rows) if lanes[r["row_id"]] == lane]
        by_lane[lane] = {"rows": len(idx), "positives": sum(rows[i]["truth"] != OTHER for i in idx), "systems": {
            name: {"flagged": sum(pred[i] not in (OTHER, ABSTAIN) for i in idx),
                   "correct": sum(pred[i] == rows[i]["truth"] != OTHER for i in idx)}
            for name, pred in systems.items() if name.startswith("model")}}
    rep["by_lane"] = by_lane
    (DS / "reports" / "heldout_predictions.json").write_text(json.dumps(
        {"split": args.split, "rows": [[r["row_id"], r["source"], r["truth"]] + [systems[s][i] for s in systems if s != "baseline: always OTHER_ERROR"]
                                        for i, r in enumerate(rows)],
         "columns": ["row_id", "source", "truth"] + [s for s in systems if s != "baseline: always OTHER_ERROR"]}), encoding="utf-8")
    (DS / "reports" / "heldout_eval.json").write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8", newline="\n")

    def r(x):
        return f"{x['value']} [{x['ci95'][0]}, {x['ci95'][1]}] ({x['k']}/{x['n']})"

    lines = ["# Held-out problems: served models vs the always-OTHER baseline", "",
             f"Generated by `scripts/eval_heldout_rows.py` at {rep['at']}. Do not edit by hand.", "",
             f"- Rows: {rep['n_rows']} over {rep['problems']} unseen problems · truth {rep['truth_counts']}",
             f"- Models: {rep['models']}",
             "- Labels: independent annotator agents' consensus and blind labels, treated as human on the owner's instruction;"
             " every number is agreement with those annotators.", ""]
    names = [n for n in systems if n.startswith("model")]
    lines += ["## By data lane", "",
              "A model that flags one lane and nothing in another, on the same problems, is recognising the lane and not the bug.", "",
              "| Lane | Rows | Positives | " + " | ".join(f"{n}: flagged / correct" for n in names) + " |",
              "|---|---:|---:|" + "---:|" * len(names)]
    for lane, b in by_lane.items():
        lines.append(f"| {lane} | {b['rows']} | {b['positives']} | " + " | ".join(
            f"{b['systems'][n]['flagged']} / {b['systems'][n]['correct']}" for n in names) + " |")
    lines.append("")
    for scope, body in rep["scopes"].items():
        lines += [f"## {scope} (n={body['n']}, {body['problems']} problems)", "",
                  "| System | Accuracy | False alarm on OTHER | Precision when flagged | Misconception recall | Abstain | Macro-F1 [95% CI by problem] |",
                  "|---|---|---|---|---|---|---|"]
        for name, s in body["systems"].items():
            lines.append(f"| {name} | {s['accuracy']} | {r(s['false_alarm_rate'])} | {r(s['precision_when_flagged'])} | "
                         f"{r(s['misconception_recall'])} | {r(s['abstain_rate'])} | {s['macro_f1']} {s['macro_f1_ci95_by_problem']} |")
        for system in ("model: best", "model: execution", "model: execution, no abstain"):
            lines += ["", f"Per class ({system}):", "", "| Class | Support | Predicted | Correct | Precision | Recall |", "|---|---:|---:|---:|---:|---:|"]
            for c, v in body["systems"][system]["per_class"].items():
                lines.append(f"| {c} | {v['support']} | {v['predicted']} | {v['correct']} | {v['precision']} | {v['recall']} |")
        lines.append("")
    (DS / "reports" / "heldout_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with (DS / "reports" / "holdout_evaluations.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"split": f"heldout_rows_{args.split}", "at": rep["at"], "n": rep["n_rows"],
                             "models": rep["models"]}) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
