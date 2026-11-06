"""Gates I2 (prediction golden) and I3 (contract) for the trained classifier,
plus the model-evidence fusion rules (B3, B4).

The golden fixture pins what the *current* model returns for one training row
per class. It protects against silent change (a retrain, a library upgrade, a
reordered feature list), not against the model being right: one in-sample row
is predicted as a different class and the fixture records that as it is.
Regenerate with `python scripts/make_model_golden.py` and review the diff.
"""
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.analysis.model_evidence import model_evidence
from backend.app.config import Settings
from backend.app.diagnosis.confidence import apply_evidence_weights, fuse_diagnosis
from backend.app.diagnosis.cpp_mapping import MODEL_LABEL_TO_BACKEND, backend_code_for_model_label
from backend.app.diagnosis.taxonomy import (
    CPP_MISCONCEPTIONS,
    CPP_OTHER_ERROR,
    CPP_RANGE_CHECK,
    NO_MISCONCEPTION,
    UNCERTAIN,
)
from backend.app.diagnosis.xgb_classifier import (
    DEFAULT_MODELS_DIR,
    ModelClassifier,
    ModelContractError,
    ModelPrediction,
)
from tracelearn_features.schema import feature_names

GOLDEN = Path(__file__).parent / "fixtures" / "model_golden.json"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def model(golden):
    return ModelClassifier.load(golden["variant"])


@pytest.fixture()
def models_copy(tmp_path):
    target = tmp_path / "models"
    shutil.copytree(DEFAULT_MODELS_DIR, target)
    return target


def _edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")


# ----------------------------------------------------------- I2 golden


def test_golden_predictions_match(model, golden):
    assert model.model_sha256 == golden["model_sha256"], (
        "model file changed: run scripts/make_model_golden.py and review the diff"
    )
    assert model.temperature == golden["temperature"]
    assert model.threshold == golden["threshold"]
    assert len(golden["cases"]) >= 10
    for case in golden["cases"]:
        pred = model.predict(case["features"])
        want = case["expected"]
        assert pred.top_label == want["top_label"], case["row_id"]
        assert pred.abstained == want["abstained"], case["row_id"]
        for label, p in want["probabilities"].items():
            assert math.isclose(pred.probabilities[label], p, abs_tol=1e-4), (case["row_id"], label)


def test_probabilities_are_a_distribution(model, golden):
    for case in golden["cases"]:
        pred = model.predict(case["features"])
        assert math.isclose(sum(pred.probabilities.values()), 1.0, abs_tol=1e-4)
        assert all(0.0 <= p <= 1.0 for p in pred.probabilities.values())
        assert pred.top_probability == max(pred.probabilities.values())
        assert pred.top_k[0] == (pred.top_label, pred.top_probability)
        assert [p for _, p in pred.top_k] == sorted((p for _, p in pred.top_k), reverse=True)


def test_prediction_is_identical_in_a_fresh_process(golden):
    case = golden["cases"][0]
    script = (
        "import json,sys;"
        "from backend.app.diagnosis.xgb_classifier import ModelClassifier;"
        "d=json.load(open(sys.argv[1]));c=d['cases'][0];"
        "p=ModelClassifier.load(d['variant']).predict(c['features']);"
        "print(json.dumps(p.probabilities,sort_keys=True))"
    )
    out = subprocess.run(
        [sys.executable, "-c", script, str(GOLDEN)],
        cwd=ROOT, capture_output=True, text=True, timeout=120, check=True,
    ).stdout
    other = json.loads(out)
    here = ModelClassifier.load(golden["variant"]).predict(case["features"]).probabilities
    assert other == here


# ------------------------------------------------------- I3 contract


def test_feature_order_comes_from_the_artifact_and_fits_the_schema(model):
    assert len(model.features) == len(set(model.features)) > 0
    assert set(model.features) <= set(feature_names())


