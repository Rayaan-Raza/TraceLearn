from __future__ import annotations
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

def compute_classification_metrics(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict:
    if not y_true:
        return {"accuracy": 0.0, "macro_precision": 0.0, "macro_recall": 0.0, "macro_f1": 0.0, "confusion_matrix": []}
    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
    macro_p = precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    macro_r = recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    macro_f1 = f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    return {
        "accuracy": accuracy,
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "confusion_matrix": cm.tolist(),
        "labels": labels,
    }
