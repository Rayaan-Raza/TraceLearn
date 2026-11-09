# TraceLearn dataset feature schema

**schema_version:** 1.2 · **taxonomy_version:** tl-cpp-v2 · **library:** `tracelearn_features` 0.x
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
Every row with a run record takes this block from that record (`normalize.runner_warnings`), because lanes
that measured it themselves disagreed and models learned the disagreement (`docs/6-nov.md` section 15).

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
| `warnings.infinite_recursion` | int | `-Winfinite-recursion` fires (label-defining: missing base case) |
| `warnings.tautological_compare` | int | `-Wtautological-compare` fires (label-defining: assignment vs compare / off-by-one) |
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
| `warnings.infinite_recursion` | -Winfinite-recursion | gcc/clang recursion detector |
| `warnings.tautological_compare` | -Wtautological-compare | clang spelling; gcc emits `-Wtautological-compare` in newer versions |

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

## `semantics`

Deterministic source-level signals computed by
`tracelearn_features/semantics.py` for SYNTHETIC (embedded mutant code) and
CODESTREAM (resolved submission code). PROGPEDIA rows have no source in this
dataset, so their semantics stay NaN. These are source signals only; label
metadata (`mutation_op`, `seed_ref`) is never used.

| feature | type | meaning |
|---|---|---|
| `semantics.assign_in_cond` | int | assignment used as an `if`/`while` condition |
| `semantics.recursion` | int | a function body calls its own name |
| `semantics.increment` | int | `++` count |
| `semantics.decrement` | int | `--` count |
| `semantics.idx_minus1` | int | an index expression of the form `a[i - 1]` |
| `semantics.idx_plus1` | int | an index expression of the form `a[i + 1]` |
| `semantics.if_gt` | int | an `if` uses `>` |
| `semantics.if_ge` | int | an `if` uses `>=` |
| `semantics.if_lt` | int | an `if` uses `<` |
| `semantics.if_le` | int | an `if` uses `<=` |
| `semantics.loop_lt` | int | a loop condition uses `<` |
| `semantics.loop_le` | int | a loop condition uses `<=` |
| `semantics.init_zero` | int | an `int` local is initialized to zero |
| `semantics.return_minus1` | int | a `return` expression subtracts one |
| `semantics.base_case` | int | a recursive base-case test against 0/1 is present |
| `semantics.chained_compare` | int | a condition chains comparisons, as in `1 <= x <= 10` |
| `semantics.index_is_bound` | int | an index read whose subscript is the length (`a[n]`, `v[v.size()]`) |
| `semantics.scanf_no_amp` | int | a `scanf` argument that is a bare identifier without `&` |
| `semantics.no_input_read` | int | the program never reads input |
| `semantics.prompt_text` | int | output text that looks like a prompt (enter, input, please, type, give) |
| `semantics.printf_addr_arg` | int | `printf` given the address of a variable |
| `semantics.int_div_literals` | int | integer division of two literals, as in `1/2` |
| `semantics.char_vs_string_cmp` | int | a comparison against a one-character string literal |
| `semantics.empty_body_stmt` | int | an `if`/`for`/`while` header followed directly by `;` |
| `semantics.loop_var_reused` | int | a loop nested in a loop that re-initialises the same undeclared variable |
| `semantics.plus1_index_in_full_loop` | int | `a[i + 1]` inside a loop that runs `i` up to `n` (reads one past the end) |
| `semantics.minus1_index_from_zero` | int | `a[i - 1]` inside a loop that starts `i` at 0 (reads before the start) |

## `context`

Problem context joined from normalized `problems.csv` at merge time (§4).

| feature | type | meaning |
|---|---|---|
| `context.available` | bool | problem row joined for this row |
| `context.statement_length` | int | chars of statement text |
| `context.sample_test_count` | int | sample tests shipped with the problem |
| `context.sample_tests_present` | bool | statement includes sample tests |
| `context.constraints_present` | bool | statement includes a constraints section |
| `context.difficulty` | float | problem difficulty if the source provides one (NaN for CodeStream/PROGpedia) |
| `context.concept_tag_count` | int | concept tags on the problem |
| `context.cpp_submission_count` | int | C/C++ submissions recorded for the problem |