def test_missing_features_become_nan_and_prediction_still_works(model):
    row, missing = model.vector({})
    assert missing == len(model.features)
    assert row.shape == (1, len(model.features))
    assert all(math.isnan(v) for v in row[0])
    pred = model.predict({})
    assert pred.n_missing == pred.n_features
    assert math.isclose(sum(pred.probabilities.values()), 1.0, abs_tol=1e-4)


def test_non_numeric_and_infinite_values_are_treated_as_missing(model):
    name = model.features[0]
    row, missing = model.vector({name: "not a number", model.features[1]: math.inf, model.features[2]: True})
    assert math.isnan(row[0, 0]) and math.isnan(row[0, 1])
    assert row[0, 2] == 1.0
    assert missing == len(model.features) - 1


def test_unknown_keys_are_ignored(model):
    base = model.predict({})
    assert model.predict({"not.a.feature": 3}).probabilities == base.probabilities


@pytest.mark.parametrize("variant", ["full", "common", "best"])
def test_every_servable_variant_loads(variant):
    loaded = ModelClassifier.load(variant)
    assert loaded.variant == variant
    assert loaded.classes == ModelClassifier.load("best").classes


def test_unknown_variant_is_refused():
    with pytest.raises(ModelContractError, match="unknown variant"):
        ModelClassifier.load("nope")


def test_missing_model_file_is_refused(models_copy):
    (models_copy / "xgb_best_v1.json").unlink()
    with pytest.raises(ModelContractError, match="model file missing"):
        ModelClassifier.load("best", models_copy)


def test_corrupt_model_file_is_refused(models_copy):
    (models_copy / "xgb_best_v1.json").write_text("{not a model", encoding="utf-8")
    with pytest.raises(ModelContractError):
        ModelClassifier.load("best", models_copy)


def test_feature_absent_from_the_schema_is_refused(models_copy):
    _edit_json(models_copy / "metrics_v1.json", lambda m: m["best"]["features"].__setitem__(0, "static.renamed"))
    with pytest.raises(ModelContractError, match="absent from the current schema"):
        ModelClassifier.load("best", models_copy)


def test_feature_count_mismatch_is_refused(models_copy):
    _edit_json(models_copy / "metrics_v1.json", lambda m: m["best"]["features"].pop())
    with pytest.raises(ModelContractError, match="booster expects"):
        ModelClassifier.load("best", models_copy)


def test_inconsistent_label_encoder_is_refused(models_copy):
    def swap(enc):
        enc["class_to_idx"]["CPP_ARRAY_BOUNDS"], enc["class_to_idx"]["CPP_ASSIGN_VS_COMPARE"] = 1, 0

    _edit_json(models_copy / "label_encoder.json", swap)
    with pytest.raises(ModelContractError, match="disagrees"):
        ModelClassifier.load("best", models_copy)


def test_label_encoder_with_a_different_class_count_is_refused(models_copy):
    def drop(enc):
        enc["idx_to_class"].pop()
        enc["class_to_idx"].popitem()

    _edit_json(models_copy / "label_encoder.json", drop)
    _edit_json(models_copy / "metrics_v1.json", lambda m: m.__setitem__("classes", m["classes"][:-1]))
    with pytest.raises(ModelContractError, match="classes"):
        ModelClassifier.load("best", models_copy)


@pytest.mark.parametrize("patch", [{"temperature": 0}, {"temperature": -1}, {"threshold": 0}, {"threshold": 1.5}])
def test_bad_calibrator_is_refused(models_copy, patch):
    _edit_json(models_copy / "calibrator.json", lambda c: c.update(patch))
    with pytest.raises(ModelContractError, match="calibrator"):
        ModelClassifier.load("best", models_copy)


def test_a_high_threshold_makes_the_model_abstain(models_copy, golden):
    _edit_json(models_copy / "calibrator.json", lambda c: c.update(threshold=1.0))
    strict = ModelClassifier.load("best", models_copy)
    pred = strict.predict(golden["cases"][0]["features"])
    assert pred.abstained is True


