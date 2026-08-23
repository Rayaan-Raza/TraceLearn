"""Holdout ground truth — not imported by diagnosis modules."""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_LABELS_PATH = Path("data/annotations/ground_truth.json")


class GroundTruthRepository:
    """Loads misconception labels for evaluation only."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_LABELS_PATH
        self._by_submission: dict[str, list[str]] = {}
        if self._path.is_file():
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for row in raw.get("submissions", []):
                sid = str(row["submission_id"])
                self._by_submission[sid] = list(row.get("misconception_ids", []))

    def get_misconceptions(self, submission_id: int | str) -> list[str]:
        return list(self._by_submission.get(str(submission_id), []))

    def has_label(self, submission_id: int | str) -> bool:
        return str(submission_id) in self._by_submission