## `source`

Patterns in the submission's own code, from `tracelearn_features/execution.py`. Added in 1.2.

| feature | type | meaning |
|---|---|---|
| `source.arr_fixed_n` | int | arrays declared with a constant size |
| `source.arr_vla_n` | int | arrays sized by a non-constant |
| `source.arr_fixed_max_log` | float | log10 of the largest constant array size |
| `source.arr_fixed_min_log` | float | log10 of the smallest constant array size |
| `source.heap_alloc` | int | malloc, calloc or new uses |
| `source.uses_ll` | int | long long or a 64-bit type appears |
| `source.uses_long` | int | `long` appears |
| `source.uses_double` | int | double or float appears |
| `source.mult_ident` | int | multiplications of identifiers |
| `source.mult_assign` | int | `*=` uses |
| `source.pow_call` | int | pow() calls |
| `source.accum` | int | `+=` uses |
| `source.fmt_ll` | int | `%ld` or `%lld` appears |
| `source.lp_le` | int | loop conditions using `<=` |
| `source.lp_lt` | int | loop conditions using `<` |
| `source.lp_ge` | int | loop conditions using `>=` |
| `source.lp_gt` | int | loop conditions using `>` |
| `source.lp_le_idx` | int | `<=` loops indexing with the loop variable |
| `source.lp_lt_m1` | int | `<` loops bounded by something minus 1 |
| `source.lp_s1_lt` | int | loops from 1 using `<` |
| `source.lp_s1_le` | int | loops from 1 using `<=` |
| `source.lp_s0_le` | int | loops from 0 using `<=` |
| `source.lp_idx_plus` | int | loops indexing `[i+k]` |
| `source.lp_idx_minus` | int | loops indexing `[i-k]` |
| `source.lp_wrong_idx` | int | loops indexing only with other variables |
| `source.lp_stale` | int | while loops whose condition variables never change in the body |
| `source.lp_desc` | int | loops with a decrementing update |
| `source.read_before_write` | int | declared-unset variables whose first use reads them |
| `source.if_lit_cmp` | int | if conditions comparing to a literal |
| `source.if_and` | int | if conditions with `&&` |
| `source.if_or` | int | if conditions with `\|\|` |
| `source.else_if` | int | `else if` uses |
| `source.if_strict` | int | if conditions with `<` or `>` |
| `source.if_nonstrict` | int | if conditions with `<=` or `>=` |
| `source.if_eq` | int | if conditions with `==` |
| `source.minus1` | int | `- 1` uses |
| `source.plus1` | int | `+ 1` uses |

## `evidence`

What running the program against the problem's tests shows, from `scripts/counterfactual_evidence.py`: one runner and one set of flags for every lane, with sanitizers on and Valgrind off. NaN when the program did not compile or has no run record. Added in 1.2.

