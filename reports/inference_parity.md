# Inference Feature Parity Report

**Date:** 2026-11-08  
**Branch:** feat/inference-feature-builder  
**Corpus:** `data/cpp_diagnostics/` — 72 `.cpp` files across 8 misconception classes  
**Parity test:** `backend/tests/test_model_feature_parity.py` (12 tests, all PASSED)

---

## Summary

The `InferenceFeatureBuilder` produces a feature vector that is byte-for-byte
identical to the reference `extract_features()` call for every checkable block.
No mismatches were found across 2 520 feature-file combinations (1 440 static
checks + 1 080 semantics checks) on the full 72-file corpus.

---

## Feature schema

| Block      | Features | Source at inference        |
|------------|----------|---------------------------|
| static     | 20       | `extract_features()` — full parity |
| warnings   | 24       | `parse_warnings(stderr)` |
| runtime    | 14       | All NaN (`runtime.available = False`) |
| tests      | 11       | `map_test_results(test_results)` |
| cpg        | 15       | CPG proxy (`extract_cpg_source()`) |
| semantics  | 15       | `extract_features()` — full parity |
| context    | 8        | Reserved — all NaN at inference |
| **Total**  | **107**  | |

> The "best" variant uses a 59-feature subset; the full 107-feature schema is
> the basis for `InferenceFeatureBuilder.build()` regardless of variant.

---

## Per-block mismatch table

| Block     | Files checked | Features/file | Checks | Mismatches | Parity |
|-----------|--------------|---------------|--------|------------|--------|
| static    | 72           | 20            | 1 440  | 0          | ✓ 100% |
| semantics | 72           | 15            | 1 080  | 0          | ✓ 100% |
| warnings  | n/a          | 24            | unit   | 0          | ✓ unit |
| runtime   | 72           | 13 numeric    | 936    | 0 (all NaN)| ✓ 100% |
| cpg       | 72           | 1 bool + 14   | 72     | 0          | ✓ 100% |
| tests     | n/a          | 11            | unit   | 0          | ✓ unit |

Runtime and context blocks are intentionally all-NaN at inference time (no
execution output is available); the parity test asserts this invariant.

---

## Gates verified

| Gate | Description | Result |
|------|-------------|--------|
| I1-schema | Key set equals `feature_names()` on any source | PASS |
| I1-empty  | Key set equals `feature_names()` on empty source | PASS |
| I1-static | Static block identical to `extract_features()` on 72 files | PASS |
| I1-semantics | Semantics block identical to `extract_features()` on 72 files | PASS |
| I1-runtime | All runtime numeric features are NaN; `runtime.available = False` | PASS |
| I1-cpg | CPG proxy fills `loop_count` and structural fields for sources with loops | PASS |
| I1-vector | Builder output accepted by `ModelClassifier.vector()` on all 72 files | PASS |
| I1-warnings | `parse_warnings()` counts, deduplicates, and orders warning flags | PASS |

---

## Notes

- The CPG proxy (`extract_cpg_source`) uses regex heuristics rather than a
  true code property graph; it fills structural counts (loops, comparisons,
  assignments-in-conditions, unguarded recursion) but leaves fine-grained
  graph metrics at NaN.  The model was trained on the same proxy output, so
  train/inference parity is maintained.
- `cpg.available` is a boolean (`True`/`False`), not a float; the parity test
  explicitly excludes it from the NaN-check on empty source.
- The "best" variant uses 59 of the 107 schema features.  The 48 unused
  features are passed to `model.vector()` and silently dropped by the booster.
