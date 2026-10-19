"""tracelearn_features — shared feature library for the misconception dataset.

v0 (Week 0, master plan §5/§6): fixed, versioned interface that lanes use to
compute their own JSONL feature blocks from day one. The interface is pinned in
`features/FEATURE_SCHEMA.md`; breaking changes are forbidden until the single
post-G3 migration window (`scripts/migrate_schema.py`).

Public surface (v0):
- `taxonomy` — the tl-cpp-v2 label set, families, hard-3.
- `schema`   — the enumerated feature registry (name -> type) and helpers.
- `extract_features(...)` — Task 3 (added next); raises NotImplementedError
  until then so no lane silently consumes a half-built extractor.
"""

from tracelearn_features import taxonomy
from tracelearn_features.schema import FEATURE_BLOCKS, SCHEMA_VERSION, feature_names

__version__ = "0.1.0"

__all__ = [
    "taxonomy",
    "FEATURE_BLOCKS",
    "SCHEMA_VERSION",
    "feature_names",
    "extract_features",
    "__version__",
]


def extract_features(*args, **kwargs):  # noqa: ANN002, ANN003 — v0 signature pinned in FEATURE_SCHEMA.md
    """Fixed v0 interface — implemented in Task 3."""
    raise NotImplementedError(
        "tracelearn_features.extract_features lands with Task 3; until then "
        "lanes ship raw-evidence blocks only (§5 fallback)."
    )
