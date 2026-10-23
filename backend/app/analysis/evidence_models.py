from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class EvidenceRecord:
    source_type: str
    evidence_code: str
    direction: str
    weight: float
    description: str
    misconception_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
