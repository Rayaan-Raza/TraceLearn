# Dataset expansion + best-model plan (2026-10-24)

## Goal

Make the misconception classifier materially better without tuning G8 caps:

1. Fix the feature-availability report and add the two warning signals the audit found.
2. Add a source-semantics feature block computed for SYNTHETIC and CODESTREAM rows.
3. Add a `best` model variant (`static + warnings + semantics`) and repeated grouped CV.
4. Expand the synthetic dataset across under-represented problem clusters using the
   existing mutation library and verifier.
5. Regenerate `labels.jsonl`, `features.csv`, `merge_report.json`, `metrics_v1.json`
   and model artifacts, then report honest before/after metrics.

## Evidence driving the plan

Prototype on the current merged data (semantics computed for synthetic **and**
CodeStream source, 3-fold grouped CV, seed 7):

| variant | CV macro-F1 | OOF macro-F1 | test F1 (7 present) |
|---|---:|---:|---:|
| common (static+warnings) | 0.2025 | 0.2241 | 0.420 |
| common+sem | **0.2324** | **0.2620** | **0.493** |
| warnings+sem | 0.2554 | 0.3068 | 0.382 |
| full+sem | 0.2120 | 0.2286 | 0.400 |

The semantics extractor is 15 deterministic regex features (assignment in
condition, recursion/base case, increment/decrement, index ±1, comparison
directions, loop comparison direction, zero-init, return-minus-one). It uses
source only, never labels.

## Constraints

- Do **not** tune the G8 caps (synthetic mass <= 50%, class mass <= 15%).
  `full` remains the G8-gated variant; `best` is reported separately.
- Preserve lane-supplied values. Missing evidence stays NaN. Never use
  `mutation_op`, `seed_ref`, or other label-derived metadata as a feature.
- Do not edit other lanes' `tier*.jsonl` inputs. Fix merge/trainer/expansion paths.
- Additive schema changes only; bump `schema_version` to `1.1`.
- TDD: write/adjust the test first where practical; run the targeted suite and
  read the output before claiming completion.

## Tasks

### 1. Add the two warning features (schema 1.1)

Files: `tracelearn_features/schema.py`,
`data/misconception_dataset/features/FEATURE_SCHEMA.md`,
`tests/test_extract_features.py`, `tests/test_dataset_contracts.py`,
`tests/test_normalize_lane_features.py`, `tests/test_lane_a.py`,
`scripts/generate_mutants.py`.

Steps:
- Add `infinite_recursion` and `tautological_compare` to
  `FEATURE_BLOCKS["warnings"]` before `other`.
- Add `warnings.infinite_recursion -> -Winfinite-recursion` and
  `warnings.tautological_compare -> -Wtautological-compare` to
  `WARNING_FLAG_OF`.
- Bump `SCHEMA_VERSION` to `"1.1"`; update the module docstring.
- Add both rows to the `warnings` table and normalization map in
  `FEATURE_SCHEMA.md`; update the pinned version to `1.1`.
- Update the version assertions in `test_extract_features.py` and
  `test_dataset_contracts.py`.
- In `test_normalize_lane_features.py`, `-Wtautological-compare` must now map to
  `warnings.tautological_compare == 1` and `warnings.other == 0`; add an
  `-Winfinite-recursion` assertion.
- Allow committed lane rows to be `1.0` **or** `1.1` in `test_lane_a.py`
  (old lane inputs stay 1.0; new/generated rows use 1.1).
- Set `SCHEMA_VERSION = "1.1"` in `scripts/generate_mutants.py` (it is a local
  constant, not imported from the registry).

Verify: `pytest tests/test_extract_features.py tests/test_dataset_contracts.py tests/test_normalize_lane_features.py tests/test_lane_a.py -q`.

### 2. Add the source-semantics block and normalization

Files: new `tracelearn_features/semantics.py`,
`tracelearn_features/schema.py`, `tracelearn_features/normalize.py`,
`FEATURE_SCHEMA.md`, new `tests/test_semantics.py`,
`tests/test_normalize_lane_features.py`, `tests/test_merge_dataset.py`.

Extractor contract:
`extract_semantics(source: str) -> dict[str, int]` returns exactly:

```
assign_in_cond, recursion, increment, decrement, idx_minus1, idx_plus1,
if_gt, if_ge, if_lt, if_le, loop_lt, loop_le, init_zero,
return_minus1, base_case
```

All are ints (0/1 or counts), matching the prototype. Strip comments and string
literals first. Detect function bodies by brace matching for `recursion`.
Return `{}` for an empty/whitespace source so the caller leaves NaN.

