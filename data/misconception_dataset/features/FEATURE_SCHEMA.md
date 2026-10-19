# TraceLearn dataset feature schema

**schema_version:** 1.0 · **taxonomy_version:** tl-cpp-v2 · **library:** `tracelearn_features` 0.x
**Status:** frozen at Week-0 (R1). Additive changes bump `schema_version`; breaking changes only in the single post-G3 window executed by `scripts/migrate_schema.py` (§6).

This file is the *enumerated* contract: every feature name and type the
dataset may contain is listed here, and `tests/test_dataset_contracts.py`
enforces exact set equality against `tracelearn_features.schema.FEATURE_BLOCKS`
— a feature that is not in both places does not exist.

## Row shape (JSONL, §6)

```json
{"row_id":"mut-000101", "dataset_source":"SYNTHETIC", "source_record_id":"...",
 "problem_id":"prob_006", "problem_cluster":"clu-014", "language":"cpp",
 "label":"CPP_LOOP_BOUNDARY", "label_source":"synthetic", "label_confidence":0.93,
 "secondary_labels":[], "verdict":null, "firing_functions":["verify_boundary_diff"],
 "seed_ref":"...", "mutation_op":"for_le_bound_lt_n1", "verified_by_execution":true,
 "meta":{"user_id_hash":"...", "attempt_index":3, "timestamp":null, "prev_submission_id":null},
 "static":{...}, "warnings":{...}, "runtime":{...}, "tests":{...}, "cpg":{...}, "context":{...},
 "pipeline_run_id":"run-...", "taxonomy_version":"tl-cpp-v2", "schema_version":"1.0"}
```

- JSONL nests features in their block under the **short** name (`static.loc`);
  `features.csv` flattens to the **canonical** name (`static.loc` → column
  `static.loc`). `lf_inputs`, the masked variant and all docs use canonical names.
- `null` / **NaN** = "the source cannot provide it", never 0. A feature that a
  source structurally cannot produce is NaN for every row of that source
  (e.g. `warnings.*` = NaN for a row whose warnings pass never ran; PROGpedia
  has no tests → `tests.*` NaN unless executed).
- **`meta` is never a feature.** It is carried for V2 history work (§13.6) and
  user-sensitivity checks only; the training matrix drops it by allowlist (§11.1).
- Bookkeeping columns dropped from the matrix by allowlist: `row_id`,
  `dataset_source`, `source_record_id`, `problem_id`, `problem_cluster`,
  `language`, `label`, `label_source`, `label_confidence`, `secondary_labels`,
  `verdict`, `firing_functions`, `seed_ref`, `mutation_op`,
  `verified_by_execution`, `meta`, `pipeline_run_id`, `taxonomy_version`,
  `schema_version`.

## `static`

Source-only features, computed by `tracelearn_features.extract_features` from
the submitted text (no execution required — always available when code exists).

| feature | type | meaning |
|---|---|---|
| `static.loc` | int | physical lines of code |
| `static.sloc` | int | non-blank, non-comment-only lines |
| `static.comment_lines` | int | lines that are only comments |
| `static.max_indent_depth` | int | maximum bracket/indent nesting depth |
| `static.function_count` | int | function/method definitions |
| `static.loop_count` | int | `for`/`while`/`do` loops |
| `static.if_count` | int | `if` statements (incl. `else if`) |
| `static.switch_count` | int | `switch` statements |
| `static.return_count` | int | `return` statements |
| `static.array_decl_count` | int | fixed-size array declarations |
| `static.string_literal_count` | int | string literals |
| `static.numeric_literal_count` | int | integer/floating literals |
| `static.token_count` | int | lexical token count |
| `static.unique_token_ratio` | float | unique tokens / total tokens |
| `static.avg_line_length` | float | mean chars per non-blank line |
| `static.max_line_length` | int | longest line in chars |
| `static.include_count` | int | `#include` directives |
| `static.uses_stdio` | bool | includes `<stdio.h>`/`<cstdio>`/`<iostream>` |
| `static.uses_malloc_free` | bool | uses `malloc`/`calloc`/`free` |
| `static.uses_vector` | bool | uses `std::vector` |

## `warnings`

Compiler warnings from the `-O2 -Wall -Wextra` pass (§9.2-U0 first compile).
`warnings.available` gates the block: NaN everywhere when no pass ran.

