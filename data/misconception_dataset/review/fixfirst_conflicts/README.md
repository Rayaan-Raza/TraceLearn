# Label review: instructions for raters

140 real student programs. Fill a copy of `blind_sheet.csv` alone and save it as
`rater_<name>.csv`. Open each program at `source_code_path` in the raw copy (Datasets_RAW).

- `rater_label`: one of OFF_BY_ONE | LOOP_BOUNDARY | ARRAY_BOUNDS | INT_OVERFLOW | UNINITIALIZED_VAR | RANGE_CHECK | ASSIGN_VS_COMPARE | STALE_EXIT | MISSING_BASE_CASE | WRONG_LOOP_DIR | OTHER_ERROR | UNCERTAIN. ANNOTATION_GUIDELINE.md section 2: the misconception that **causes**
  the first failing test.
- `cause_line`: the line you would change. `note`: required for OTHER_ERROR and UNCERTAIN.
- Before submitting, do not open any other file in this folder, the labels file, the strategy
  document, the pull request that added this sheet, or model output.
