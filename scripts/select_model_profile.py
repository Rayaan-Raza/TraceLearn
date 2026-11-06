"""Choose the training profile from grouped out-of-fold results only (never the blind test).

    python scripts/select_model_profile.py

For each profile in `train_xgb_misconception.PROFILES`, on the served `best` columns:

1. out-of-fold probabilities from the trainer's own grouped folds (3 repeats);
2. temperature + abstain threshold from `scripts/calibration.py` on those folds;
3. the applicability rules, then the metrics on the NON-SYNTHETIC rows at that operating
   point: macro-F1 (abstention counts as a miss), false-alarm rate on real OTHER_ERROR rows,
   precision when flagged, recall, abstain rate;
4. an overfit check: the same profile fitted on all training rows and scored on those same
   rows (in-sample macro-F1) against the out-of-fold macro-F1.

Pre-registered rule, written before the numbers were seen: take the profile with the
highest real-row macro-F1 whose false-alarm rate is at most 0.30; profiles within 0.01 of
the best are treated as tied and the shallower (simpler) one wins. Labels on real rows
include weak and assumed-human ones, so this ranks profiles against each other; it is not
an accuracy estimate. Writes reports/model_profile_selection.json / .md.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import eval_baselines as eb  # noqa: E402
import train_xgb_misconception as trainer  # noqa: E402

from backend.app.diagnosis.applicability import move_ruled_out_mass, ruled_out  # noqa: E402
from scripts.calibration import calibrate_variant, rescale  # noqa: E402

DS = eb.DATASET_DIR
OTHER = "CPP_OTHER_ERROR"
MAX_FALSE_ALARM = 0.30
TIE = 0.01
SIMPLICITY = ["strong", "regular", "default"]      # simplest first
MULTIPLIER = 0.75


def real_metrics(P: np.ndarray, y: np.ndarray, feats: list[dict], classes: list[str], real: np.ndarray,
                 temperature: float, threshold: float) -> dict[str, Any]:
    scaled = rescale(P, temperature)
    scaled = np.array([move_ruled_out_mass(p, classes, ruled_out(f)) for p, f in zip(scaled, feats)])
    top = scaled.argmax(1)
    abst = scaled.max(1) < threshold
    truth = [classes[i] for i in y[real]]
    pred = ["ABSTAIN" if a else classes[t] for a, t in zip(abst[real], top[real])]
    other_idx = [i for i, t in enumerate(truth) if t == OTHER]
    flagged = [i for i, p in enumerate(pred) if p not in (OTHER, "ABSTAIN")]
    misc_idx = [i for i, t in enumerate(truth) if t != OTHER]
    labels = sorted(set(truth))
    f1s = []
    for c in labels:
        tp = sum(1 for t, p in zip(truth, pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(truth, pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(truth, pred) if t == c and p != c)
        f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    return {
        "real_rows": len(truth),
        "macro_f1": round(float(np.mean(f1s)), 4),
        "false_alarm_on_other": round(sum(1 for i in other_idx if pred[i] not in (OTHER, "ABSTAIN")) / max(len(other_idx), 1), 3),
        "precision_when_flagged": round(sum(1 for i in flagged if pred[i] == truth[i]) / max(len(flagged), 1), 3) if flagged else None,
        "misconception_recall": round(sum(1 for i in misc_idx if pred[i] == truth[i]) / max(len(misc_idx), 1), 3),
        "abstain_rate": round(float(np.mean([p == "ABSTAIN" for p in pred])), 3),
    }


def evaluate_profile(pool: dict[str, Any], profile: str, seed: int = 7, repeats: int = 3) -> dict[str, Any]:
    trainer.set_profile(profile)
    names, classes, k = pool["features"], pool["classes"], len(pool["classes"])
    cols = eb.columns_for(names, ("static", "warnings", "semantics"))
    tri = np.flatnonzero(pool["split"] == "train")
    Xfull, yt, ct = pool["X"][tri], pool["y"][tri], pool["cluster"][tri]
    Xt = Xfull[:, cols]
    meta = pool["meta"].iloc[tri].reset_index(drop=True)
    real = pool["source"][tri] != "SYNTHETIC"
    feats = [{n: (None if math.isnan(v) else float(v)) for n, v in zip(names, row)} for row in Xfull]

    reps = []
    for rep in range(repeats):
        P = np.zeros((len(yt), k))
        for _, tr, va in eb.folds(yt, ct, seed + rep, 1):
            w, _ = trainer.compute_weights(meta.iloc[tr].reset_index(drop=True), MULTIPLIER)
            P[va] = trainer._fit_predict(Xt[tr], yt[tr], w, Xt[va], seed + rep, k)
        reps.append(P)
    cal = calibrate_variant(reps, yt, ct, real, seed, other_idx=classes.index(OTHER))
    stacked = np.vstack(reps)
    metrics = real_metrics(stacked, np.tile(yt, repeats), feats * repeats, classes, np.tile(real, repeats),
                           cal["temperature"], cal["threshold"])

    w, _ = trainer.compute_weights(meta, MULTIPLIER)
    model, present = trainer._fit_model(Xt, yt, w, seed)
    insample = trainer._to_global(model.predict_proba(Xt), present, k).argmax(1)
    oof_f1 = float(np.mean([trainer.macro_f1(yt, P.argmax(1), list(range(k))) for P in reps]))
    return {"profile": profile, "temperature": cal["temperature"], "threshold": cal["threshold"],
            "threshold_bootstrap": [cal["bootstrap"].get("p05"), cal["bootstrap"].get("p95")],
            "oof_macro_f1_all_rows": round(oof_f1, 4),
            "in_sample_macro_f1": round(trainer.macro_f1(yt, insample, list(range(k))), 4),
            **metrics}


def choose(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Pre-registered rule: best real macro-F1 with false alarm <= 0.30; near-ties go to the simpler profile."""
    ok = [r for r in results if r["false_alarm_on_other"] <= MAX_FALSE_ALARM]
    pool = ok or results
    best = max(r["macro_f1"] for r in pool)
    tied = [r for r in pool if best - r["macro_f1"] <= TIE]
    return min(tied, key=lambda r: SIMPLICITY.index(r["profile"]))


