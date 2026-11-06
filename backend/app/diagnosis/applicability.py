"""Which misconception classes are even possible for this program?

A learned classifier trained mostly on mutants of loop-heavy programs will name
a loop misconception for a program that has no loop. Real beginner failures
are often exactly that kind of program (wrong output format, wrong formula), and
dev-gold clusters of CodeStream have a median of 0 loops against 5 in the real
training rows (`reports/shift_dev_gold.md`).

This module encodes NECESSARY conditions only: a construct a misconception cannot
exist without. If the construct is absent the class is ruled out before the
abstain decision, and its probability moves to OTHER_ERROR (`move_ruled_out_mass`). A rule is
silent (the class stays possible) when the feature it needs is missing, and when
a class can occur without any simple construct (INT_OVERFLOW, UNINITIALIZED_VAR,
and OFF_BY_ONE: 7 of 16 rule-labelled CodeStream OFF_BY_ONE rows have no loop,
array or recursion, because the off-by-one sits in a formula).

These are definitions, not learned values, so they do not drift with the data.
`tests/test_applicability.py` pins that no certain training row (execution-
verified mutant or repair-verified real row) is ruled out by its own label, and
`scripts/eval_applicability.py` reports the rate for weak rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class Rule:
    label: str
    needs: str                      # construct (no article) the class cannot exist without
    possible: Callable[[Mapping[str, float | None]], bool | None]   # None = cannot tell


def _val(features: Mapping[str, float | None], name: str) -> float | None:
    value = features.get(name)
    return None if value is None else float(value)


def _any_positive(features: Mapping[str, float | None], names: tuple[str, ...]) -> bool | None:
    values = [_val(features, n) for n in names]
    if all(v is None for v in values):
        return None
    return any(v is not None and v >= 1 for v in values)


def _has_loop(f):
    return _any_positive(f, ("static.loop_count",))


def _has_array_like_or_loop(f):
    # The array detector is a regex and misses macro-sized, multi-dimensional and
    # pointer arrays (about 40% of the rule-labelled PROGPedia array rows), so a
    # loop, where indexing normally happens, keeps the class possible too.
    return _any_positive(f, ("static.array_decl_count", "static.uses_vector", "static.uses_malloc_free",
                             "semantics.idx_minus1", "semantics.idx_plus1", "static.loop_count"))


def _has_recursion(f):
    return _any_positive(f, ("semantics.recursion",))


def _has_condition(f):
    return _any_positive(f, ("static.if_count", "static.loop_count", "static.switch_count"))



RULES: tuple[Rule, ...] = (
    Rule("CPP_LOOP_BOUNDARY", "loop", _has_loop),
    Rule("CPP_WRONG_LOOP_DIR", "loop", _has_loop),
    Rule("CPP_STALE_EXIT", "loop", _has_loop),
    Rule("CPP_ARRAY_BOUNDS", "array, vector, buffer, index expression or loop", _has_array_like_or_loop),
    Rule("CPP_MISSING_BASE_CASE", "recursive call", _has_recursion),
    Rule("CPP_RANGE_CHECK", "condition (if, loop or switch)", _has_condition),
    Rule("CPP_ASSIGN_VS_COMPARE", "condition (if, loop or switch)", _has_condition),
)
RULES_BY_LABEL = {r.label: r for r in RULES}


def ruled_out(features: Mapping[str, float | None]) -> dict[str, str]:
    """Classes this program cannot exhibit, with the construct each one needs."""
    out: dict[str, str] = {}
    for rule in RULES:
        if rule.possible(features) is False:
            out[rule.label] = f"the program has no {rule.needs}"
    return out


OPEN_SET_LABEL = "CPP_OTHER_ERROR"


def move_ruled_out_mass(probs: np.ndarray, classes: Sequence[str], masked: Iterable[str]) -> np.ndarray:
    """Give the probability of impossible classes to OTHER_ERROR.

    Renormalizing over the remaining classes would make the model MORE sure of a
    different, equally unsupported class (measured on unseen CodeStream clusters:
    OFF_BY_ONE answers went from 7 to 51). When the evidence points at a
    misconception the program cannot contain, the honest reading is "something
    else is wrong", so that mass goes to the open-set label.
    """
    out = np.array(probs, dtype=float, copy=True)
    names = list(classes)
    if OPEN_SET_LABEL not in names:
        return out
    sink = names.index(OPEN_SET_LABEL)
    for label in masked:
        if label in names and label != OPEN_SET_LABEL:
            i = names.index(label)
            out[sink] += out[i]
            out[i] = 0.0
    return out
