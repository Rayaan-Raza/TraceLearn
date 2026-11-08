# Misconception Taxonomy

Three vocabularies meet in TraceLearn. This table is the single cross-reference.

| Bank code | Bank label | Model label (11-class) | Backend / taxonomy code | Frontend label |
|-----------|------------|------------------------|-------------------------|----------------|
| CPP-M01 | Exclusive upper bound treated as inclusive | `CPP_LOOP_BOUNDARY` | `CPP_LOOP_BOUNDARY` | Off-by-one loop bound |
| CPP-M02 | Reports a value where a position belongs | *(rule-only, no model label)* | `M02_INDEX_VALUE` | Index vs. value |
| CPP-M03 | Prints instead of returning | *(rule-only, no model label)* | `M03_MISSING_RETURN` | Print instead of return |
| CPP-M04 | Index equal to `size()` | `CPP_ARRAY_BOUNDS` | `CPP_ARRAY_BOUNDS` | Array bounds |
| CPP-M05 | Range check as a chained comparison | `CPP_RANGE_CHECK` | `CPP_RANGE_CHECK` | Range check |
| CPP-M06 | Assignment used where a comparison belongs | `CPP_ASSIGN_VS_COMPARE` | `CPP_ASSIGN_VS_COMPARE` | Assign vs. compare |
| CPP-M07 | Recursion without progress toward base case | `CPP_MISSING_BASE_CASE` | `CPP_MISSING_BASE_CASE` | Missing base case |
| CPP-M08 | Loop never updates its exit condition | `CPP_STALE_EXIT` | `CPP_STALE_EXIT` | Stale exit condition |
| — | *(no bank entry)* | `CPP_INT_OVERFLOW` | `CPP_INT_OVERFLOW` | Integer overflow |
| — | *(no bank entry)* | `CPP_OFF_BY_ONE` | `CPP_OFF_BY_ONE` | Off-by-one error |
| — | *(no bank entry)* | `CPP_UNINITIALIZED_VAR` | `CPP_UNINITIALIZED_VAR` | Uninitialized variable |
| — | *(no bank entry)* | `CPP_WRONG_LOOP_DIR` | `CPP_WRONG_LOOP_DIR` | Wrong loop direction |
| — | *(no bank entry)* | `CPP_OTHER_ERROR` | *(no backend mapping — open-set label)* | Other error |

## Notes

- **Bank codes** (`CPP-M01`–`CPP-M08`) are used in `data/cpp_diagnostics` problems, hints,
  and diagnostic tests. See `cpp_mapping.py:BANK_TO_BACKEND` for the authoritative mapping.
- **Model labels** are the 11 classes the XGBoost classifier (`tl-cpp-v2`) produces.
  `CPP_OTHER_ERROR` is an open-set catch-all and maps to `None` in `MODEL_LABEL_TO_BACKEND`.
- **Backend codes** are the `CPP_*` and `M0*_*` constants in `backend/app/diagnosis/taxonomy.py`.
  They drive the learner model, hint selection, and teacher-facing labels.
- `CPP-M02` and `CPP-M03` share backend codes (`M02_INDEX_VALUE`, `M03_MISSING_RETURN`) with
  the Python misconception bank — the learner model can observe cross-language patterns.
- `CPP_INT_OVERFLOW`, `CPP_OFF_BY_ONE`, `CPP_UNINITIALIZED_VAR`, and `CPP_WRONG_LOOP_DIR`
  exist as model labels but have no bank entry — they are detected by the classifier only.