| feature | type | meaning |
|---|---|---|
| `evidence.n` | float | tests run |
| `evidence.pass_frac` | float | share of tests passed |
| `evidence.ff_frac` | float | position of the first failing test, 0 to 1 |
| `evidence.ff_wrong` | float | first failing test has status wrong |
| `evidence.fr_wrong` | float | share of failures with status wrong |
| `evidence.ff_crash` | float | first failing test has status crash |
| `evidence.fr_crash` | float | share of failures with status crash |
| `evidence.ff_timeout` | float | first failing test has status timeout |
| `evidence.fr_timeout` | float | share of failures with status timeout |
| `evidence.ff_presentation` | float | first failing test has status presentation |
| `evidence.fr_presentation` | float | share of failures with status presentation |
| `evidence.tok_delta` | float | output token count minus expected, first failing test |
| `evidence.tok_ratio` | float | output tokens over expected tokens, first failing test |
| `evidence.prefix_frac` | float | share of expected tokens matched before the first difference |
| `evidence.exp_tok_log` | float | log10 of expected token count |
| `evidence.is_prefix_of_expected` | float | first failing test: is prefix of expected |
| `evidence.expected_is_prefix` | float | first failing test: expected is prefix |
| `evidence.is_suffix_of_expected` | float | first failing test: is suffix of expected |
| `evidence.expected_is_suffix` | float | first failing test: expected is suffix |
| `evidence.empty_output` | float | first failing test: empty output |
| `evidence.reversed_tokens` | float | first failing test: reversed tokens |
| `evidence.reversed_lines` | float | first failing test: reversed lines |
| `evidence.same_multiset` | float | first failing test: same multiset |
| `evidence.all_deltas_pm1` | float | first failing test: all deltas pm1 |
| `evidence.negative_where_positive` | float | first failing test: negative where positive |
| `evidence.maxd_log` | float | log10 of the largest numeric difference |
| `evidence.nd_frac` | float | differing numeric tokens over expected tokens |
| `evidence.sign_delta` | float | sign of the first numeric difference |
| `evidence.fr_pm1` | float | share of failures where every difference is 1 |
| `evidence.fr_neg` | float | share of failures with a negative where a positive was expected |
| `evidence.fr_empty` | float | share of failures with empty output |
| `evidence.sa_avail` | float | the sanitizer pass ran |
| `evidence.sa_oob` | float | sanitizer reported oob |
| `evidence.sa_stack` | float | sanitizer reported stack |
| `evidence.sa_heap` | float | sanitizer reported heap |
| `evidence.sa_global` | float | sanitizer reported global |
| `evidence.sa_signed` | float | sanitizer reported signed |
| `evidence.sa_shift` | float | sanitizer reported shift |
| `evidence.sa_div` | float | sanitizer reported div |
| `evidence.sa_null` | float | sanitizer reported null |
| `evidence.sa_so` | float | sanitizer reported so |
| `evidence.sa_uaf` | float | sanitizer reported uaf |
| `evidence.sa_vla` | float | sanitizer reported vla |
| `evidence.sa_n` | float | distinct sanitizer report kinds |
| `evidence.sa_past_min` | float | smallest elements past the end of an array |
| `evidence.sa_past_max_log` | float | log10 of the largest elements past the end |
| `evidence.sa_neg_idx` | float | a report shows a negative index |
| `evidence.sa_left` | float | a report shows an access left of the buffer |
| `evidence.sa_write` | float | a report shows a write |
| `evidence.rt_so` | float | stack overflow reported |

## `repair`

For each class's inverse edits (`scripts/repair_verify.py`), whether one small edit changes the test results. No label is read. NaN when no first failing test exists or no run record exists. Added in 1.2.