def main() -> int:
    pool = eb.load_training_pool(DS)
    results = []
    for name in trainer.PROFILES:
        r = evaluate_profile(pool, name)
        results.append(r)
        print(f"{name:8s} real macro-F1 {r['macro_f1']:.3f}  false alarm {r['false_alarm_on_other']:.3f}  "
              f"precision {r['precision_when_flagged']}  recall {r['misconception_recall']}  abstain {r['abstain_rate']}  "
              f"| OOF {r['oof_macro_f1_all_rows']:.3f} vs in-sample {r['in_sample_macro_f1']:.3f}  thr {r['threshold']}",
              flush=True)
    trainer.set_profile("default")
    chosen = choose(results)
    out = {"rule": __doc__.split("Pre-registered rule, written before the numbers were seen:")[1].split("Labels on real")[0].strip(),
           "chosen": chosen["profile"], "results": results}
    (DS / "reports" / "model_profile_selection.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Model profile selection (grouped out-of-fold only)", "",
             "Generated by `scripts/select_model_profile.py`. Do not edit by hand.", "",
             f"Rule: {out['rule']}", "", f"**Chosen: `{chosen['profile']}`**", "",
             "| Profile | Real-row macro-F1 | False alarm on OTHER | Precision when flagged | Misconception recall | Abstain | "
             "OOF macro-F1 (all rows) | In-sample macro-F1 | Threshold |", "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['profile']} | {r['macro_f1']} | {r['false_alarm_on_other']} | {r['precision_when_flagged']} | "
                     f"{r['misconception_recall']} | {r['abstain_rate']} | {r['oof_macro_f1_all_rows']} | "
                     f"{r['in_sample_macro_f1']} | {r['threshold']} |")
    (DS / "reports" / "model_profile_selection.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("chosen:", chosen["profile"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
