"""Inference wrapper for the trained XGBoost misconception classifier.

The trainer (`scripts/train_xgb_misconception.py`) saves four native boosters,
a label encoder, one global temperature + threshold, and `metrics_v1.json`,
which lists the exact feature order each variant was trained on. This module
loads those artifacts and turns a feature mapping into a calibrated
prediction. It does not build features; that is the job of the feature builder.

Contract (blueprint §9, §12; master plan §11):

1. The feature order is read from `metrics_v1.json`, never re-derived, so a
   retrain cannot silently disagree with the server.
2. A feature the caller does not supply is NaN. XGBoost handles NaN natively
   and the dataset keeps NaN for missing evidence.
3. Probabilities pass through temperature scaling (`_rescale` in the trainer).
   If the best probability is below the variant's threshold the prediction
   abstains; the caller then falls back to the rule engine. Each served
   variant has its own temperature and threshold in `calibrator.json`
   ("variants"), fitted by `scripts/calibration.py`.
4. Loading refuses a model whose artifacts disagree (class list, feature list
   against the schema, booster width, output width).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from backend.app.diagnosis.applicability import move_ruled_out_mass, ruled_out
from tracelearn_features.schema import feature_names as schema_feature_names

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODELS_DIR = REPO_ROOT / "data" / "misconception_dataset" / "models"

VARIANT_FILES: dict[str, str] = {
    "full": "xgb_v1.json",
    "masked": "xgb_masked_v1.json",
    "common": "xgb_common_v1.json",
    "best": "xgb_best_v1.json",
    "execution": "xgb_execution_v1.json",
}
TOP_K = 3

# Repair-first stage: if exactly one class has repair.{class}_fix_all == 1 in
# the feature mapping, that class overrides the model's label. Measured on real
# rows (docs/6-nov.md section 15, senior review 2026-11-09): right on 102 of 115
# training-problem rows (0.89) and 27 of 29 held-out rows (0.93). Not 100%: a
# passing edit shows *a* fix, and the annotators sometimes name another cause.
_REPAIR_FIX_ALL_FEATURES: dict[str, str] = {
    "CPP_LOOP_BOUNDARY": "repair.loop_boundary_fix_all",
    "CPP_OFF_BY_ONE": "repair.off_by_one_fix_all",
    "CPP_ARRAY_BOUNDS": "repair.array_bounds_fix_all",
    "CPP_UNINITIALIZED_VAR": "repair.uninitialized_var_fix_all",
    "CPP_INT_OVERFLOW": "repair.int_overflow_fix_all",
    "CPP_MISSING_BASE_CASE": "repair.missing_base_case_fix_all",
    "CPP_ASSIGN_VS_COMPARE": "repair.assign_vs_compare_fix_all",
    "CPP_WRONG_LOOP_DIR": "repair.wrong_loop_dir_fix_all",
    "CPP_RANGE_CHECK": "repair.range_check_fix_all",
}


def repair_override(features: Mapping[str, Any]) -> str | None:
    """Return the unique class whose repair fixes all tests, or None.

    When exactly one class has ``repair.{class}_fix_all == 1`` in the feature
    mapping, that class explains the failing tests with certainty — no model
    inference is needed. When zero or more than one class fires, return None
    so the model runs normally.
    """
    hits = [
        cls
        for cls, feat in _REPAIR_FIX_ALL_FEATURES.items()
        if _as_float(features.get(feat)) == 1.0
    ]
    return hits[0] if len(hits) == 1 else None


# Which stage of the runtime decided a prediction. `model` = the classifier; every other value
# is a rule that runs before it and replaces its label.
DECISION_SOURCES = ("model", "repair")

# Measured precision of each rule stage as (correct, total) on real rows of TRAINING problems
# only, never the held-out ones (docs/EVAL_PROTOCOL.md section 5). A passing repair shows *a*
# fix, not the cause, so no rule is certain. `repair`: the repair-first rule, 102 of 115
# (see the comment above `_REPAIR_FIX_ALL_FEATURES`).
RULE_STAGE_PRECISION: dict[str, tuple[int, int]] = {
    "repair": (102, 115),
}


def wilson_lower(correct: int, total: int, z: float = 1.96) -> float:
    """Lower end of the Wilson score interval for a proportion (95% by default)."""
    if total <= 0:
        return 0.0
    p = correct / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre - spread) / (1 + z * z / total)


def rule_confidence(source: str) -> float:
    """The confidence a rule stage reports: the lower 95% Wilson bound of its measured precision.

    The lower bound, not the ratio, so that a rule seen right 2 times in 2 does not report 1.0.
    """
    if source not in RULE_STAGE_PRECISION:
        raise KeyError(f"no measured precision for decision source {source!r}")
    return round(wilson_lower(*RULE_STAGE_PRECISION[source]), 3)


def decided_by_rule(pred: "ModelPrediction", label: str, source: str) -> "ModelPrediction":
    """`pred` with its label replaced by a rule stage's decision.

    The classifier's own answer is kept in `classifier_label`, `classifier_probability` and
    `classifier_abstained`, and `top_k` / `probabilities` stay the classifier's, so a reader can
    always tell the decision from what the classifier thought.
    """
    if source == "model":
        raise ValueError("a rule decision needs a rule source, not 'model'")
    return replace(
        pred,
        top_label=label,
        top_probability=rule_confidence(source),
        abstained=False,
        decision_source=source,
    )


# Share of the classifier's features that may be missing before its decision abstains.
MAX_MISSING_SHARE = 0.25


def too_many_missing(pred: "ModelPrediction") -> bool:
    """The classifier abstains when too many of its features are missing.

    Only a classifier decision is affected: a rule decision reads its own evidence (a repair that
    passes every test), not the classifier's feature vector.
    """
    return (pred.decision_source == "model" and bool(pred.n_features)
            and pred.n_missing / pred.n_features > MAX_MISSING_SHARE and not pred.abstained)


def runtime_decision(clf: "ModelClassifier", features: Mapping[str, Any],
                     run_record: Mapping[str, Any] | None = None) -> "ModelPrediction":
    """What the served system decides for one feature mapping, in serving order.

    1. The classifier runs, so its own answer and top-k are always kept.
    2. Repair-first: exactly one class's repair passes every test, and that class decides
       (`decided_by_rule`, at its measured precision).
    3. Otherwise the classifier decides, and abstains when too many of its features are missing.

    The backend (`model_runner.predict_source`) and the held-out evaluation
    (`scripts/eval_heldout_rows.py`) both call this function, so the evaluation scores what is
    served and cannot drift from it (docs/EVAL_PROTOCOL.md section 2). `run_record` is accepted
    for rule stages that read the run record directly; none on this branch does.
    """
    pred = clf.predict(features)
    override = repair_override(features)
    if override is not None:
        return decided_by_rule(pred, override, "repair")
    if too_many_missing(pred):
        return replace(pred, abstained=True)
    return pred


class ModelContractError(RuntimeError):
    """The model artifacts are missing, inconsistent, or not loadable."""


@dataclass(frozen=True)
class ModelPrediction:
    """One decision. `top_label`, `top_probability` and `abstained` are the DECISION, made by the
    stage named in `decision_source`. The `classifier_*` fields, `top_k` and `probabilities` are
    always the classifier's own output, whichever stage decided."""

    variant: str
    model_sha256: str
    top_label: str
    top_probability: float
    abstained: bool
    threshold: float
    temperature: float
    probabilities: dict[str, float]
    top_k: tuple[tuple[str, float], ...]
    n_features: int
    n_missing: int
    ruled_out: tuple[tuple[str, str], ...] = ()
    decision_source: str = "model"
    classifier_label: str | None = None
    classifier_probability: float | None = None
    classifier_abstained: bool | None = None

    def __post_init__(self) -> None:
        if self.decision_source not in DECISION_SOURCES:
            raise ValueError(f"unknown decision_source {self.decision_source!r}")
        # A prediction built straight from the classifier: its decision IS the classifier's answer.
        if self.classifier_label is None:
            object.__setattr__(self, "classifier_label", self.top_label)
            object.__setattr__(self, "classifier_probability", self.top_probability)
            object.__setattr__(self, "classifier_abstained", self.abstained)

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "model_sha256": self.model_sha256,
            "decision_source": self.decision_source,
            "top_label": self.top_label,
            "top_probability": self.top_probability,
            "abstained": self.abstained,
            "classifier_label": self.classifier_label,
            "classifier_probability": self.classifier_probability,
            "classifier_abstained": self.classifier_abstained,
            "threshold": self.threshold,
            "temperature": self.temperature,
            "probabilities": self.probabilities,
            "top_k": [{"label": label, "p": p} for label, p in self.top_k],
            "n_features": self.n_features,
            "n_missing": self.n_missing,
            "ruled_out": [{"label": label, "reason": reason} for label, reason in self.ruled_out],
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ModelPrediction":
        """Rebuild a prediction from `as_dict()` output, e.g. the stored evidence `details`.

        Records written before `decision_source` existed read as classifier decisions.
        """
        return cls(
            variant=str(d["variant"]),
            model_sha256=str(d["model_sha256"]),
            top_label=str(d["top_label"]),
            top_probability=float(d["top_probability"]),
            abstained=bool(d["abstained"]),
            threshold=float(d["threshold"]),
            temperature=float(d["temperature"]),
            probabilities={str(k): float(v) for k, v in (d.get("probabilities") or {}).items()},
            top_k=tuple((str(x["label"]), float(x["p"])) for x in d.get("top_k") or ()),
            n_features=int(d.get("n_features") or 0),
            n_missing=int(d.get("n_missing") or 0),
            ruled_out=tuple((str(x["label"]), str(x["reason"])) for x in d.get("ruled_out") or ()),
            decision_source=str(d.get("decision_source") or "model"),
            classifier_label=d.get("classifier_label"),
            classifier_probability=d.get("classifier_probability"),
            classifier_abstained=d.get("classifier_abstained"),
        )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ModelContractError(f"cannot read {path.name}: {exc}") from exc


