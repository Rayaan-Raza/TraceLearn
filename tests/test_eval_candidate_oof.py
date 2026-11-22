"""The P0 candidate harness (`scripts/eval_candidate_oof.py`) and the trainer's real/synthetic split."""
from __future__ import annotations

import json
from collections import Counter
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import eval_candidate_oof as H  # noqa: E402
import train_xgb_misconception as T  # noqa: E402

from backend.app.diagnosis.xgb_classifier import ModelClassifier  # noqa: E402

DS = ROOT / "data" / "misconception_dataset"
OTHER = "CPP_OTHER_ERROR"
CLASSES = ["CPP_INT_OVERFLOW", OTHER, "CPP_WRONG_LOOP_DIR"]
FEATURES = ["f1", "f2"]


def _clf(bars=None, threshold=0.5):
    base = ModelClassifier(variant="execution", booster=None, features=FEATURES, classes=CLASSES,
                           temperature=1.0, threshold=threshold, model_sha256="x")
    return H.PresetClassifier(base, features=FEATURES, temperature=1.0, threshold=threshold,
                              class_thresholds=bars or {})


def _row(rid, label, real=True, **feats):
    return {"row_id": rid, "label": label, "real": real, "features": {"f1": 1.0, "f2": 0.0, **feats}}


def test_candidate_needs_a_name_and_known_keys():
    with pytest.raises(ValueError, match="name"):
        H.load_candidate({"bars": "none"})
    with pytest.raises(ValueError, match="unknown"):
        H.load_candidate({"name": "x", "synthetic_weight": 0.5})
    cand = H.load_candidate({"name": "x", "note": "kept"})
    assert cand["folds"] == 3 and cand["repeats"] == 3 and cand["bars"] == "served"


def test_committed_candidates_load():
    for path in sorted((DS / "candidates").glob("*.json")):
        assert H.load_candidate(path)["name"] == path.stem


def test_decisions_go_through_the_runtime_rule_stages_first():
    clf = _clf()
    rows = [_row("a", "CPP_INT_OVERFLOW"),
            _row("b", "CPP_WRONG_LOOP_DIR", **{"repair.wrong_loop_dir_fix_all": 1.0}),
            _row("c", OTHER)]
    raw = np.array([[0.8, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.8, 0.1]])
    decided = H.decisions(clf, rows, raw, {})
    assert decided[0] == ("CPP_INT_OVERFLOW", "model")
    # the class rule overrides a classifier that said OTHER_ERROR
    assert decided[1] == ("CPP_WRONG_LOOP_DIR", "class_rule")
    assert decided[2] == (OTHER, "model")


def test_decisions_abstain_below_threshold_and_use_per_row_bars():
    clf = _clf(threshold=0.9)
    rows = [_row("a", "CPP_INT_OVERFLOW"), _row("b", "CPP_INT_OVERFLOW")]
    raw = np.array([[0.45, 0.5, 0.05], [0.45, 0.5, 0.05]])
    assert H.decisions(clf, rows, raw, {}) == [(H.ABSTAIN, "model"), (H.ABSTAIN, "model")]
    # a bar of 0.4 on the first row lifts the class out of the OTHER_ERROR majority
    decided = H.decisions(clf, rows, raw, {}, [{"CPP_INT_OVERFLOW": 0.4}, {}])
    assert decided[0] == ("CPP_INT_OVERFLOW", "model") and decided[1] == (H.ABSTAIN, "model")
    assert clf.class_thresholds == {}


def test_class_stats_counts_abstention_as_a_miss_and_marks_small_support():
    truth = ["A"] * 4 + [OTHER] * 2
    pred = ["A", "A", H.ABSTAIN, OTHER, OTHER, "A"]
    s = H.class_stats(truth, pred, "A")
    assert (s["tp"], s["support"], s["flagged"]) == (2, 4, 3)
    assert s["recall"] == 0.5 and s["precision"] == round(2 / 3, 4)
    assert not s["estimable"]
    lo, hi = s["recall_95"]
    assert 0 < lo < 0.5 < hi < 1
    assert H.class_stats(["A"] * 10, ["A"] * 10, "A")["estimable"]


def test_macro_f1_is_over_the_classes_present_in_the_truth():
    truth = ["A", "A", OTHER, OTHER]
    pred = ["A", "B", OTHER, OTHER]
    # B never appears in the truth, so it does not enter the mean
    assert H.macro_f1(truth, pred) == pytest.approx(np.mean([2 / 3, 1.0]))


def test_false_alarm_ignores_abstentions():
    fa = H.false_alarm([OTHER] * 4 + ["A"], ["A", H.ABSTAIN, OTHER, OTHER, "A"])
    assert (fa["k"], fa["n"], fa["value"]) == (1, 4, 0.25)


def test_stage_fires_split_real_and_synthetic():
    rows = [_row("r1", "CPP_WRONG_LOOP_DIR"), _row("r2", OTHER), _row("s1", "CPP_WRONG_LOOP_DIR", real=False)]
    decided = [("CPP_WRONG_LOOP_DIR", "class_rule"), ("CPP_WRONG_LOOP_DIR", "class_rule"),
               ("CPP_WRONG_LOOP_DIR", "class_rule")]
    st = H.stage_fires(rows, decided)["class_rule"]
    assert st["real"] == {"fires": 2, "right": 1, "wrong_rows": ["r2"]}
    assert st["synthetic"]["fires"] == 1 and st["synthetic"]["right"] == 1


