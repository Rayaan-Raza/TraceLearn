# TraceLearn Misconception Dataset — Data Card

## Dataset / version
- **Name**: TraceLearn tl-cpp-v2 Misconception Dataset
- **Version**: 0.6 (PROGPedia execution lane, dev-gold + IID pools, schema v1.1)
- **Date**: 2026-10-26
- **Schema version**: 1.1 (`warnings.infinite_recursion`, `warnings.tautological_compare`, `semantics.*` block)

## Intended use
- **Primary**: Train and evaluate an XGBoost misconception classifier for C++ student submissions
- **Taxonomy development**: 11-class `tl-cpp-v2` taxonomy (loop boundary, off-by-one, array bounds, uninitialized variable, integer overflow, missing base case, assign-vs-compare, wrong loop direction, range check, stale exit, other error)
- **Feature research**: Study which feature blocks (static, warnings, runtime, tests, CPG, semantics) are most predictive per misconception class
- **Not intended for**: Direct student-facing feedback without human review; production grading

## Sources

| Source | Rows | Lanes | License / access |
|--------|------|-------|-----------------|
| PROGPEDIA | 285 | `tier1b` pg-3 static rule (pg-\*), `tier1c` executed on oracle tests (pgx-\*) | Research only; not redistributable |
| CODESTREAM | 33 | `tier1a` executed weak rules + repair verification (cs-\*) | Research only; not redistributable |
| SYNTHETIC | 384 | `tier0` cluster-aware mutants (mut-\*) | Generated; no third-party restriction |
| **Total** | **702** | after MinHash dedupe (996 → 702, Jaccard ≥ 0.8) | |

PROGPedia has no hidden tests, so `scripts/progpedia_oracle_tests.py` builds **oracle tests**
for 12 problems (128 tests): seeded generators, expected output = the consensus of
ACCEPTED submissions (≥ 2 agree and ≥ 2/3 of those that finish), statement samples must
match, and Python reference solvers drop tests where the accepted programs themselves
overflow (e.g. Inversions). See `reports/progpedia_oracle_tests.md` and
`reports/progpedia_exec_report.md`.

## Processing
- **Normalization version**: `tracelearn_features.normalize` v1.1 (rows with `evidence_vocab = sandbox_runner` get the CodeStream runtime/tests mapping, whatever their source)
- **Feature schema version**: 1.1 (`tracelearn_features.schema.SCHEMA_VERSION`)
- **Feature dimensions**: 90 canonical features across 7 blocks (static, warnings, runtime, tests, cpg, semantics, context)
- **Merge script**: `scripts/merge_dataset.py` (G1 row checks, MinHash dedupe, signed review decisions, G7 leakage gate, IID override)
- **Labeling**: SYNTHETIC labels are deterministic from the mutation operator (execution-verified). Executed lanes (CodeStream, PROGPedia tier1c) label `repair_verified` when one targeted repair makes every test pass, `weak_rule` when a single LF fires; multi-signal and discovery-class rows go to a review pool, never straight to a label. Weak confidence = min(0.85, Beta(1,1) lower-80% bound of the audited LF precision), so unaudited LFs ship at ~0.2. PROGPedia tier1b ships at the §3.4 provisional cap (0.60/0.55).

## Labels

| Class | Rows | PROGPEDIA | CODESTREAM | SYNTHETIC |
|-------|-----:|----------:|-----------:|----------:|
| CPP_ARRAY_BOUNDS | 191 | 173 | 8 | 10 |
| CPP_ASSIGN_VS_COMPARE | 22 | 0 | 1 | 21 |
| CPP_INT_OVERFLOW | 101 | 56 | 8 | 37 |
| CPP_LOOP_BOUNDARY | 95 | 48 | 4 | 43 |
| CPP_MISSING_BASE_CASE | 47 | 1 | 0 | 46 |
| CPP_OFF_BY_ONE | 62 | 7 | 12 | 43 |
| CPP_OTHER_ERROR | 13 | 0 | 0 | 13 |
| CPP_RANGE_CHECK | 51 | 0 | 0 | 51 |
| CPP_STALE_EXIT | 43 | 0 | 0 | 43 |
| CPP_UNINITIALIZED_VAR | 35 | 0 | 0 | 35 |
| CPP_WRONG_LOOP_DIR | 42 | 0 | 0 | 42 |