| feature | type | meaning |
|---|---|---|
| `warnings.available` | bool | warnings pass produced output for this row |
| `warnings.total` | int | total warnings parsed (all flags) |
| `warnings.unused_variable` | int | `-Wunused-variable` fires |
| `warnings.unused_parameter` | int | `-Wunused-parameter` fires |
| `warnings.unused_but_set_variable` | int | `-Wunused-but-set-variable` fires |
| `warnings.implicit_function_declaration` | int | `-Wimplicit-function-declaration` fires |
| `warnings.parentheses` | int | `-Wparentheses` fires (label-defining: pg-1) |
| `warnings.maybe_uninitialized` | int | `-Wmaybe-uninitialized` fires (label-defining: pg-4, det-4) |
| `warnings.uninitialized` | int | `-Wuninitialized` fires (clang) |
| `warnings.array_bounds` | int | `-Warray-bounds` fires (label-defining: class 3 evidence) |
| `warnings.return_type` | int | `-Wreturn-type` fires |
| `warnings.misleading_indentation` | int | `-Wmisleading-indentation` fires |
| `warnings.stringop_overflow` | int | `-Wstringop-overflow` fires |
| `warnings.stringop_truncation` | int | `-Wstringop-truncation` fires |
| `warnings.format` | int | `-Wformat` fires |
| `warnings.char_subscripts` | int | `-Wchar-subscripts` fires |
| `warnings.sign_compare` | int | `-Wsign-compare` fires |
| `warnings.sequence_point` | int | `-Wsequence-point` fires |
| `warnings.division_by_zero` | int | `-Wdiv-by-zero` fires |
| `warnings.deprecated_declarations` | int | `-Wdeprecated-declarations` fires |
| `warnings.int_in_bool_context` | int | `-Wint-in-bool-context` fires |
| `warnings.other` | int | any other `-W…` warning not enumerated above |

### Warning normalization map

The parser normalizes every compiler warning line to exactly one registry id:

| id | flag | notes |
|---|---|---|
| `warnings.unused_variable` | -Wunused-variable | |
| `warnings.unused_parameter` | -Wunused-parameter | |
| `warnings.unused_but_set_variable` | -Wunused-but-set-variable | |
| `warnings.implicit_function_declaration` | -Wimplicit-function-declaration | |
| `warnings.parentheses` | -Wparentheses | suggest parentheses around assignment used as truth value |
| `warnings.maybe_uninitialized` | -Wmaybe-uninitialized | gcc `-O2` only |
| `warnings.uninitialized` | -Wuninitialized | clang spelling |
| `warnings.array_bounds` | -Warray-bounds | gcc `-O2` |
| `warnings.return_type` | -Wreturn-type | |
| `warnings.misleading_indentation` | -Wmisleading-indentation | |
| `warnings.stringop_overflow` | -Wstringop-overflow | |
| `warnings.stringop_truncation` | -Wstringop-truncation | |
| `warnings.format` | -Wformat | includes `-Wformat-security` |
| `warnings.char_subscripts` | -Wchar-subscripts | |
| `warnings.sign_compare` | -Wsign-compare | |
| `warnings.sequence_point` | -Wsequence-point | |
| `warnings.division_by_zero` | -Wdiv-by-zero | |
| `warnings.deprecated_declarations` | -Wdeprecated-declarations | |
| `warnings.int_in_bool_context` | -Wint-in-bool-context | clang |

Unmatched warning lines increment `warnings.other`.

## `runtime`

From the sanitizer passes (ASan/UBSan `-O1`) and Valgrind memcheck (§9.2-U0).
`runtime.available` gates the block.

| feature | type | meaning |
|---|---|---|
| `runtime.available` | bool | at least one execution pass produced output |
| `runtime.crashed` | bool | process died by signal or abort |
| `runtime.timed_out` | bool | hit the 2 s/test limit (×3 sanitizer) |
| `runtime.exit_code` | int | normal exit code (NaN if signalled) |
| `runtime.signal` | int | terminating signal number (NaN if none) |
| `runtime.duration_s` | float | wall time of the run |
| `runtime.asan_error` | bool | any AddressSanitizer report |
| `runtime.asan_heap_buffer_overflow` | bool | ASan heap-buffer-overflow (label evidence: class 3) |
| `runtime.asan_stack_buffer_overflow` | bool | ASan stack-buffer-overflow |
| `runtime.ubsan_error` | bool | any UndefinedBehaviorSanitizer report |
| `runtime.ubsan_signed_overflow` | bool | UBSan signed integer overflow (label evidence: class 5) |
| `runtime.stack_overflow` | bool | stack-overflow crash growing with input (label evidence: class 6) |
| `runtime.valgrind_error` | bool | any Valgrind memcheck error |
| `runtime.valgrind_uninit_value` | bool | memcheck "uninitialised value" use (label evidence: class 4, det-4) |

## `tests`

Differential results against the problem's embedded tests (§9.2-U0 test
runner). `tests.available` gates the block; PROGpedia rows executed without
tests keep it NaN.

