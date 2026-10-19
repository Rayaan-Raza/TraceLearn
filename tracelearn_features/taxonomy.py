"""Taxonomy `tl-cpp-v2` — 10 misconception classes + OTHER_ERROR (§3).

Single source of truth for label identity, families and the hard-3 grouping.
Class *merges* are not decided here: they execute as a `label_mapping.csv`
join after G3 (§3.2 rule 6), never by editing this module.
"""

from __future__ import annotations

TAXONOMY_VERSION = "tl-cpp-v2"

NO_MISCONCEPTION = "NO_MISCONCEPTION"

# §3.1, in numeric order. NO_MISCONCEPTION is intentionally absent: it is a
# deterministic pre-branch, never modeled (§1, §3.1 fixed decisions).
MODELED_LABELS: tuple[str, ...] = (
    "CPP_LOOP_BOUNDARY",
    "CPP_OFF_BY_ONE",
    "CPP_ARRAY_BOUNDS",
    "CPP_UNINITIALIZED_VAR",
    "CPP_INT_OVERFLOW",
    "CPP_MISSING_BASE_CASE",
    "CPP_ASSIGN_VS_COMPARE",
    "CPP_WRONG_LOOP_DIR",
    "CPP_RANGE_CHECK",
    "CPP_STALE_EXIT",
    "CPP_OTHER_ERROR",
)

# §3.1 families: Boundary(1,2,3) ControlFlow(6,8,10) Data(4,5) Logic(7,9) Other(11)
FAMILY_OF: dict[str, str] = {
    "CPP_LOOP_BOUNDARY": "Boundary",
    "CPP_OFF_BY_ONE": "Boundary",
    "CPP_ARRAY_BOUNDS": "Boundary",
    "CPP_UNINITIALIZED_VAR": "Data",
    "CPP_INT_OVERFLOW": "Data",
    "CPP_MISSING_BASE_CASE": "ControlFlow",
    "CPP_WRONG_LOOP_DIR": "ControlFlow",
    "CPP_STALE_EXIT": "ControlFlow",
    "CPP_ASSIGN_VS_COMPARE": "Logic",
    "CPP_RANGE_CHECK": "Logic",
    "CPP_OTHER_ERROR": "Other",
}

# "Hard-3" (§3.1) — used everywhere; gets the deep review budget (§13.4).
HARD_3: tuple[str, ...] = (
    "CPP_WRONG_LOOP_DIR",
    "CPP_RANGE_CHECK",
    "CPP_STALE_EXIT",
)

LABEL_SOURCES: tuple[str, ...] = (
    "synthetic",
    "weak_rule",
    "human",
    "repair_verified",
)


def is_modeled(label: str) -> bool:
    """True only for the 11 labels the classifier predicts."""
    return label in MODELED_LABELS


def family_of(label: str) -> str:
    return FAMILY_OF[label]