| feature | type | meaning |
|---|---|---|
| `repair.loop_boundary_fix_first` | float | LOOP_BOUNDARY inverse edits: edits passing the first failing test, capped at 3 |
| `repair.loop_boundary_noreg` | float | LOOP_BOUNDARY inverse edits: of those, edits breaking no passing test, capped at 3 |
| `repair.loop_boundary_fix_all` | float | LOOP_BOUNDARY inverse edits: an edit passes every test |
| `repair.loop_boundary_gain` | float | LOOP_BOUNDARY inverse edits: best gain in share of tests passed |
| `repair.loop_boundary_tried` | float | LOOP_BOUNDARY inverse edits: at least one edit compiled |
| `repair.off_by_one_fix_first` | float | OFF_BY_ONE inverse edits: edits passing the first failing test, capped at 3 |
| `repair.off_by_one_noreg` | float | OFF_BY_ONE inverse edits: of those, edits breaking no passing test, capped at 3 |
| `repair.off_by_one_fix_all` | float | OFF_BY_ONE inverse edits: an edit passes every test |
| `repair.off_by_one_gain` | float | OFF_BY_ONE inverse edits: best gain in share of tests passed |
| `repair.off_by_one_tried` | float | OFF_BY_ONE inverse edits: at least one edit compiled |
| `repair.array_bounds_fix_first` | float | ARRAY_BOUNDS inverse edits: edits passing the first failing test, capped at 3 |
| `repair.array_bounds_noreg` | float | ARRAY_BOUNDS inverse edits: of those, edits breaking no passing test, capped at 3 |
| `repair.array_bounds_fix_all` | float | ARRAY_BOUNDS inverse edits: an edit passes every test |
| `repair.array_bounds_gain` | float | ARRAY_BOUNDS inverse edits: best gain in share of tests passed |
| `repair.array_bounds_tried` | float | ARRAY_BOUNDS inverse edits: at least one edit compiled |
| `repair.uninitialized_var_fix_first` | float | UNINITIALIZED_VAR inverse edits: edits passing the first failing test, capped at 3 |
| `repair.uninitialized_var_noreg` | float | UNINITIALIZED_VAR inverse edits: of those, edits breaking no passing test, capped at 3 |
| `repair.uninitialized_var_fix_all` | float | UNINITIALIZED_VAR inverse edits: an edit passes every test |
| `repair.uninitialized_var_gain` | float | UNINITIALIZED_VAR inverse edits: best gain in share of tests passed |
| `repair.uninitialized_var_tried` | float | UNINITIALIZED_VAR inverse edits: at least one edit compiled |
| `repair.int_overflow_fix_first` | float | INT_OVERFLOW inverse edits: edits passing the first failing test, capped at 3 |
| `repair.int_overflow_noreg` | float | INT_OVERFLOW inverse edits: of those, edits breaking no passing test, capped at 3 |
| `repair.int_overflow_fix_all` | float | INT_OVERFLOW inverse edits: an edit passes every test |
| `repair.int_overflow_gain` | float | INT_OVERFLOW inverse edits: best gain in share of tests passed |
| `repair.int_overflow_tried` | float | INT_OVERFLOW inverse edits: at least one edit compiled |
| `repair.missing_base_case_fix_first` | float | MISSING_BASE_CASE inverse edits: edits passing the first failing test, capped at 3 |
| `repair.missing_base_case_noreg` | float | MISSING_BASE_CASE inverse edits: of those, edits breaking no passing test, capped at 3 |
| `repair.missing_base_case_fix_all` | float | MISSING_BASE_CASE inverse edits: an edit passes every test |
| `repair.missing_base_case_gain` | float | MISSING_BASE_CASE inverse edits: best gain in share of tests passed |
| `repair.missing_base_case_tried` | float | MISSING_BASE_CASE inverse edits: at least one edit compiled |
| `repair.assign_vs_compare_fix_first` | float | ASSIGN_VS_COMPARE inverse edits: edits passing the first failing test, capped at 3 |
| `repair.assign_vs_compare_noreg` | float | ASSIGN_VS_COMPARE inverse edits: of those, edits breaking no passing test, capped at 3 |
| `repair.assign_vs_compare_fix_all` | float | ASSIGN_VS_COMPARE inverse edits: an edit passes every test |
| `repair.assign_vs_compare_gain` | float | ASSIGN_VS_COMPARE inverse edits: best gain in share of tests passed |
| `repair.assign_vs_compare_tried` | float | ASSIGN_VS_COMPARE inverse edits: at least one edit compiled |
| `repair.wrong_loop_dir_fix_first` | float | WRONG_LOOP_DIR inverse edits: edits passing the first failing test, capped at 3 |
| `repair.wrong_loop_dir_noreg` | float | WRONG_LOOP_DIR inverse edits: of those, edits breaking no passing test, capped at 3 |
| `repair.wrong_loop_dir_fix_all` | float | WRONG_LOOP_DIR inverse edits: an edit passes every test |
| `repair.wrong_loop_dir_gain` | float | WRONG_LOOP_DIR inverse edits: best gain in share of tests passed |
| `repair.wrong_loop_dir_tried` | float | WRONG_LOOP_DIR inverse edits: at least one edit compiled |
| `repair.range_check_fix_first` | float | RANGE_CHECK inverse edits: edits passing the first failing test, capped at 3 |
| `repair.range_check_noreg` | float | RANGE_CHECK inverse edits: of those, edits breaking no passing test, capped at 3 |
| `repair.range_check_fix_all` | float | RANGE_CHECK inverse edits: an edit passes every test |
| `repair.range_check_gain` | float | RANGE_CHECK inverse edits: best gain in share of tests passed |
| `repair.range_check_tried` | float | RANGE_CHECK inverse edits: at least one edit compiled |
| `repair.n_fix_all` | float | classes with an edit that passes every test |
| `repair.n_fix_first` | float | classes with an edit that passes the first failing test |
| `repair.uninit_differs` | float | first failing test output changes between zero and pattern initialisation of locals |
| `repair.uninit_zero_fixes` | float | zero-initialising locals passes the first failing test |

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
