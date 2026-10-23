from __future__ import annotations
from backend.app.diagnosis.taxonomy import ALL_LABELS
from backend.app.evaluation.metrics import compute_classification_metrics

def compare_modes(current_preds: list[str], history_preds: list[str], labels: list[str]) -> dict:
    changed = sum(1 for a, b in zip(current_preds, history_preds) if a != b)
    return {
        "history_changed_predictions": changed,
        "current_only_metrics": compute_classification_metrics(labels, current_preds, ALL_LABELS),
        "history_aware_metrics": compute_classification_metrics(labels, history_preds, ALL_LABELS),
    }