| feature | type | meaning |
|---|---|---|
| `tests.available` | bool | test runner produced results |
| `tests.total` | int | tests executed |
| `tests.passed` | int | tests producing expected output |
| `tests.failed` | int | tests producing wrong output |
| `tests.pass_rate` | float | passed / total |
| `tests.wrong_answer_count` | int | failures with clean exit + diff output |
| `tests.runtime_error_count` | int | tests where the program crashed |
| `tests.timeout_count` | int | tests that hit the time limit |
| `tests.first_fail_index` | int | 0-based index of first divergent test (tie-break input, §3.2 rule 5; -1 when none) |
| `tests.first_fail_numeric_diff` | float | signed numeric delta of first divergent test when both sides parse as numbers (±1 signal for classes 1/2; NaN otherwise) |
| `tests.boundary_fail_count` | int | failing tests whose input sits at a boundary value (label evidence: class 9, det-9) |

## `cpg`

Code-property-graph features from `scripts/parse_cpg.py` (clang AST, ≥95%
parse gate R3). `cpg.available` gates the block; unparsed rows are dropped at
R3, never guessed.

| feature | type | meaning |
|---|---|---|
| `cpg.available` | bool | CPG parsed for this row |
| `cpg.node_count` | int | graph nodes |
| `cpg.edge_count` | int | graph edges |
| `cpg.max_depth` | int | AST depth |
| `cpg.function_count` | int | function decls |
| `cpg.loop_count` | int | loop statements |
| `cpg.assign_in_condition_count` | int | assignments inside conditions (label-defining: pg-1) |
| `cpg.assign_feeds_output_count` | int | such assignments whose variable reaches output computation (pg-1's second distinct signal, §3.4/§17) |
| `cpg.unguarded_recursion_count` | int | self-calls without base-case guard (label-defining: pg-2) |
| `cpg.array_write_oob_count` | int | writes beyond fixed declared size (label-defining: pg-3) |
| `cpg.use_before_init_count` | int | use-before-init paths (label-defining: pg-4) |
| `cpg.decrement_in_loop_count` | int | decrementing/reversed loop iteration (label evidence: class 8, det-8) |
| `cpg.loop_cond_var_unassigned_count` | int | loop-condition vars never assigned in body (label evidence: class 10, det-10) |
| `cpg.comparison_count` | int | relational comparisons |
| `cpg.ast_ref_similarity` | float | AST similarity to the problem's reference solution (det-8; NaN when no reference) |

## `context`

Problem context joined from normalized `problems.csv` at merge time (§4).

| feature | type | meaning |
|---|---|---|
| `context.statement_length` | int | chars of statement text |
| `context.sample_test_count` | int | sample tests shipped with the problem |
| `context.sample_tests_present` | bool | statement includes sample tests |
| `context.constraints_present` | bool | statement includes a constraints section |
| `context.difficulty` | float | problem difficulty if the source provides one (NaN for CodeStream/PROGpedia) |
| `context.concept_tag_count` | int | concept tags on the problem |
| `context.cpp_submission_count` | int | C/C++ submissions recorded for the problem |

## `tracelearn_features` v0 interface (fixed, Week 0)

Lanes compute their own JSONL feature blocks from day one with exactly this
signature (§5); the merge re-runs it only to backfill blocks a lane shipped as
null (schema allows lane feature blocks to be null → filled post-concat).

```python
def extract_features(
    source: str,
    language: str = "cpp",
    *,
    warnings: list[dict] | None = None,
    runtime: dict | None = None,
    tests: dict | None = None,
    cpg: dict | None = None,
    context: dict | None = None,
) -> dict[str, dict[str, float | None]]:
    """Return nested feature blocks keyed by block name (row shape above).

    - `source` is the submitted text; `static` is always computed from it.
    - Evidence arguments are raw parses (warning lines, sanitizer report,
      test results, CPG dump, problem row). Omitted/None evidence ⇒ that
      whole block is filled with NaN and its `available` gate False.
    - Never raises on malformed evidence: NaN means "cannot provide".
    - `meta` is never produced here; it is copied verbatim from lane rows.
    """
```

Version pin: lanes import `tracelearn_features.__version__` and stamp it in
`pipeline_run_id`; the interface above does not change until the post-G3
migration window (R1 contract).

## Label-defining feature registry

`label_defining_features.json` (same directory) lists, per LF/operator, the
features its label depends on (`lf_inputs`). Uses:

1. **Masked variant** (§11.5): those inputs → NaN on weak rows at train time.
2. **Leakage audit** (G9 SHAP): if a rule-labeled class draws >70% of its SHAP
   mass from its own `lf_inputs`, that is flagged as learning the rule, not the bug.
3. **Decoy design** (E1d): decoy operators present the surface pattern of an
   `lf_inputs` feature while the failure cause is elsewhere.

## Evolution policy

- Additive (new feature, new warning id): allowed anytime, `schema_version`
  bumped, this file updated in the same commit, contract test enforces sync.
- Breaking (rename/drop/retype): only in the one scheduled post-G3 window via
  `scripts/migrate_schema.py`; before then, readers must tolerate unknown
  additive columns but writers must never emit them.