Schema:
- Add `"semantics": { ...15 int fields... }` after `cpg`.
- Update `FEATURE_SCHEMA.md` with a `## semantics` section and every row.

Normalization:
- In `normalize_row`, after static mining, if the row source is non-empty and the
  source kind is SYNTHETIC or CODESTREAM, call
  `_fill_block(out, "semantics", extract_semantics(source))`.
- Never overwrite lane values; PROGPEDIA has no source, so it stays NaN.
- This automatically covers CodeStream because the merge passes resolved code.

Tests:
- `assign_in_cond` for `if (x = 1)` and `while (a = b)`.
- `recursion == 1` for a self-call; `base_case == 1` for `if (n <= 1)`.
- `idx_minus1` / `idx_plus1`, `loop_lt` / `loop_le`, `decrement`, `init_zero`,
  `return_minus1`.
- `normalize_row` fills semantics for a synthetic row and for a CodeStream row
  with resolved code; no source -> block stays absent/NaN.
- Update the availability-matrix test's allowed block set to include
  `semantics`.

Verify: `pytest tests/test_semantics.py tests/test_normalize_lane_features.py tests/test_merge_dataset.py -q`.

### 3. Fix `block_present()` availability reporting

File: `scripts/merge_dataset.py` (~line 620).

- Skip the `available` key when deciding whether a block has evidence:
  `available=False` means "not measured", not "populated".
- Keep the existing null/NaN skip.
- Add a merge test with `runtime={"available": False}` and
  `tests={"available": False}` asserting 0.0 availability; a block with
  `total=0` still counts as present.

Verify: `pytest tests/test_merge_dataset.py -q`.

### 4. Add the `best` variant and repeated grouped CV

File: `scripts/train_xgb_misconception.py`;
`tests/test_train_xgb_misconception.py`.

- Add `BEST_PREFIXES = COMMON_PREFIXES + ("semantics.",)`.
- Extend `oof_for` with `repeats: int`; for each repeat create a
  `StratifiedGroupKFold` with `random_state=seed + rep`, accumulate OOF
  probabilities, and average them; collect fold scores across repeats.
- Add `cv_repeats: int = 1` to `train` (tests stay fast); the CLI default is 3.
- Use repeats for the synthetic-multiplier grid and every variant.
- Build `X_best` from `BEST_PREFIXES`, compute `oof_best`, `best_metrics`, save
  `models/xgb_best_v1.json`, and add `metrics["best"]` with its feature list.
- Keep G8 computed from `full` exactly as today; do not change caps or gate.
- Print `best` in the CLI summary and record `cv["repeats"]`.
- Tests: `best` model file exists, `metrics["best"]["features"]` includes
  `semantics.assign_in_cond`, repeated CV is deterministic under a fixed seed,
  and G8 still uses full.

Verify: `pytest tests/test_train_xgb_misconception.py -q`.

### 5. Add the cluster-aware expansion script

New file: `scripts/expand_mutants.py`; new `tests/test_expand_mutants.py`.

Purpose: generate additional verified synthetic mutants from CodeStream seeds in
merge-authority **train** clusters, focusing on classes with 1–2 clusters.

Reuse from `scripts/generate_mutants.py`: `compile_cpp`, `run_cmd`,
`apply_operator_form`, `check_collision`, `make_row`, `norm_pid`, `sha256`,
`load_seeds`, `load_problem_tests`, `load_operator_library`.

Key functions:
- `deterministic_row_id(seed_id, operator, label, cluster) -> str`:
  `"mut-" + sha256(f"{seed_id}|{operator}|{label}|{cluster}|expand-v1")[:10]`.
- `load_cluster_assignments(path) -> dict[str, str]`: train problems only.
- `load_existing_keys(path) -> set[tuple]`: `(seed_ref, mutation_op, problem_id,
  label)` from existing tier0 rows.
- `load_problem_context(path) -> dict[problem_id, dict]`: statement length and
  sample test count for the canonical `context` block.
- `select_target_clusters(class_cluster_counts, reachable_clusters,
  max_clusters)`: prefer clusters with the fewest existing rows for the class.
- `build_expansion_row(seed, mutant_code, label, operator, proof, cluster,
  pipeline_run_id)`: use `make_row`, then set canonical `runtime`/`tests`
  blocks from the proof, set `problem_cluster`, `schema_version="1.1"`, and
  leave `semantics`/`cpg` for the merge to fill.