def _as_float(value: Any) -> float:
    if value is None:
        return math.nan
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def rescale(probs: np.ndarray, temperature: float) -> np.ndarray:
    """Temperature scaling; identical to `_rescale` in the trainer."""
    logp = np.log(np.clip(probs, 1e-12, 1.0)) / temperature
    ex = np.exp(logp - logp.max(axis=1, keepdims=True))
    return ex / ex.sum(axis=1, keepdims=True)


class ModelClassifier:
    """One loaded model variant. Build it with `ModelClassifier.load`."""

    def __init__(
        self,
        *,
        variant: str,
        booster: Any,
        features: list[str],
        classes: list[str],
        temperature: float,
        threshold: float,
        model_sha256: str,
    ) -> None:
        self.variant = variant
        self._booster = booster
        self.features = features
        self.classes = classes
        self.temperature = temperature
        self.threshold = threshold
        self.model_sha256 = model_sha256

    @classmethod
    def load(cls, variant: str = "best", models_dir: Path | str | None = None) -> "ModelClassifier":
        if variant not in VARIANT_FILES:
            raise ModelContractError(f"unknown variant {variant!r}; expected one of {sorted(VARIANT_FILES)}")
        directory = Path(models_dir) if models_dir else DEFAULT_MODELS_DIR
        model_path = directory / VARIANT_FILES[variant]
        if not model_path.is_file():
            raise ModelContractError(f"model file missing: {model_path}")

        encoder = _read_json(directory / "label_encoder.json")
        classes = list(encoder.get("idx_to_class") or [])
        class_to_idx = encoder.get("class_to_idx") or {}
        if not classes or len(set(classes)) != len(classes):
            raise ModelContractError("label_encoder.json has no classes or duplicate classes")
        if any(class_to_idx.get(name) != idx for idx, name in enumerate(classes)):
            raise ModelContractError("label_encoder.json: class_to_idx disagrees with idx_to_class")

        calibrator = _read_json(directory / "calibrator.json")
        # Served variants carry their own out-of-fold calibration; the top-level
        # values are the legacy dev-gold fit used by the variants without one.
        calibrator = (calibrator.get("variants") or {}).get(variant) or calibrator
        temperature = float(calibrator.get("temperature", 1.0))
        threshold = float(calibrator.get("threshold", 0.5))
        if not temperature > 0 or not 0 < threshold <= 1:
            raise ModelContractError(f"calibrator out of range: temperature={temperature}, threshold={threshold}")

        metrics = _read_json(directory / "metrics_v1.json")
        features = list((metrics.get(variant) or {}).get("features") or [])
        if not features or len(set(features)) != len(features):
            raise ModelContractError(f"metrics_v1.json has no usable feature list for variant {variant!r}")
        unknown = sorted(set(features) - set(schema_feature_names()))
        if unknown:
            raise ModelContractError(
                f"model was trained on features absent from the current schema: {unknown[:5]}"
            )
        if list(metrics.get("classes") or classes) != classes:
            raise ModelContractError("metrics_v1.json classes disagree with label_encoder.json")

        try:
            import xgboost as xgb
        except ImportError as exc:  # pragma: no cover - dependency is pinned in requirements.txt
            raise ModelContractError("xgboost is not installed") from exc
        booster = xgb.Booster()
        try:
            booster.load_model(str(model_path))
        except Exception as exc:  # xgboost raises its own XGBoostError
            raise ModelContractError(f"cannot load {model_path.name}: {exc}") from exc
        booster.set_param({"nthread": 1})   # bit-deterministic across machines
        if booster.num_features() != len(features):
            raise ModelContractError(
                f"booster expects {booster.num_features()} features, metrics list {len(features)}"
            )

        sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
        model = cls(
            variant=variant, booster=booster, features=features, classes=classes,
            temperature=temperature, threshold=threshold, model_sha256=sha,
        )
        # Probe with an all-NaN row: proves the output width matches the class
        # list before the first real request does.
        model._raw(np.full((1, len(features)), np.nan, dtype=np.float32))
        return model

    def _raw(self, matrix: np.ndarray) -> np.ndarray:
        import xgboost as xgb

        out = self._booster.predict(xgb.DMatrix(matrix, missing=np.nan))
        out = np.asarray(out, dtype=float).reshape(len(matrix), -1)
        if out.shape[1] != len(self.classes):
            raise ModelContractError(
                f"model returned {out.shape[1]} classes, label encoder has {len(self.classes)}"
            )
        return out

    def vector(self, features: Mapping[str, Any]) -> tuple[np.ndarray, int]:
        """Feature mapping -> (1 x n float32 row in model order, missing count)."""
        row = np.empty((1, len(self.features)), dtype=np.float32)
        missing = 0
        for i, name in enumerate(self.features):
            value = _as_float(features.get(name))
            if math.isnan(value):
                missing += 1
            row[0, i] = value
        return row, missing

    def predict(self, features: Mapping[str, Any], apply_applicability: bool = True) -> ModelPrediction:
        """Calibrated prediction for one feature mapping.

        With `apply_applicability`, classes whose required construct is absent from
        the program (`applicability.py`) get probability 0 and that mass moves to
        OTHER_ERROR before the abstain decision. The rules read the mapping the
        caller passes, which may hold more features than this variant uses.
        """
        row, missing = self.vector(features)
        scaled = rescale(self._raw(row), self.temperature)[0]
        out_rules: dict[str, str] = {}
        if apply_applicability:
            numeric = {k: _as_float(v) for k, v in features.items()}
            out_rules = ruled_out({k: (None if math.isnan(v) else v) for k, v in numeric.items()})
            scaled = move_ruled_out_mass(scaled, self.classes, out_rules)
        order = np.argsort(-scaled, kind="stable")
        top = int(order[0])
        top_p = float(scaled[top])
        probabilities = {name: round(float(scaled[i]), 6) for i, name in enumerate(self.classes)}
        return ModelPrediction(
            variant=self.variant,
            model_sha256=self.model_sha256,
            top_label=self.classes[top],
            top_probability=round(top_p, 6),
            abstained=top_p < self.threshold,
            threshold=self.threshold,
            temperature=self.temperature,
            probabilities=probabilities,
            top_k=tuple((self.classes[int(i)], round(float(scaled[i]), 6)) for i in order[:TOP_K]),
            n_features=len(self.features),
            n_missing=missing,
            ruled_out=tuple(sorted(out_rules.items())),
        )
