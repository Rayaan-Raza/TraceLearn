"""Enumerated feature registry for schema_version 1.0 (§6, R1).

`FEATURE_BLOCKS` is the single source of truth: every feature name and type the
dataset may ever contain is listed here, and `FEATURE_SCHEMA.md` must document
exactly this set (enforced by tests/test_dataset_contracts.py).

Naming: registry keys are canonical full names `block.short_name`. In JSONL
rows features live in their nested block under the short name (§6 row shape);
in `features.csv` they flatten to the canonical full name. The `lf_inputs`
registry, the masked training variant and every doc reference use the
canonical full name.

Evolution: additive changes are allowed anytime (schema_version bump);
breaking changes only in the single post-G3 window (§6).
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0"

# block -> {short_name: type}. Order = column order in features.csv.
FEATURE_BLOCKS: dict[str, dict[str, str]] = {
    "static": {
        "loc": "int",
        "sloc": "int",
        "comment_lines": "int",
        "max_indent_depth": "int",
        "function_count": "int",
        "loop_count": "int",
        "if_count": "int",
        "switch_count": "int",
        "return_count": "int",
        "array_decl_count": "int",
        "string_literal_count": "int",
        "numeric_literal_count": "int",
        "token_count": "int",
        "unique_token_ratio": "float",
        "avg_line_length": "float",
        "max_line_length": "int",
        "include_count": "int",
        "uses_stdio": "bool",
        "uses_malloc_free": "bool",
        "uses_vector": "bool",
    },
    "warnings": {
        "available": "bool",
        "total": "int",
        "unused_variable": "int",
        "unused_parameter": "int",
        "unused_but_set_variable": "int",
        "implicit_function_declaration": "int",
        "parentheses": "int",
        "maybe_uninitialized": "int",
        "uninitialized": "int",
        "array_bounds": "int",
        "return_type": "int",
        "misleading_indentation": "int",
        "stringop_overflow": "int",
        "stringop_truncation": "int",
        "format": "int",
        "char_subscripts": "int",
        "sign_compare": "int",
        "sequence_point": "int",
        "division_by_zero": "int",
        "deprecated_declarations": "int",
        "int_in_bool_context": "int",
        "other": "int",
    },
    "runtime": {
        "available": "bool",
        "crashed": "bool",
        "timed_out": "bool",
        "exit_code": "int",
        "signal": "int",
        "duration_s": "float",
        "asan_error": "bool",
        "asan_heap_buffer_overflow": "bool",
        "asan_stack_buffer_overflow": "bool",
        "ubsan_error": "bool",
        "ubsan_signed_overflow": "bool",
        "stack_overflow": "bool",
        "valgrind_error": "bool",
        "valgrind_uninit_value": "bool",
    },
    "tests": {
        "available": "bool",
        "total": "int",
        "passed": "int",
        "failed": "int",
        "pass_rate": "float",
        "wrong_answer_count": "int",
        "runtime_error_count": "int",
        "timeout_count": "int",
        "first_fail_index": "int",
        "first_fail_numeric_diff": "float",
        "boundary_fail_count": "int",
    },
    "cpg": {
        "available": "bool",
        "node_count": "int",
        "edge_count": "int",
        "max_depth": "int",
        "function_count": "int",
        "loop_count": "int",
        "assign_in_condition_count": "int",
        "assign_feeds_output_count": "int",
        "unguarded_recursion_count": "int",
        "array_write_oob_count": "int",
        "use_before_init_count": "int",
        "decrement_in_loop_count": "int",
        "loop_cond_var_unassigned_count": "int",
        "comparison_count": "int",
        "ast_ref_similarity": "float",
    },
    "context": {
        "available": "bool",
        "statement_length": "int",
        "sample_test_count": "int",
        "sample_tests_present": "bool",
        "constraints_present": "bool",
        "difficulty": "float",
        "concept_tag_count": "int",
        "cpp_submission_count": "int",
    },
}

# Canonical -W flag for every countable warnings.* feature (§6 "full warning
# enumeration"). `available`, `total` and the `other` catch-all have no flag.
WARNING_FLAG_OF: dict[str, str] = {
    "warnings.unused_variable": "-Wunused-variable",
    "warnings.unused_parameter": "-Wunused-parameter",
    "warnings.unused_but_set_variable": "-Wunused-but-set-variable",
    "warnings.implicit_function_declaration": "-Wimplicit-function-declaration",
    "warnings.parentheses": "-Wparentheses",
    "warnings.maybe_uninitialized": "-Wmaybe-uninitialized",
    "warnings.uninitialized": "-Wuninitialized",
    "warnings.array_bounds": "-Warray-bounds",
    "warnings.return_type": "-Wreturn-type",
    "warnings.misleading_indentation": "-Wmisleading-indentation",
    "warnings.stringop_overflow": "-Wstringop-overflow",
    "warnings.stringop_truncation": "-Wstringop-truncation",
    "warnings.format": "-Wformat",
    "warnings.char_subscripts": "-Wchar-subscripts",
    "warnings.sign_compare": "-Wsign-compare",
    "warnings.sequence_point": "-Wsequence-point",
    "warnings.division_by_zero": "-Wdiv-by-zero",
    "warnings.deprecated_declarations": "-Wdeprecated-declarations",
    "warnings.int_in_bool_context": "-Wint-in-bool-context",
}


def feature_names(with_types: bool = False) -> list[str] | list[tuple[str, str]]:
    """Canonical feature names in features.csv column order."""
    out: list[tuple[str, str]] = []
    for block, feats in FEATURE_BLOCKS.items():
        for short, ftype in feats.items():
            out.append((f"{block}.{short}", ftype))
    if with_types:
        return out
    return [name for name, _ in out]


def block_of(feature_name: str) -> str:
    """`static.loc` -> `static`."""
    block, _, _ = feature_name.partition(".")
    if block not in FEATURE_BLOCKS:
        raise KeyError(f"unknown feature block: {feature_name}")
    return block