- `RichVerifier`: compile seed, compile mutant, run tests with per-test status
  (`pass`/`wrong`/`crash`/`timeout`), run ASan/UBSan when the standard run
  passes, classify `asan_heap_buffer_overflow`, `asan_stack_buffer_overflow`,
  `ubsan_signed_overflow`, `stack_overflow`, and write proof JSON.
- `main`: CLI with `--raw-root`, `--dataset-dir`, `--out`, `--proofs-dir`,
  `--classes`, `--clusters-per-class` (default 3), `--rows-per-cluster`
  (default 5), `--max-attempts` (default 30), `--dry-run`, `--pilot`.
  It backs up the target JSONL once (`*.pre_expansion.jsonl`), skips existing
  keys/row_ids, appends accepted rows, and writes
  `reports/expansion_report.json` with per-class/cluster counts and reject
  reasons.

Tests (no compiler):
- deterministic IDs are stable and differ by cluster/operator;
- dedupe keys skip existing rows;
- target-cluster selection prefers under-represented clusters;
- `build_expansion_row` carries canonical `tests`/`runtime` and 1.1;
- `run_tests_rich` status classification with a monkeypatched `run_cmd`.

Verify: `pytest tests/test_expand_mutants.py -q`.

### 6. Pilot and full expansion (WSL)

The Windows host has no `g++`; WSL Ubuntu has g++ 13.3.0. Raw data is at
`/mnt/g/TraceLearn/Datasets_RAW`.

- Dry-run reachability:
  `wsl -e bash -lc "cd /mnt/c/Users/rayaan/Desktop/Trace_Learn/TraceLearn && python3 scripts/expand_mutants.py --raw-root /mnt/g/TraceLearn/Datasets_RAW --dry-run --classes CPP_MISSING_BASE_CASE CPP_RANGE_CHECK CPP_WRONG_LOOP_DIR --clusters-per-class 3 --rows-per-cluster 2"`
- Small real pilot (2 classes, 2 clusters, 2 rows each); inspect new rows and
  proofs, confirm compile/run/sanitizer evidence.
- Full run for the structurally starved classes:
  `CPP_MISSING_BASE_CASE CPP_RANGE_CHECK CPP_WRONG_LOOP_DIR CPP_INT_OVERFLOW
  CPP_STALE_EXIT CPP_UNINITIALIZED_VAR CPP_ASSIGN_VS_COMPARE
  CPP_LOOP_BOUNDARY CPP_OFF_BY_ONE`
  with `--clusters-per-class 3 --rows-per-cluster 5`.
- Do **not** add ARRAY_BOUNDS in this pass: PROGPEDIA already supplies 150 weak
  ARRAY_BOUNDS rows and adding more would increase the source/class confound.
- If `CPP_INT_OVERFLOW` is unreachable in 3 clusters, add only verified forms to
  `scripts/operator_library.json` (`overflow_int64_to_int`,
  `overflow_ll_any_to_int`) and rerun that class; otherwise report the 2-cluster
  limit honestly.

### 7. Regenerate merge/train and compare

- Run `python scripts/merge_dataset.py`.
- Run `python scripts/train_xgb_misconception.py --cv-repeats 3`.
- Confirm:
  - `features.csv` header matches the 1.1 registry (105+ columns);
  - `merge_report.json` availability no longer counts `available=False`;
  - semantics is populated for SYNTHETIC and CODESTREAM, NaN for PROGPEDIA;
  - new rows are in train clusters only; test rows unchanged;
  - `metrics_v1.json` has `best`, `cv.repeats`, and the old `full`/`masked`/`common`;
  - `xgb_best_v1.json` exists.
- Compare `best` vs the previous `common` baseline on CV, OOF, test F1(7), test
  F1(11), per-class F1, ECE, synthetic mass, and class-cluster counts.
- Keep G8 honest: report margin/caps even if they still fail.

### 8. Docs and verification

- Update `docs/dataset_progress_log.md` and
  `.superpowers/sdd/master_plan_dataset/progress.md` with the new section.
- Run the targeted suite:
  `pytest tests/test_semantics.py tests/test_extract_features.py
  tests/test_dataset_contracts.py tests/test_merge_dataset.py
  tests/test_normalize_lane_features.py tests/test_lane_a.py
  tests/test_train_xgb_misconception.py tests/test_expand_mutants.py -q`.
- Run `ruff check` on changed Python files.
- Report exact commands/outputs and before/after metrics. Do not claim G8 passed
  unless the recorded margin actually reaches 0.25.
