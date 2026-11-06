"""Applicability rules: classes a program cannot exhibit are ruled out before the abstain decision.

The rules are necessary-condition definitions. The tests pin three things:
the rules say what they claim, ruled-out mass goes to OTHER_ERROR (renormalizing
instead made unseen real code look MORE like a different misconception), and no
labelled training row is ever ruled out by its own label.
"""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from backend.app.diagnosis.applicability import RULES_BY_LABEL, move_ruled_out_mass, ruled_out
from backend.app.diagnosis.xgb_classifier import DEFAULT_MODELS_DIR, ModelClassifier

DATASET = Path(DEFAULT_MODELS_DIR).parent
ALL_THERE = {"static.loop_count": 3, "static.if_count": 2, "static.switch_count": 0, "static.array_decl_count": 1,
             "static.uses_vector": 0, "static.uses_malloc_free": 0, "semantics.recursion": 1,
             "semantics.idx_minus1": 0, "semantics.idx_plus1": 0}
FLAT = {"static.loop_count": 0, "static.if_count": 0, "static.switch_count": 0, "static.array_decl_count": 0,
        "static.uses_vector": 0, "static.uses_malloc_free": 0, "semantics.recursion": 0,
        "semantics.idx_minus1": 0, "semantics.idx_plus1": 0}


def test_a_program_with_every_construct_rules_nothing_out():
    assert ruled_out(ALL_THERE) == {}


def test_a_straight_line_program_rules_out_every_construct_dependent_class():
    out = ruled_out(FLAT)
    assert set(out) == set(RULES_BY_LABEL)
    assert "no loop" in out["CPP_LOOP_BOUNDARY"]
    assert "CPP_INT_OVERFLOW" not in out and "CPP_UNINITIALIZED_VAR" not in out and "CPP_OFF_BY_ONE" not in out


def test_a_loop_alone_keeps_loop_array_and_condition_classes_possible_but_not_recursion():
    out = ruled_out({**FLAT, "static.loop_count": 1})
    assert set(out) == {"CPP_MISSING_BASE_CASE"}


def test_missing_features_never_rule_a_class_out():
    assert ruled_out({}) == {}
    assert ruled_out({"static.loop_count": None, "semantics.recursion": None}) == {}


def test_recursion_is_the_only_thing_that_keeps_the_base_case_class_possible():
    assert "CPP_MISSING_BASE_CASE" in ruled_out({**ALL_THERE, "semantics.recursion": 0})
    assert "CPP_MISSING_BASE_CASE" not in ruled_out({**FLAT, "semantics.recursion": 1})


CLASSES = ["CPP_ARRAY_BOUNDS", "CPP_LOOP_BOUNDARY", "CPP_OTHER_ERROR", "CPP_RANGE_CHECK"]


def test_ruled_out_mass_moves_to_other_error_and_total_is_conserved():
    probs = np.array([0.5, 0.3, 0.1, 0.1])
    out = move_ruled_out_mass(probs, CLASSES, ["CPP_ARRAY_BOUNDS", "CPP_LOOP_BOUNDARY"])
    np.testing.assert_allclose(out, [0.0, 0.0, 0.9, 0.1])
    assert out.sum() == pytest.approx(1.0)
    assert probs.tolist() == [0.5, 0.3, 0.1, 0.1]            # input untouched


def test_unknown_or_open_set_labels_are_ignored_and_a_missing_sink_changes_nothing():
    probs = np.array([0.4, 0.3, 0.2, 0.1])
    np.testing.assert_allclose(move_ruled_out_mass(probs, CLASSES, ["CPP_OTHER_ERROR", "CPP_NOPE"]), probs)
    np.testing.assert_allclose(move_ruled_out_mass(probs, ["a", "b", "c", "d"], ["a"]), probs)


def test_no_labelled_training_row_is_ruled_out_by_its_own_label():
    labels = {}
    for line in (DATASET / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            labels[row["row_id"]] = row["label"]

    def num(v):
        return None if v in ("", "nan", "NaN") else float(v)

    checked = 0
    for row in csv.DictReader((DATASET / "features" / "features.csv").open(encoding="utf-8", newline="")):
        feats = {k: num(v) for k, v in row.items() if "." in k}
        assert labels[row["row_id"]] not in ruled_out(feats), row["row_id"]
        checked += 1
    assert checked >= 600


@pytest.fixture(scope="module")
def model():
    return ModelClassifier.load("best")


def test_the_classifier_never_answers_a_class_the_program_cannot_have(model):
    for variant_flat in (FLAT, {**FLAT, "static.loop_count": 1}):
        pred = model.predict(variant_flat)
        assert pred.top_label not in dict(pred.ruled_out)
        for label, _ in pred.ruled_out:
            assert pred.probabilities[label] == 0.0
        assert sum(pred.probabilities.values()) == pytest.approx(1.0, abs=1e-4)


def test_switching_the_rules_off_restores_the_raw_model_output(model):
    raw = model.predict(FLAT, apply_applicability=False)
    ruled = model.predict(FLAT)
    assert raw.ruled_out == ()
    assert len(ruled.ruled_out) > 0
    assert ruled.probabilities["CPP_OTHER_ERROR"] >= raw.probabilities["CPP_OTHER_ERROR"]


def test_the_prediction_records_why_a_class_was_ruled_out(model):
    pred = model.predict(FLAT)
    as_dict = pred.as_dict()
    assert {"label", "reason"} <= set(as_dict["ruled_out"][0])
