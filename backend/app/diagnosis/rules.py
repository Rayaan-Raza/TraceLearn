from __future__ import annotations
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.diagnosis.taxonomy import ALL_MISCONCEPTIONS, NO_MISCONCEPTION, UNCERTAIN

CODE_TO_MISCONCEPTION: dict[str, str] = {}

def register(code: str, mid: str) -> None:
    CODE_TO_MISCONCEPTION[code] = mid

for mid in ALL_MISCONCEPTIONS:
    register(f"STATIC_{mid.split('_')[0]}_", mid)

STATIC_MAP = {
    "STATIC_RANGE_N_PLUS_ONE": "M01_LOOP_BOUNDARY",
    "STATIC_ITER_VALUE_USED_AS_INDEX": "M02_INDEX_VALUE",
    "STATIC_NO_RETURN": "M03_MISSING_RETURN",
    "STATIC_PRINT_INSTEAD_OF_RETURN": "M03_MISSING_RETURN",
}

def map_evidence(rec: EvidenceRecord) -> str | None:
    if rec.misconception_id:
        return rec.misconception_id
    return STATIC_MAP.get(rec.evidence_code)

def aggregate_scores(records: list[EvidenceRecord]) -> dict[str, float]:
    scores = {m: 0.0 for m in ALL_MISCONCEPTIONS}
    for rec in records:
        mid = map_evidence(rec)
        if mid and mid in scores:
            if rec.direction == "support":
                scores[mid] += rec.weight
            elif rec.direction == "conflict":
                scores[mid] -= rec.weight * 0.5
    return scores
