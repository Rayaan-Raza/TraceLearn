"""Map the C++ diagnostic bank's vocabulary onto the backend taxonomy.

Two vocabularies meet here.

1. The data and the docs use the bank codes `CPP-M01` to `CPP-M08`. Every
   problem, hint, and diagnostic test in `data/cpp_diagnostics` is written in
   that vocabulary.
2. The backend, the frontend labels, and the teacher correction list use the
   `CPP_*` codes in `backend.app.diagnosis.taxonomy`.

Nothing else translates between them, so before this module existed a C++
evidence record was dropped by `rules.aggregate_scores`, never reached
`learner_model.updater`, and could not select a hint. This module is the one
place that knows both vocabularies.

Rules:

1. Every code in the bank must map. `backend/tests/test_cpp_end_to_end.py`
   reads the bank at run time and fails when a tag or a misconception has no
   entry, so a new bank tag cannot fail silently again.
2. A mapping states its meaning. The four exact rows are listed first; the
   rest document why two beliefs share one backend code.
3. The tables are data, not logic. `code_for_diagnostic_tag` is the only
   function callers need.
"""
from __future__ import annotations

from backend.app.diagnosis.taxonomy import (
    CPP_ARRAY_BOUNDS,
    CPP_ASSIGN_VS_COMPARE,
    CPP_LOOP_BOUNDARY,
    CPP_MISSING_BASE_CASE,
    CPP_RANGE_CHECK,
    CPP_STALE_EXIT,
    M01_LOOP_BOUNDARY,
    M02_INDEX_VALUE,
    M03_MISSING_RETURN,
)

# Bank misconception -> backend misconception.
#
# Exact rows:
#   CPP-M01 exclusive upper bound treated as inclusive -> CPP_LOOP_BOUNDARY
#   CPP-M04 index equal to size()                      -> CPP_ARRAY_BOUNDS
#   CPP-M06 assignment used where a comparison belongs -> CPP_ASSIGN_VS_COMPARE
#   CPP-M07 recursion without progress                 -> CPP_MISSING_BASE_CASE
#
# Shared rows. The belief is the same in Python and C++, so it keeps the
# language-neutral backend code and the learner model can see a cross-language
# pattern:
#   CPP-M02 reports a value where the position belongs -> M02_INDEX_VALUE
#   CPP-M03 prints instead of returning                 -> M03_MISSING_RETURN
#
# New rows. No backend code described these beliefs, so the taxonomy gained
# one instead of overloading a near neighbour:
#   CPP-M05 range check written as a chained comparison -> CPP_RANGE_CHECK
#   CPP-M08 loop never updates its exit condition       -> CPP_STALE_EXIT
BANK_TO_BACKEND: dict[str, str] = {
    "CPP-M01": CPP_LOOP_BOUNDARY,
    "CPP-M02": M02_INDEX_VALUE,
    "CPP-M03": M03_MISSING_RETURN,
    "CPP-M04": CPP_ARRAY_BOUNDS,
    "CPP-M05": CPP_RANGE_CHECK,
    "CPP-M06": CPP_ASSIGN_VS_COMPARE,
    "CPP-M07": CPP_MISSING_BASE_CASE,
    "CPP-M08": CPP_STALE_EXIT,
}

# Backend misconception -> every bank code that maps to it. Used to find the
# bank vocabulary again, for example when a hint row is stored under `CPP-M05`
# but the diagnosis holds `CPP_RANGE_CHECK`.
BACKEND_TO_BANK: dict[str, list[str]] = {}
for _bank_code, _backend_code in BANK_TO_BACKEND.items():
    BACKEND_TO_BANK.setdefault(_backend_code, []).append(_bank_code)


# Diagnostic tag -> backend misconception, per problem language.
#
# The banks share tag names with different targets: `upper_boundary` is a
# Python M01 test in `data/problems` and a C++ M01 test in the carried-over
# problems of the C++ bank. The tag alone is ambiguous, so the lookup takes
# the problem language.
TAG_TO_CODE: dict[str, dict[str, str]] = {
    "python": {
        # Emitted by the six dataset problems in `data/problems`.
        "upper_boundary": M01_LOOP_BOUNDARY,
        "empty_list": M02_INDEX_VALUE,
        "index_value": M02_INDEX_VALUE,
        # Held by older rows and by `test_analyzer` before this module.
        "index_vs_value": M02_INDEX_VALUE,
        "return_value": M03_MISSING_RETURN,
    },
    "cpp": {
        # CPP-M01 exclusive upper bound
        "inclusive_upper_bound": CPP_LOOP_BOUNDARY,
        "upper_boundary": CPP_LOOP_BOUNDARY,
        # CPP-M02 value reported where a position belongs
        "duplicate_values": M02_INDEX_VALUE,
        "value_not_index": M02_INDEX_VALUE,
        "value_not_position": M02_INDEX_VALUE,
        # CPP-M03 print in place of return
        "print_in_place_of_return": M03_MISSING_RETURN,
        "return_channel": M03_MISSING_RETURN,
        # CPP-M04 index equal to size()
        "index_equal_to_size": CPP_ARRAY_BOUNDS,
        "last_valid_index": CPP_ARRAY_BOUNDS,
        "size_one": CPP_ARRAY_BOUNDS,
        "size_zero": CPP_ARRAY_BOUNDS,
        # CPP-M05 range check as a chained comparison
        "above_range": CPP_RANGE_CHECK,
        "below_range": CPP_RANGE_CHECK,
        "chained_comparison": CPP_RANGE_CHECK,
        "lower_bound": CPP_RANGE_CHECK,
        "upper_bound": CPP_RANGE_CHECK,
        # CPP-M06 assignment inside a condition
        "assignment_in_condition": CPP_ASSIGN_VS_COMPARE,
        "nonzero_input": CPP_ASSIGN_VS_COMPARE,
        "zero_input": CPP_ASSIGN_VS_COMPARE,
        # CPP-M07 recursion without progress
        "base_case": CPP_MISSING_BASE_CASE,
        "no_progress": CPP_MISSING_BASE_CASE,
        "one_step": CPP_MISSING_BASE_CASE,
        "several_steps": CPP_MISSING_BASE_CASE,
        # CPP-M08 exit condition never updated
        "absent_target": CPP_STALE_EXIT,
        "exit_condition_not_updated": CPP_STALE_EXIT,
        "immediate_find": CPP_STALE_EXIT,
        "last_index": CPP_STALE_EXIT,
        "sentinel_not_detected": CPP_STALE_EXIT,
    },
}


def code_for_diagnostic_tag(language: str | None, tag: str | None) -> str | None:
    """Return the backend misconception a failing diagnostic test supports."""
    if not tag:
        return None
    return TAG_TO_CODE.get(language or "python", {}).get(tag)


def hint_misconception_ids(code: str) -> list[str]:
    """Return every misconception id a hint row may be stored under.

    A diagnosis holds a backend code. The bank stores its problem hints under
    the bank code, for example `CPP-M05` for `CPP_RANGE_CHECK`. Both spellings
    have to reach the query, and the Python codes appear in the list as well
    because two of them are shared with the bank.
    """
    candidates = [code]
    for bank_code in BACKEND_TO_BANK.get(code, []):
        if bank_code not in candidates:
            candidates.append(bank_code)
    return candidates
