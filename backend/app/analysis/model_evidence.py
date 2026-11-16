"""Turn a classifier prediction into one evidence record.

The model is one more evidence source, not a replacement for the rules
(blueprint §9.1: XGBoost answers "what does the current submission suggest";
the learner model decides what that means over time). Writing it as an
`EvidenceRecord` keeps provenance in the same table, lets the rule engine stay
the fallback, and makes "rules, model, or both" a configuration switch.

Three outcomes, each with a distinct evidence code so a teacher can tell them
apart:

- `MODEL_PREDICTION`: a confident, mappable label. Support for that
  misconception, weighted by the calibrated probability.
- `MODEL_ABSTAINED`: the best probability is under the global threshold.
  Neutral and weightless, so the rules decide.
- `MODEL_OTHER_ERROR`: confident `CPP_OTHER_ERROR`. Neutral and weightless:
  it says "none of the modelled beliefs fits", which is not evidence for any
  one belief.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.config import settings
from backend.app.db.models import EvidenceItem, EvidenceSourceType
from backend.app.diagnosis.cpp_mapping import backend_code_for_model_label
from backend.app.diagnosis.xgb_classifier import ModelPrediction

log = logging.getLogger(__name__)


def stored_model_prediction(db: Session, submission_id: int) -> ModelPrediction | None:
    """The named model prediction stored for a submission, or None.

    Reads what the analysis stored (inline or on the background worker) instead of predicting
    again, so the hint follows the diagnosis that was actually made. Only `MODEL_PREDICTION`
    counts: shadow, abstained and OTHER_ERROR records name no misconception and must never
    change a hint.
    """
    item = (
        db.query(EvidenceItem)
        .filter(
            EvidenceItem.submission_id == submission_id,
            EvidenceItem.source_type == EvidenceSourceType.MODEL,
            EvidenceItem.evidence_code == "MODEL_PREDICTION",
        )
        .order_by(EvidenceItem.id.desc())
        .first()
    )
    if item is None:
        return None
    try:
        return ModelPrediction.from_dict(json.loads(item.details_json or "{}"))
    except (KeyError, TypeError, ValueError):
        log.warning("stored model prediction for submission %s is unreadable; hint ignores it", submission_id)
        return None


def model_evidence(prediction: ModelPrediction, max_weight: float | None = None) -> EvidenceRecord:
    ceiling = settings.model_evidence_weight if max_weight is None else max_weight
    details = prediction.as_dict()
    if prediction.abstained:
        return EvidenceRecord(
            source_type="model", evidence_code="MODEL_ABSTAINED", direction="neutral", weight=0.0,
            description=(
                f"The classifier was not sure (best {prediction.top_label} at "
                f"{prediction.top_probability:.2f}, threshold {prediction.threshold:.2f})."
            ),
            details=details,
        )
    code = backend_code_for_model_label(prediction.top_label)
    if code is None:
        return EvidenceRecord(
            source_type="model", evidence_code="MODEL_OTHER_ERROR", direction="neutral", weight=0.0,
            description="The classifier found a failure that fits none of the modelled misconceptions.",
            details=details,
        )
    return EvidenceRecord(
        source_type="model", evidence_code="MODEL_PREDICTION", direction="support",
        weight=round(prediction.top_probability * ceiling, 4),
        description=(
            f"The classifier ({prediction.variant}) supports {code} "
            f"at probability {prediction.top_probability:.2f}."
        ),
        misconception_id=code,
        details=details,
    )