- **Label sources**: synthetic 384 · weak_rule 266 · repair_verified 52 · human 0 (yet)
- **Human review**: Claude pre-reviewed 264 items in `review/model_prereview/` (CodeStream weak 33 + dev-gold 30, PROGPedia weak 150, PROGPedia dev-gold 17 + IID 17). **No sheet is signed yet**, so no label has changed and `lf_audits.csv` is still empty. Model-estimated weak-label precision: CodeStream ~45% (15/33), PROGPedia pg-3 ~76% (104/137 judged). Sign-off rules: `review/model_prereview/README.md`.

## Splits

| Split | Rows | Note |
|-------|-----:|------|
| train | 588 | All three sources; grouped by problem cluster |
| dev_gold | 45 | 4 CodeStream clusters + PROGPedia clu-049 / clu-051; calibration only, never in CV |
| test | 33 | Frozen cluster-disjoint CodeStream test; evaluated once |
| test_iid | 36 | Seeded stratified natural rows from train clusters (in-distribution test); excluded from training |

- Clusters never straddle splits; seed groups intact; MinHash cross-split twins: 0 (G7, with test_iid checked as its own split)
- Dev-gold reaches ≥ 60 **certain** rows once the dev-gold sheets are signed (30 CodeStream items + 41 PROGPedia rows)
- Only certain labels (human / repair-verified / synthetic) are scored on held-out pools (`scripts/evaluate_holdout.py`); see `splits/README.md`

## Model performance (v0.6)

| Variant | CV macro-F1 | OOF macro-F1 | ECE |
|---------|-------------|--------------|-----|
| **full (all features)** | **0.724 ± 0.030** | 0.713 | 0.064 |
| common (static + warnings) | 0.705 ± 0.045 | 0.696 | 0.087 |
| best (static + warnings + semantics) | 0.711 ± 0.037 | 0.703 | 0.101 |

CV: 3×3 StratifiedGroupKFold, grouped by problem cluster. Majority baseline 0.035. Not comparable to v0.5 (0.746): v0.6 adds 199 harder natural PROGPedia rows and moves two clusters to dev-gold. Dev-gold macro-F1 0.24 on 45 rows that are still mostly weak labels; the test and test_iid splits have not been scored yet.

## G8 gate status

| Check | Status |
|-------|--------|
| CV beats majority by ≥0.25 | ✅ PASS (margin 0.690) |
| Gold not in train | ✅ PASS |
| Class mass ≤15% | ✅ PASS (max 0.104) |
| Synthetic mass ≤50% | ❌ FAIL (0.91 by weight) |

Synthetic mass is measured by **weight**, so it is high for two reasons. Unaudited natural rows carry low confidence: repair-verified and CodeStream weak rows ship at 0.2 until their LF is audited. And six classes are almost entirely synthetic (ASSIGN_VS_COMPARE, MISSING_BASE_CASE, OTHER_ERROR, RANGE_CHECK, STALE_EXIT, UNINITIALIZED_VAR, WRONG_LOOP_DIR). If every model pre-review verdict were confirmed, the projection is ≈ 0.87. If the 65 train-cluster discovery rows in the review pool (UNINITIALIZED_VAR 29, RANGE_CHECK 27, …) were also human-confirmed, it would be ≈ 0.75–0.81. Reaching ≤ 50% needs real rows in the synthetic-only classes.

## Limitations
- **Population**: C++ competitive programming submissions (Codeforces-style); not representative of classroom or industry code
- **Language**: C++ only; `tl-cpp-v2` taxonomy is not transferable to other languages
- **Label quality**: Most natural labels are weak-rule silver; pre-reviewed by a model but not yet signed by a person; no inter-annotator agreement measured
- **Missing evidence**: SYNTHETIC rows have no CPG/context/runtime evidence from lane; CODESTREAM has no CPG; PROGPedia tier1b rows (pg-\*) have no runtime/tests (47% of PROGPedia rows)
- **Class imbalance**: CPP_ARRAY_BOUNDS is 27% of the dataset; seven classes have no natural rows in train
- **Source/label confound** (reduced): PROGPedia train rows were 100% ARRAY_BOUNDS and are now 58% ARRAY_BOUNDS / 23% INT_OVERFLOW / 17% LOOP_BOUNDARY. Within PROGPedia, INT_OVERFLOW still comes almost only from one problem (00000045, pyramid path counts)
- **Oracle tests**: PROGPedia expected outputs come from agreeing accepted submissions, not the original judge; 222 WA/RE submissions pass every oracle test and are left unlabeled
- **Licensing**: Raw source files are not redistributable; only derived features and labels are in this repository