def test_trainer_per_class_metrics_respects_the_mask():
    y = np.array([0, 0, 1, 1])
    pred = np.array([0, 1, 1, 1])
    real = np.array([True, True, False, False])
    allm = T.per_class_metrics(y, pred, ["A", "B"])
    realm = T.per_class_metrics(y, pred, ["A", "B"], real)
    synth = T.per_class_metrics(y, pred, ["A", "B"], ~real)
    assert allm["A"]["support"] == 2 and realm["A"]["recall"] == 0.5 and realm["B"]["support"] == 0
    assert synth["B"]["f1"] == 1.0 and synth["A"]["support"] == 0


def _fake_result(name, f1, support):
    stats = {"f1": f1, "support": support, "estimable": support >= H.MIN_SUPPORT, "recall_95": [0.1, 0.9]}
    return {"candidate": {"name": name, "bars": "served"},
            "rows": {"real": 100},
            "composition": {"CPP_STALE_EXIT": {"real": 8, "synthetic": 141}},
            "summary": {"macro_f1_real_mean": 0.5, "macro_f1_real_sd": 0.03, "macro_f1_real_pooled": 0.49,
                        "macro_f1_all_pooled": 0.8, "false_alarm_real_other_pooled": {"value": 0.03, "k": 3, "n": 100}},
            "pooled": {"per_class_real": {"CPP_STALE_EXIT": stats},
                       "rule_stages": {"repair": {"real": {"fires": 1, "right": 1, "wrong_rows": []},
                                                  "synthetic": {"fires": 0, "right": 0}}}}}


def test_compare_prints_not_estimable_for_small_classes(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(_fake_result("a", 0.33, 4)), encoding="utf-8")
    text = H.compare(tmp_path)
    assert "not estimable (4)" in text and "| STALE_EXIT | 8 / 141 |" in text
    assert "0.500 ± 0.030" in text and (tmp_path / "candidates.md").is_file()


SERVED = DS / "reports" / "candidates" / "served.json"


@pytest.mark.skipif(not SERVED.is_file(), reason="no committed served baseline")
def test_committed_baseline_reproduces_the_recorded_figure():
    """P0 passing check: the served configuration scores real-row macro-F1 within 0.50 +- 0.03."""
    r = json.loads(SERVED.read_text(encoding="utf-8"))
    assert r["candidate"]["name"] == "served" and not r["candidate"]["run_records"]
    assert abs(r["summary"]["macro_f1_real_pooled"] - 0.50) <= 0.03
    assert r["rows"]["by_split"] == {"train": r["rows"]["real"] + r["rows"]["synthetic"]}
    for cls in ("CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR", "CPP_MISSING_BASE_CASE"):
        assert not r["pooled"]["per_class_real"][cls]["estimable"]
    assert all(not math.isnan(v) for v in r["summary"]["macro_f1_real_per_repeat"])


def _cap_rows():
    rows = [{"label": "A", "real": True, "cluster": f"r{i}"} for i in range(10)]
    rows += [{"label": "A", "real": False, "cluster": f"s{i // 5}"} for i in range(40)]   # 8 clusters of 5
    rows += [{"label": "B", "real": True, "cluster": "rb"}]
    rows += [{"label": "B", "real": False, "cluster": "sb"} for _ in range(30)]
    return rows


def test_cap_keeps_whole_clusters_under_the_ratio_and_spares_rare_classes():
    out = H.cap_synthetic(_cap_rows(), {"ratio": 2, "min_real": 5}, seed=7)
    synth_a = [r for r in out if r["label"] == "A" and not r["real"]]
    assert len(synth_a) == 20                                   # 2 x 10 real, in clusters of 5
    clusters = Counter(r["cluster"] for r in synth_a)
    assert set(clusters.values()) == {5}
    assert sum(r["label"] == "B" and not r["real"] for r in out) == 30   # 1 real row: not capped
    assert sum(r["real"] for r in out) == 11


def test_cap_ratio_zero_removes_synthetic_rows_of_capped_classes():
    out = H.cap_synthetic(_cap_rows(), {"ratio": 0, "min_real": 0}, seed=7)
    assert all(r["real"] for r in out)


def test_estimable_macro_f1_ignores_classes_under_ten_rows():
    truth = ["A"] * 10 + ["B"]
    pred = ["A"] * 10 + ["A"]
    assert H.estimable_classes(truth) == ["A"]
    assert H.macro_f1_over(truth, pred, H.estimable_classes(truth)) == pytest.approx(20 / 21)


def _preds(pred):
    truth = (["A"] * 12 + [OTHER] * 12) * 2
    return {"real_predictions": {"row_id": [str(i) for i in range(len(truth))],
                                 "cluster": [f"c{i % 8}" for i in range(len(truth))],
                                 "truth": truth, "pred": pred}}


def test_paired_difference_is_zero_for_the_same_predictions_and_positive_for_a_clear_gain():
    truth = _preds([])["real_predictions"]["truth"]
    weak = [OTHER if t == "A" and i % 2 else t for i, t in enumerate(truth)]
    same = H.paired_difference(_preds(weak), _preds(weak), n=200)
    assert same["macro_f1_estimable_diff"] == 0 and same["macro_f1_estimable_diff_95"] == [0, 0]
    gain = H.paired_difference(_preds(weak), _preds(list(truth)), n=200)
    assert gain["macro_f1_estimable_diff"] > 0 and gain["macro_f1_estimable_diff_95"][0] > 0
    assert H.verdict(gain) == "better" and H.verdict(same) == "no difference shown"


def test_paired_difference_refuses_different_rows():
    a = _preds(["A"] * 48)
    b = _preds(["A"] * 48)
    b["real_predictions"]["row_id"] = list(reversed(b["real_predictions"]["row_id"]))
    with pytest.raises(ValueError):
        H.paired_difference(a, b)