def test_every_model_label_has_a_backend_decision(model):
    assert set(model.classes) == set(MODEL_LABEL_TO_BACKEND), "a model class has no backend mapping"
    for label in model.classes:
        code = backend_code_for_model_label(label)
        if label == CPP_OTHER_ERROR:
            assert code is None
        else:
            assert code in CPP_MISCONCEPTIONS
    with pytest.raises(KeyError):
        backend_code_for_model_label("CPP_NEW_CLASS")


def test_mapping_is_one_to_one_for_real_beliefs():
    codes = [c for c in MODEL_LABEL_TO_BACKEND.values() if c]
    assert len(codes) == len(set(codes))


def test_model_is_off_by_default():
    assert Settings().model_diagnosis == "off"


# ----------------------------------------------- B4 model evidence + fusion


def _prediction(label: str, p: float, abstained: bool = False) -> ModelPrediction:
    probabilities = {label: p}
    return ModelPrediction(
        variant="best", model_sha256="0" * 64, top_label=label, top_probability=p,
        abstained=abstained, threshold=0.3, temperature=1.2, probabilities=probabilities,
        top_k=((label, p),), n_features=59, n_missing=0,
    )


def test_confident_label_becomes_weighted_support():
    rec = model_evidence(_prediction("CPP_RANGE_CHECK", 0.9), max_weight=0.4)
    assert (rec.source_type, rec.evidence_code, rec.direction) == ("model", "MODEL_PREDICTION", "support")
    assert rec.misconception_id == CPP_RANGE_CHECK
    assert rec.weight == pytest.approx(0.36)
    assert rec.details["model_sha256"] == "0" * 64   # provenance travels with the record


def test_abstention_and_other_error_carry_no_weight():
    abstained = model_evidence(_prediction("CPP_RANGE_CHECK", 0.2, abstained=True))
    other = model_evidence(_prediction("CPP_OTHER_ERROR", 0.9))
    for rec, code in ((abstained, "MODEL_ABSTAINED"), (other, "MODEL_OTHER_ERROR")):
        assert (rec.evidence_code, rec.direction, rec.weight, rec.misconception_id) == (code, "neutral", 0.0, None)


def test_weight_survives_apply_evidence_weights():
    rec = model_evidence(_prediction("CPP_RANGE_CHECK", 0.9), max_weight=0.4)
    out = apply_evidence_weights([rec])[0]
    assert out.weight == pytest.approx(0.36)
    assert out.misconception_id == CPP_RANGE_CHECK


def test_confident_model_alone_selects_its_misconception():
    result = fuse_diagnosis([model_evidence(_prediction("CPP_RANGE_CHECK", 0.98), max_weight=0.4)])
    assert result["primary"] == CPP_RANGE_CHECK


def test_weak_model_alone_is_uncertain_not_a_confident_label():
    result = fuse_diagnosis([model_evidence(_prediction("CPP_RANGE_CHECK", 0.40), max_weight=0.4)])
    assert result["primary"] == UNCERTAIN and result["requires_review"] is True


@pytest.mark.parametrize("neutral", [
    _prediction("CPP_RANGE_CHECK", 0.2, abstained=True),
    _prediction("CPP_OTHER_ERROR", 0.95),
])
def test_neutral_model_output_never_changes_the_rule_result(neutral):
    rule = EvidenceRecord(
        source_type="static", evidence_code="CPP_ASSIGN_IN_CONDITION", direction="support", weight=0.3,
        description="assignment in condition", misconception_id="CPP_ASSIGN_VS_COMPARE",
    )
    alone = fuse_diagnosis([rule])
    with_model = fuse_diagnosis([rule, model_evidence(neutral)])
    assert with_model["primary"] == alone["primary"]
    assert with_model["primary_confidence"] == alone["primary_confidence"]


def test_all_tests_passing_still_wins_over_the_model():
    passed = EvidenceRecord(
        source_type="test", evidence_code="TEST_ALL_PASSED", direction="neutral", weight=0.0,
        description="all tests passed",
    )
    result = fuse_diagnosis([passed, model_evidence(_prediction("CPP_RANGE_CHECK", 0.98), max_weight=0.4)])
    assert result["primary"] == NO_MISCONCEPTION
