"""train_xgb_misconception.py tests (master plan §11.5 R6, G8).

The trainer (R6 -> G8) must:
- load the merged artifacts (features.csv + labels.jsonl + splits.csv);
- `assert gold not in train` IN-SCRIPT (dev-gold clusters held out);
- Layer-3 weights w = w_balance x w_confidence x w_source, clipped
  (clip <= 10; pilot uses [0.1, 10]);
- three variants: full / common-feature (static+warnings only) /
  masked (lf_inputs -> NaN on weak rows at train time, informational);
- one global threshold + temperature scaling on dev-gold ONLY (isotonic
  banned; per-class thresholds infeasible) with a recorded fallback
  note when dev-gold is too small to calibrate;
- StratifiedGroupKFold by problem cluster, macro-F1 vs majority baseline;
- G8 checks recorded in metrics (synthetic mass <= 50%, class mass
  <= 15%, weight clip, gold-not-in-train, threshold scope);
- deterministic under a fixed seed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.merge_dataset import flatten_features
from scripts.train_xgb_misconception import (
    compute_weights,
    ece,
    fit_temperature,
    mask_weak_inputs,
    train,
    tune_threshold,
)

LABELS = ["CPP_ARRAY_BOUNDS", "CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE"]


def _row(row_id: str, label: str, *, loc: int, loops: int, comments: int,
         source: str = "PROGPEDIA", label_source: str = "weak_rule",
         firing: list[str] | None = None, oob: int | None = None) -> dict:
    row = {
        "row_id": row_id,
        "dataset_source": source,
        "source_record_id": f"rec-{row_id}",
        "problem_id": None,  # filled by caller per cluster
        "problem_cluster": None,
        "language": "c",
        "label": label,
        "label_source": label_source,
        "label_confidence": 0.6 if label_source != "human" else 1.0,
        "secondary_labels": [],
        "verdict": "RUNTIME_ERROR",
        "firing_functions": firing or [],
        "seed_ref": None,
        "mutation_op": None,
        "verified_by_execution": label_source == "synthetic",
        "meta": {},
        "pipeline_run_id": "fixture/1.0.0",
        "taxonomy_version": "tl-cpp-v2",
        "schema_version": "1.0",
        "static": {"loc": loc, "sloc": loc - comments, "comment_lines": comments,
                   "loop_count": loops, "if_count": loops // 2 + 1},
        "warnings": {"available": False},
        "runtime": {"available": False},
        "tests": {"available": False},
        "cpg": {"array_write_oob_count": oob if oob is not None else 0},
        "context": {"available": False},
    }
    return row


def _build_dataset(tmp_path: Path, *, dev_gold_small: bool = False) -> Path:
    """3 separable classes across train clusters + held-out dev-gold."""
    rows: list[dict] = []
    clusters: list[tuple[str, str, str]] = []  # problem_id, cluster, split
    for c in range(6):  # 6 train clusters
        clusters.append((f"p-t{c}", f"clu-t{c:02d}", "train"))
        for i, label in enumerate(LABELS):
            rows.append(_row(
                f"pg-t{c}{i}", label,
                loc=100 + i * 40 + c, loops=1 + i * 5, comments=i,
                firing=["pg-3"] if i == 0 else [], oob=3 if i == 0 else 0,
            ) | {"problem_id": f"p-t{c}"})
    n_dev = 4 if dev_gold_small else 12
    for c in range(2):  # 2 dev-gold clusters, disjoint from train
        clusters.append((f"p-d{c}", f"clu-d{c:02d}", "dev_gold"))
        for i in range(n_dev // 2):
            label = LABELS[i % 3]
            base = 100 + (i % 3) * 40 + c
            rows.append(_row(
                f"pg-d{c}{i}", label,
                loc=base, loops=1 + (i % 3) * 5, comments=i % 3,
            ) | {"problem_id": f"p-d{c}"})
    clusters.append(("p-s", "clu-s00", "test"))
    rows.append(_row("pg-s00", LABELS[0], loc=105, loops=3, comments=0) | {"problem_id": "p-s"})

    ds = tmp_path / "ds"
    (ds / "annotations").mkdir(parents=True)
    with (ds / "annotations" / "labels.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    import csv as _csv
    flat = flatten_features(rows)
    (ds / "features").mkdir()
    with (ds / "features" / "features.csv").open("w", encoding="utf-8", newline="") as fh:
        names = list(flat[0])[2:]
        writer = _csv.DictWriter(fh, fieldnames=["row_id", "label"] + names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(flat)
    (ds / "features" / "label_defining_features.json").write_text(json.dumps({
        "entries": {
            "pg-3": {"kind": "lf", "status": "active", "confidence_cap": 0.6,
                     "features": ["cpg.array_write_oob_count"]},
            "synthetic_ops": {"kind": "operator_group", "status": "active",
                              "confidence_cap": 1.0, "features": []},
        }
    }), encoding="utf-8")

    (ds / "splits").mkdir()
    with (ds / "splits" / "splits.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = _csv.writer(fh, lineterminator="\n")
        writer.writerow(["row_id", "problem_id", "cluster_id", "split"])
        by_problem = {pid: (cid, split) for pid, cid, split in clusters}
        for r in rows:
            cid, split = by_problem[r["problem_id"]]
            writer.writerow([r["row_id"], r["problem_id"], cid, split])
    (ds / "splits" / "cluster_assignments.csv").write_text(
        "problem_id,cluster_id,split,statement_len\n" + "".join(
            f"{p},{c},{s},10\n" for p, c, s in clusters
        ), encoding="utf-8")
    return ds


def _run(ds: Path, tmp_path: Path, **kw):
    return train(dataset_dir=ds, models_dir=tmp_path / "models", seed=7, **kw)


# ------------------------------------------------------------- outputs


def test_train_writes_models_metrics_encoder_calibrator(tmp_path: Path):
    ds = _build_dataset(tmp_path)
    metrics = _run(ds, tmp_path)
    models = tmp_path / "models"
    for name in ("xgb_v1.json", "xgb_masked_v1.json", "xgb_common_v1.json",
                 "metrics_v1.json", "label_encoder.json", "calibrator.json"):
        assert (models / name).is_file(), name
    encoder = json.loads((models / "label_encoder.json").read_text(encoding="utf-8"))
    assert set(encoder["class_to_idx"]) == set(LABELS)
    assert metrics["cv"]["macro_f1_mean"] >= 0.0
    assert metrics["g8"]["gold_not_in_train"] is True


def test_dev_gold_clusters_must_be_absent_from_train(tmp_path: Path):
    # one cluster leaking into both train and dev_gold -> the held-out
    # discipline is violated: loud failure, never a quiet overlap
    ds = _build_dataset(tmp_path)
    splits = ds / "splits" / "splits.csv"
    lines = splits.read_text(encoding="utf-8").splitlines()
    # move one dev-gold row onto a train cluster
    lines = [l if not l.startswith("pg-d00,") else "pg-d00,p-t0,clu-t00,dev_gold" for l in lines]
    splits.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="gold"):
        _run(ds, tmp_path)


# --------------------------------------------------------------- weights


def test_compute_weights_formula_and_clip():
    import pandas as pd

    meta = pd.DataFrame({
        "label": ["A", "A", "B", "B", "C"],
        "label_confidence": [0.6, 1.0, 0.6, 0.6, 0.6],
        "dataset_source": ["SYNTHETIC", "SYNTHETIC", "PROGPEDIA", "SYNTHETIC", "PROGPEDIA"],
    })
    w, stats = compute_weights(meta, synthetic_multiplier=0.5, clip=(0.1, 10.0))
    # w = clip(w_balance * w_confidence * w_source, 0.1, 10)
    assert w.shape == (5,)
    assert stats["clip_applied"] >= 0
    assert (w <= 10.0 + 1e-9).all() and (w >= 0.1 - 1e-9).all()
    # same class+source, confidence is the only difference -> exact ratio
    assert abs(w[0] / w[1] - 0.6) < 1e-9
    # same class+confidence, source is the only difference -> real/syn = 1/mult
    assert abs(w[2] / w[3] - 2.0) < 1e-9


# --------------------------------------------------------------- masking


def test_mask_weak_inputs_nans_firing_inputs_only():
    names = ["cpg.array_write_oob_count", "static.loc"]
    X = np.array([[3.0, 10.0], [0.0, 20.0], [5.0, 30.0]])
    meta = [
        {"row_id": "w1", "label_source": "weak_rule", "firing_functions": ["pg-3"]},
        {"row_id": "s1", "label_source": "synthetic", "firing_functions": []},
        {"row_id": "h1", "label_source": "human", "firing_functions": []},
    ]
    registry = {"pg-3": ["cpg.array_write_oob_count"]}
    Xm = mask_weak_inputs(X, names, meta, registry)
    assert np.isnan(Xm[0, 0])            # weak row: firing input masked
    assert Xm[0, 1] == 10.0              # other features intact
    assert Xm[1].tolist() == [0.0, 20.0]  # synthetic untouched
    assert Xm[2].tolist() == [5.0, 30.0]  # human untouched


def test_masked_variant_reported_informational_with_disclosure(tmp_path: Path):
    ds = _build_dataset(tmp_path)
    metrics = _run(ds, tmp_path)
    assert "informational" in metrics["masked"]["role"]
    assert metrics["masked"]["train_test_mismatch"]


# ---------------------------------------------------- calibration pieces


def test_fit_temperature_reduces_nll_and_threshold_ties_break_high():
    rng = np.random.default_rng(0)
    logits = rng.normal(size=(40, 3))
    probs = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
    y = rng.integers(0, 3, size=40)
    T = fit_temperature(probs, y)
    assert 0.05 <= T <= 5.0

    # abstain-as-wrong threshold tuning; ties break to the HIGHEST threshold
    p = np.array([[0.45, 0.30, 0.25], [0.45, 0.30, 0.25],
                  [0.90, 0.05, 0.05], [0.90, 0.05, 0.05]])
    yy = np.array([0, 0, 0, 0])
    # t <= 0.45 keeps all four (macro-F1 = 1); the highest tying threshold
    # is 0.45 (0.50 would abstain on the two 0.45 rows)
    assert tune_threshold(p, yy) == 0.45


def test_ece_confident_correct_zero_confident_wrong_high():
    p_ok = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
    p_bad = np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    y = np.array([0, 0, 1, 1])
    assert ece(p_ok, y) < 1e-9
    assert ece(p_bad, y) > 0.4  # accuracy 0.5 vs confidence 1.0


def test_calibration_falls_back_when_dev_gold_too_small(tmp_path: Path):
    ds = _build_dataset(tmp_path, dev_gold_small=True)  # 4 dev-gold rows
    metrics = _run(ds, tmp_path)
    cal = json.loads((tmp_path / "models" / "calibrator.json").read_text(encoding="utf-8"))
    assert cal["temperature"] == 1.0
    assert "too small" in cal["note"]
    assert metrics["g8"]["dev_gold_n"] == 4


# ------------------------------------------------------ variants + G8


def test_common_variant_static_warnings_only(tmp_path: Path):
    ds = _build_dataset(tmp_path)
    metrics = _run(ds, tmp_path)
    feats = metrics["common"]["features"]
    assert feats, "common variant must record its feature set"
    assert all(f.startswith(("static.", "warnings.")) for f in feats)


def test_synth_multiplier_selection_recorded_and_in_grid(tmp_path: Path):
    ds = _build_dataset(tmp_path)
    metrics = _run(ds, tmp_path)
    sel = metrics["cv"]["synthetic_multiplier"]
    assert sel in (0.5, 0.75, 1.0)
    # JSON stringifies float keys; the file round-trip is the contract
    assert set(metrics["cv"]["grid_scores"]) <= {"0.5", "0.75", "1.0"}


def test_g8_block_reports_masses_and_baselines(tmp_path: Path):
    ds = _build_dataset(tmp_path)
    metrics = _run(ds, tmp_path)
    g8 = metrics["g8"]
    assert g8["weight_clip"] == 10.0
    assert 0.0 <= g8["synthetic_mass"] <= 1.0
    assert 0.0 < g8["max_class_mass"] <= 1.0
    assert g8["threshold_scope"] == "one global threshold + temperature"
    assert g8["isotonic_used"] is False
    assert metrics["cv"]["majority_baseline"] >= 0.0
    assert metrics["cv"]["macro_f1_mean"] - metrics["cv"]["majority_baseline"] > 0.25


def test_deterministic_rerun_same_metrics(tmp_path: Path):
    ds = _build_dataset(tmp_path)
    m1 = _run(ds, tmp_path / "r1")
    m2 = _run(ds, tmp_path / "r2")
    assert m1["cv"]["macro_f1_mean"] == m2["cv"]["macro_f1_mean"]
    assert m1["cv"]["grid_scores"] == m2["cv"]["grid_scores"]
