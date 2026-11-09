"""Which evidence each diagnosis mode may read, and how stored evidence is read back.

The contract
------------

Evidence has a source type (`EvidenceSourceType`). The sources fall in two
groups:

* **Observed** sources describe the current submission only:
  `execution`, `test`, `static` and `model`. They come from running and reading
  the code of this one attempt. The trained classifier is observed evidence
  because its features are built from this submission alone (static, compiler
  warnings and source semantics; no history or label metadata).
* **Longitudinal** sources describe the student's earlier work:
  `sequence` (an earlier attempt on the same problem) and `history`
  (other problems, earlier learner states, earlier successes). `context` is
  reserved for later use and is treated as longitudinal, so that a new
  producer cannot leak into Mode A by default.

A third group, **derived**, holds `model`: the classifier's reading of the
current submission (`analysis/model_evidence.py`). It is computed *from*
observed evidence, so it is not observed evidence itself, and it is in
neither mode's allow-list until the model router (plan item B5, with the
`MODEL_DIAGNOSIS` flag) decides where it goes. The learner model never counts
it as observed support: that would count the same failure twice (once as the
rule evidence, once as the model's reading of it). Blueprint §10.4 feeds the
model's calibrated probability into the updater as `P_t` instead.

Mode A (current-only) reads **observed** sources only. It is an allow-list,
not a block-list: a source type that is not listed in `CURRENT_ONLY_SOURCES`
never reaches Mode A.

Mode B (history-aware) reads every source. All longitudinal evidence must be
built from data strictly before the current submission
(`HistoryProvider`), and every `history` record carries `details["age"]`, the
attempt distance used for decay (see `HistoryAnalyzer`).

The learner model counts **observed** support only. History and sequence
records summarise earlier attempts; counting them again as if they were
observed on the later attempt would let a misconception "recur" on a problem
where the student never showed it.

Reading stored evidence back
----------------------------

`apply_evidence_weights` re-derives each weight from the evidence code and
from `details["age"]`. The stored `details_json` must therefore come back with
the record, otherwise every history item looks like age 0 and the documented
decay never applies. `records_from_items` is the one place that rebuilds
records, and both engines use it.
"""
from __future__ import annotations

import json
from typing import Iterable

from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.db.models import EvidenceItem, EvidenceSourceType

OBSERVED_SOURCES: frozenset[EvidenceSourceType] = frozenset({
    EvidenceSourceType.EXECUTION,
    EvidenceSourceType.TEST,
    EvidenceSourceType.STATIC,
    EvidenceSourceType.MODEL,
})

LONGITUDINAL_SOURCES: frozenset[EvidenceSourceType] = frozenset({
    EvidenceSourceType.SEQUENCE,
    EvidenceSourceType.HISTORY,
    EvidenceSourceType.CONTEXT,
})

DERIVED_SOURCES: frozenset[EvidenceSourceType] = frozenset({
    EvidenceSourceType.MODEL,
})

CURRENT_ONLY_SOURCES: frozenset[EvidenceSourceType] = OBSERVED_SOURCES
HISTORY_AWARE_SOURCES: frozenset[EvidenceSourceType] = OBSERVED_SOURCES | LONGITUDINAL_SOURCES

# String forms, for code that works on `EvidenceRecord.source_type`.
OBSERVED_SOURCE_VALUES: frozenset[str] = frozenset(s.value for s in OBSERVED_SOURCES)
CURRENT_ONLY_SOURCE_VALUES: frozenset[str] = frozenset(s.value for s in CURRENT_ONLY_SOURCES)


def _details(item: EvidenceItem) -> dict:
    try:
        value = json.loads(item.details_json or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def records_from_items(items: Iterable[EvidenceItem], allowed: frozenset[EvidenceSourceType]) -> list[EvidenceRecord]:
    """Rebuild evidence records from stored rows, keeping only `allowed` sources.

    `details` is restored, so `details["age"]` reaches the decay step.
    """
    records: list[EvidenceRecord] = []
    for item in items:
        if item.source_type not in allowed:
            continue
        records.append(EvidenceRecord(
            source_type=item.source_type.value,
            evidence_code=item.evidence_code,
            misconception_id=item.misconception_id,
            direction=item.direction.value,
            weight=item.weight,
            description=item.description,
            details=_details(item),
        ))
    return records
