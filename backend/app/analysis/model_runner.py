"""Run the trained misconception classifier on one submission and return evidence.

Safety rules (this is the path a student's code takes into a diagnosis):

- `settings.model_diagnosis == "off"`: nothing is loaded, nothing runs.
- Any failure (missing files, a contract error, a feature error, an oversized
  source) returns no evidence and logs; it never raises into the pipeline, so the rule
  engine always still produces a diagnosis.
- `shadow`: the prediction is stored as neutral, weightless evidence
  (`MODEL_SHADOW`) so it can be audited against teacher decisions; the diagnosis
  does not change.
- `on`: the prediction becomes `MODEL_PREDICTION` / `MODEL_ABSTAINED` /
  `MODEL_OTHER_ERROR` (see `model_evidence`). If too many features are missing
  (the backend does not yet supply compiler-warning counts, which the training
  data had for almost every row) the prediction is forced to abstain, because a
  model fed inputs it was not trained on is not trustworthy.
"""
from __future__ import annotations

import dataclasses
import logging
import math
from functools import lru_cache
from typing import Any

from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.analysis.model_evidence import model_evidence
from backend.app.config import settings
from backend.app.diagnosis.xgb_classifier import ModelClassifier, ModelPrediction

log = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 20_000
# Share of the model's features that may be missing before "on" abstains.
MAX_MISSING_SHARE = 0.25


@lru_cache(maxsize=2)
def _classifier(variant: str, models_dir: str) -> ModelClassifier:
    return ModelClassifier.load(variant, models_dir)


def code_features(source: str, language: str = "cpp", warnings: dict[str, Any] | None = None) -> dict[str, float | None]:
    """Feature mapping ("block.name" -> number) built from the submission's own code.

    Static and semantic features come from the source. Compiler-warning counts
    are used when the caller has them; otherwise the whole warnings block is absent.
    """
    from tracelearn_features.normalize import normalize_row
    from tracelearn_features.schema import feature_names

    row = {"dataset_source": "CODESTREAM", "language": language, "warnings": warnings}
    normalized = normalize_row(row, code=source)
    out: dict[str, float | None] = {}
    for name in feature_names():
        block, _, short = name.partition(".")
        value = (normalized.get(block) or {}).get(short)
        if isinstance(value, bool):
            value = float(value)
        out[name] = value if isinstance(value, (int, float)) and math.isfinite(value) else None
    return out


def predict_source(source: str, language: str = "cpp", warnings: dict[str, Any] | None = None) -> ModelPrediction | None:
    if len(source) > MAX_SOURCE_CHARS or not source.strip():
        return None
    clf = _classifier(settings.model_variant, str(settings.model_dir))
    return clf.predict(code_features(source, language, warnings))


def model_records(source: str, language: str = "cpp", warnings: dict[str, Any] | None = None) -> list[EvidenceRecord]:
    """Zero or one evidence record for this submission, according to `model_diagnosis`."""
    mode = settings.model_diagnosis
    if mode == "off":
        return []
    try:
        pred = predict_source(source, language, warnings)
        if pred is None:
            return []
        if mode == "shadow":
            return [EvidenceRecord(
                source_type="model", evidence_code="MODEL_SHADOW", direction="neutral", weight=0.0,
                description=(f"Shadow mode: the classifier would say {pred.top_label} "
                             f"at {pred.top_probability:.2f}{' (abstained)' if pred.abstained else ''}; not used."),
                details=pred.as_dict())]
        if pred.n_features and pred.n_missing / pred.n_features > MAX_MISSING_SHARE and not pred.abstained:
            pred = dataclasses.replace(pred, abstained=True)
        return [model_evidence(pred)]
    except Exception:  # the rules must still diagnose
        log.exception("model diagnosis failed; continuing with rules only")
        return []
