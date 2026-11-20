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


# Narrow second-set repairs: the few `scripts/repair_extra.py` edits that were precise on the
# training problems (2026-11-14 audit: enlarge_every_array 16/18, output_+-1_added 17/21,
# chained_compare_split_all 2/2, while_add_update 1/1). The rest of that set also passes every
# test on unrelated bugs and stays unused. The worker measures them as `cf_narrow`.
NARROW_REPAIR_OPS: dict[str, tuple[str, ...]] = {
    "CPP_ARRAY_BOUNDS": ("enlarge_every_array",),
    "CPP_OFF_BY_ONE": ("output_-1_added", "output_+1_added"),
    "CPP_RANGE_CHECK": ("chained_compare_split_all", "range_test_swap_and_or"),
    "CPP_STALE_EXIT": ("while_add_update", "for_add_missing_step"),
    "CPP_WRONG_LOOP_DIR": ("for_run_downward",),
}


def narrow_repair_override(run_record: Mapping[str, Any] | None, skip: tuple[str, ...] = ()) -> str | None:
    """The unique class whose narrow second-set repair passes every test, or None.

    Reads the run record's `cf_narrow` block (same shape as `cf_extra`). Used only after
    `repair_override` found nothing, so a first-set proof always wins.
    """
    classes = ((run_record or {}).get("cf_narrow") or {}).get("classes") or {}
    hits = [
        cls
        for cls, rec in classes.items()
        if cls not in skip and isinstance(rec, Mapping) and rec.get("fix_all") and rec.get("ops")
        and rec["ops"][-1] in NARROW_REPAIR_OPS.get(cls, ())
    ]
    return hits[0] if len(hits) == 1 else None


OTHER_LABEL = "CPP_OTHER_ERROR"
MISSING_BASE_CASE = "CPP_MISSING_BASE_CASE"
WRONG_LOOP_DIR = "CPP_WRONG_LOOP_DIR"


def evidence_rule_override(features: Mapping[str, Any]) -> str | None:
    """Rules for the two classes real code almost never shows, so no model can be trained or
    tested on them (3 real rows in 2,600; none in the held-out problems).

    MISSING_BASE_CASE
      - the compiler's own `-Winfinite-recursion` warning: 43 of 43 right on dataset rows, 6 of 6
        on the bank benchmark, never raised on a program of another class; or
      - the base-case repair passes every test AND the program recurses AND the first failing test
        crashed or timed out: 17 of 19 and 7 of 7. Without the crash or timeout the same repair
        was right on 4 of 14 (it also "fixes" wrong range tests), so it does not count alone.
    WRONG_LOOP_DIR
      - the loop-direction repair passes every test, also when another class's repair does:
        66 of 67 and 21 of 21.

    The rules were written from the class definitions (ANNOTATION_GUIDELINE section 3) and then
    counted on every labelled row and the bank benchmark, 2026-11-15; nothing was fitted. Almost
    all of that evidence is synthetic, which is the point: it is the only evidence there is.
    """
    def at_least_one(name: str) -> bool:
        value = _as_float(features.get(name))
        return not math.isnan(value) and value >= 1

    if at_least_one("warnings.infinite_recursion"):
        return MISSING_BASE_CASE
    stopped = at_least_one("evidence.ff_crash") or at_least_one("evidence.ff_timeout")
    if _as_float(features.get("repair.missing_base_case_fix_all")) == 1.0 and at_least_one("semantics.recursion") and stopped:
        return MISSING_BASE_CASE
    if _as_float(features.get("repair.wrong_loop_dir_fix_all")) == 1.0:
        return WRONG_LOOP_DIR
    return None


def rule_override(features: Mapping[str, Any], run_record: Mapping[str, Any] | None = None) -> str | None:
    """Every rule stage, in order; None hands the submission to the model.

    1. `evidence_rule_override`: MISSING_BASE_CASE and WRONG_LOOP_DIR.
    2. `repair_override`: exactly one class's first-set repair passes every test. A lone
       base-case repair is not accepted here: stage 1 already took the supported ones.
    3. `narrow_repair_override`: one of the few precise second-set repairs does. Turning an
       upward loop downward (`for_run_downward`) counts only when the first failing test printed
       the expected output in reverse: on 2,233 real failing programs that edit passed every
       test on up to 40, none of them WRONG_LOOP_DIR, and none of the 40 printed a reversed output.
    """
    hit = evidence_rule_override(features)
    if hit:
        return hit
    hit = repair_override(features)
    if hit == MISSING_BASE_CASE:
        hit = None
    if hit:
        return hit
    reversed_output = any(
        not math.isnan(v) and v >= 1
        for v in (_as_float(features.get("evidence.reversed_tokens")), _as_float(features.get("evidence.reversed_lines"))))
    return narrow_repair_override(run_record, skip=() if reversed_output else (WRONG_LOOP_DIR,))


def decide(probs: Any, classes: list[str], threshold: float,
           class_thresholds: Mapping[str, float] | None = None) -> tuple[int, bool]:
    """(index of the label to report, abstained) for one calibrated probability row.

    Without `class_thresholds` this is the old rule: the most probable class, abstaining
    below `threshold`. A class with its own bar uses that bar instead of `threshold`, and
    when the most probable class is OTHER_ERROR (or falls short of its bar) the most
    probable class that clears its own bar is reported instead. That is what lifts a
    misconception out of the OTHER_ERROR majority. Bars come from
    `scripts/tune_class_thresholds.py` (grouped out-of-fold, training problems only).
    """
    bars = class_thresholds or {}
    top = int(np.argmax(probs))
    name = classes[top]
    if name != OTHER_LABEL and probs[top] >= bars.get(name, threshold):
        return top, False
    cleared = [(float(probs[i]), -i) for i, c in enumerate(classes)
               if c != OTHER_LABEL and c in bars and probs[i] >= bars[c]]
    if cleared:
        return -max(cleared)[1], False
    return top, bool(name != OTHER_LABEL or probs[top] < threshold)


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
        class_thresholds: Mapping[str, float] | None = None,
    ) -> None:
        self.variant = variant
        self._booster = booster
        self.features = features
        self.classes = classes
        self.temperature = temperature
        self.threshold = threshold
        self.class_thresholds = dict(class_thresholds or {})
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
        class_thresholds = {str(k): float(v) for k, v in (calibrator.get("class_thresholds") or {}).items()}
        bad = sorted(k for k, v in class_thresholds.items() if k not in classes or k == OTHER_LABEL or not 0 < v <= 1)
        if bad:
            raise ModelContractError(f"calibrator class_thresholds invalid for: {bad[:5]}")

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
            class_thresholds=class_thresholds,
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
        top, abstained = decide(scaled, self.classes, self.threshold, self.class_thresholds)
        top_p = float(scaled[top])
        probabilities = {name: round(float(scaled[i]), 6) for i, name in enumerate(self.classes)}
        return ModelPrediction(
            variant=self.variant,
            model_sha256=self.model_sha256,
            top_label=self.classes[top],
            top_probability=round(top_p, 6),
            abstained=abstained,
            threshold=self.threshold,
            temperature=self.temperature,
            probabilities=probabilities,
            top_k=tuple((self.classes[int(i)], round(float(scaled[i]), 6)) for i in order[:TOP_K]),
            n_features=len(self.features),
            n_missing=missing,
            ruled_out=tuple(sorted(out_rules.items())),
        )
