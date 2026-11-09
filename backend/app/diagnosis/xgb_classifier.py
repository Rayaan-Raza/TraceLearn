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
from dataclasses import dataclass
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


class ModelContractError(RuntimeError):
    """The model artifacts are missing, inconsistent, or not loadable."""


@dataclass(frozen=True)
class ModelPrediction:
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "model_sha256": self.model_sha256,
            "top_label": self.top_label,
            "top_probability": self.top_probability,
            "abstained": self.abstained,
            "threshold": self.threshold,
            "temperature": self.temperature,
            "probabilities": self.probabilities,
            "top_k": [{"label": label, "p": p} for label, p in self.top_k],
            "n_features": self.n_features,
            "n_missing": self.n_missing,
            "ruled_out": [{"label": label, "reason": reason} for label, reason in self.ruled_out],
        }


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
