# TraceLearn Misconception Dataset — Rayaan's Progress Log

Living log of Lane C work (contracts, recovery, weak labels, merge, training) per
`docs/master_plan_dataset.md` v4.1. **Updated after every milestone.** Branch:
`feat/misconception-dataset-rayaan`.

Status legend: ✅ done (committed) · 🚧 in progress · ⏳ blocked on lane outputs

---

## Milestone summary

| # | Milestone | Status | Commit(s) |
|---|-----------|--------|-----------|
| T1 | G0 recovery: verifier for normalized index vs raw corpora | ✅ | `3fb6a54` |
| T2 | R1 contracts: schemas, enums, taxonomy, label mapping | ✅ | `727f740` |
| T3 | Extractor v0: normalized row extraction from raw corpora | ✅ | `8363041` |
| T4 | G2 parsers: language/AST gate on fixtures + real samples | ✅ | `459b203` |
| T5 | G1 verifier: `verify_dataset.py` + per-class report | ✅ | `822247d` |
| T6 | Problem clustering → `cluster_assignments.csv` (unblocks Eman) | ✅ | `46c6506` |
| T7 | PROGPedia CPG parser + pg detectors + gcc warnings + weak labeler | ✅ | `ea5f0e0`, `8d126e3`, `aa35516`, `7217d08` |
| T8 | `merge_dataset.py`: three-lane merge, dedupe, joins, grouped split, G7 | ✅ | `afddc45` (+ lane-gate fix `c25dff0`) |
| T9 | `train_xgb_misconception.py`: three variants, Layer-3 weights, G8 metrics | ✅ (G8 red at pilot scale — see T9) | `b737b65` |
| T9b | Lane-evidence normalization at merge: mine tier0 embedded code + map tier1a raw evidence | ✅ | uncommitted |
| T10 | Dataset scaffold docs (README, DATASET_CARD, ANNOTATION_GUIDELINE) | ⏳ | — |

All three lanes are merged and on main (PRs #1/#2/#3 merged 2026-10-23);
the real merge (541 → 311 rows) and pilot training ran on this machine
with the G: raw corpus attached. Gates G3/G4/G5b/G6–G10 remain milestone
work; G5 (audit) and G6 (gold annotation) need human labeling.

---

## T1 — G0 recovery verifier (`3fb6a54`)

Verified the normalized index (153,724 submissions) against the raw corpora
mounted at `G:\TraceLearn\Datasets_RAW\`. Established provenance invariants
(counts, per-corpus breakdown, hash spot-checks) so G0 claims are checkable
rather than asserted.

## T2 — R1 contracts (`727f740`)

Single source of truth for the dataset: schema definitions, label enums,
`TAXONOMY_VERSION="tl-cpp-v2"`, `SCHEMA_VERSION="1.0"`, and
`label_mapping.csv` with LF ids `pg-1..pg-4` (and the other LF families).
Confidence caps follow §3.4 (0.60/0.60/0.60/0.55 for pg-1..pg-4), shipping
provisionally until the G5 human audit recalibrates them.

## T3 — Extractor v0 (`8363041`)

Normalized-row extraction from raw corpora into the §3.2 row shape.

## T4 — G2 parsers (`459b203`)

Language/AST parse gate verified on fixtures and real samples.

## T5 — G1 verifier (`822247d`)

`scripts/verify_dataset.py`: scans `data/misconception_dataset/annotations/*.jsonl`,
enforces schema (9 required keys), enum validity, row-id prefixes per source,
label_confidence ∈ [0,1], and orphan checks against the normalized join ids.
`--per-class-report` adds per-(class × source) counts vs the plan's min-accept
floors (UNDER/PASS). **This gate runs before every dataset claim.**

## T6 — Clustering (`46c6506`)

Single-linkage clustering over problem statements →
`data/misconception_dataset/cluster_assignments.csv` with PROGPedia cluster ids.
This is the input for grouped splits (G7: no cluster spans train/test) and
unblocks Eman's tier0 mining. Fallback rule: <41 clusters → coarser threshold.

## T7 — PROGPedia weak-label lane (`ea5f0e0` + `8d126e3` + `aa35516` + `7217d08`)

The full §3.4 pg lane, in four commits:

1. **CPG parser + detectors** (`ea5f0e0`): `scripts/parse_cpg.py` parses the
   tree-sitter CPG export (4467/4467 real files parse) and computes conservative
   detectors: pg-3 = write to fixed-size array with index not statically bounded
   below the size; pg-2 = recursion guard detection (if→return base case OR
   self-call nested under conditional/loop).
2. **Arity fix** (`8d126e3`): measured on real data, all 6 initial pg-2 flags
   were overload delegation (2-arg wrapper calling the 5-arg overload of the
   same name), not recursion. Bare CALLEXPRESSION calls now require arity
   match (call AST children = args; PARAMVARIABLEDECLARATION children = params);
   member calls require receiver exactly `self`/`this`/`super` (79/251 same-name
   member calls are other-object dispatch). Result: pg-2 honest 0 on this corpus.
3. **gcc warnings extractor** (`aa35516`): `scripts/extract_progpedia_warnings.py`
   compiles all 2375 c/cpp rows via WSL gcc 13.3.0 (`-c -O2 -Wall`; NOT
   `-fsyntax-only`, which silently drops `-Wmaybe-uninitialized` dataflow
   warnings). 2364 compile_ok; resumable sidecar cache (gitignored). Measured:
   `-Wparentheses`=0 corpus-wide → pg-1 honest 0; `-Wmaybe-uninitialized`=105
   rows but the CPG use-before-init marker (UNINITIALIZEDVALUE) exists only for
   Java (2052 java / 0 c/cpp/py) → pg-4 structurally 0 on this lane.
4. **Weak labeler** (`7217d08`): `scripts/label_weak_progpedia.py` conjoins pg
   rules over CPG + warnings + verdict + problems.csv context, emitting tier1b
   rows in the §3.2 shape to `annotations/tier1b_progpedia.jsonl` and a
   multi_signal review pool (kept OUTSIDE `annotations/` so verify never scans
   it).

**Real-data yield (full corpus, both raw halves; plan expected ~100 pg-3):**

| LF | rule conjunction | rows | confidence |
|----|------------------|------|------------|
| pg-1 CPP_ASSIGN_VS_COMPARE | verdict≠ACCEPTED ∧ -Wparentheses ∧ assign-in-cond feeds output | 0 | — |
| pg-2 CPP_MISSING_BASE_CASE | RE ∧ unguarded recursion | 0 | — |
| pg-3 CPP_ARRAY_BOUNDS | RE ∧ unbounded fixed-size array write | **335** | 0.60 silver |
| pg-4 CPP_UNINITIALIZED_VAR | verdict≠ACCEPTED ∧ -Wmaybe-uninitialized ∧ use-before-init marker | 0 | — |

`verify_dataset.py --per-class-report`: **G1 PASS** — 335 rows, 0 orphans,
enums clean, 153,724 join ids. All rows silver (`label_source=weak_rule`),
deterministic `pipeline_run_id=label_weak_progpedia/1.0.0`,
`problem_cluster=null` until T8 merge joins cluster ids.

Notable: pg-3 is the only rule with real yield on PROGPedia; the plan's
multi-signal review pool is empty (no row fires two rules). Class balance for
the remaining LF classes depends on tier0 (Eman) and tier1a (Umaima) — G0
pool was ruled CODESTREAM+PROGPedia only, and PROGPedia itself covers just
these pg rules.

---

## T8 - Three-lane merge (`c25dff0` + `afddc45`)

`scripts/merge_dataset.py`: G1-validates every lane row → joins
`label_mapping.csv` (family/modeled/hard3; pre-registered `merged_into`
folds execute as a join) → resolves each row's own code from the raw
corpus (one streaming pass per CSV) → token 5-gram Jaccard ≥ 0.8 dedupe →
cluster/split join → G7 leakage checks → `labels.jsonl`, `features.csv`,
`splits.csv`, `merge_report.json`.

**Real run: 541 rows → 311 kept** (train 274 / test 33 / dev_gold 4;
SYNTHETIC 128, PROGPEDIA 150, CODESTREAM 33; code uncovered 0).

The 230 dropped twins were verified by hand, not assumed:
- 185 PROGPedia — genuine successive-attempt twins (sampled J=0.81–0.98,
  684 real J≥0.8 pairs; e.g. J=1.000 resubmissions);
- 23 CodeStream — same-split duplicates (test↔test, dev↔dev, train↔train);
  6 held-out rows dropped against their own split's twin, never across;
- 22 synthetic — duplicate emissions: `generate_mutants.py` applies a form
  deterministically to one seed, so same (seed, form, problem, label) with
  identical runtime IS the same mutant re-emitted (row_id embeds a
  process-randomized `hash(cls)`, so resume runs cannot dedupe by id —
  flagged for lane A).

Structural G7 all zero (cross-split twins independently recomputed by
hand = 0); merged output re-passes G1 (311 rows, 0 issues).

Rulings:
- Only `tier*.jsonl` are lane inputs; a previous run's `labels.jsonl` is
  never re-merged (and the lane gate now excludes it by name — `c25dff0` —
  so per-class floors cannot double-count).
- SYNTHETIC rows have no own code (source_record_id is the shared seed):
  they dedupe by identity `(seed_ref, mutation_op, problem_id, label)`;
  code MinHash applies only to CODESTREAM/PROGPedia rows.
- Exact pairwise Jaccard replaces MinHash at pilot scale (strictly
  stricter, no candidate misses, identical threshold semantics); revisit
  LSH banding at ≥1e5 rows.
- Structural violations raise before any output; leakage findings are
  reported, never silently repaired.

Findings surfaced in `merge_report.json` (loud, not papered over):
- PSI train-vs-test drift on `tests.total`/`static.loc`/`tests.passed`
  (max 3.78) = pool asymmetry: the frozen test split is CodeStream-only
  while train mixes pg+syn+cs. Plan's PSI<0.2 gate is specced for
  train/val and runs at T9 — the merge's probe is informational.
- Feature availability matrix: **tier1a `static=null`, `cpg`/`context`
  absent**; tier0 `tests`/`cpg`/`context` empty; tier1b runtime/tests
  key-present-but-NaN.

## T9 - XGBoost trainer, pilot run (`b737b65`)

`scripts/train_xgb_misconception.py` (§11.5 R6 → G8): in-script
`assert gold ∉ train` (dev-gold clusters disjoint); Layer-3 weights
`w = w_balance × w_confidence × w_source` clipped [0.1, 10]; synthetic
multiplier CV-selected on train-only StratifiedGroupKFold folds; three
variants (full / common=static+warnings / masked=lf_inputs→NaN on weak
rows, informational with disclosed train/test mismatch); ONE global
threshold + temperature on dev-gold only (isotonic banned; with 4
dev-gold rows the calibrator records the explicit too-small fallback).
Deterministic (seeded, single-threaded hist). Artifacts in
`data/misconception_dataset/models/`.

**Pilot G8 status — honest, gates red:**
- PASS: gold-not-in-train · class-mass ≤15% · weight clip · artifacts;
- **FAIL: CV macro-F1 0.102 vs majority 0.069 (margin 0.033, needs ≥0.25)**;
- **FAIL: synthetic mass 0.89 > 0.50**.

Root causes (data, not code):
1. **tier0 carries no canonical features except `static.loc`** — its
   blocks are `static={source_code, sha256, loc}`, raw gcc text in
   `warnings.compile_warnings`, non-canonical `runtime={tests_passed,
   tests_failed, tests_total, sanitizer_ok}`, empty `tests`/`cpg`/
   `context`. The 106 synthetic train rows therefore expose ONE number
   each: ARRAY_BOUNDS learns well (OOF F1 0.943), the other 10 classes
   have recall 0 and the margin cannot materialize. **Lane-A feature
   mining of mutant rows is the blocker for G8/G3.**
2. At pilot scale non-synthetic mass sits almost entirely in
   ARRAY_BOUNDS (150 pg + 18 cs of 168 real rows), making the ≤50%
   synthetic-mass and ≤15% class-mass caps arithmetically mutually
   exclusive — both need the full real-row supply (≥5,300 weak rules,
   decoy pool). Caps are recorded in `metrics_v1.json`, never tuned into
   green.

Masked == full OOF was verified as genuine coincidence (masking does
introduce 150 NaNs on real data; predictions merely coincide), not a
wiring bug.

## T9b - Lane-evidence normalization (fixes T9 root cause 1)

**Root cause (measured, not inferred).** `merge_dataset.flatten_features()`
read canonical short names only, but the lanes emit their evidence in their
own vocabulary. Before this fix, `features.csv` carried:

| source | canonical columns populated (of 87) | what survived |
|---|---|---|
| SYNTHETIC | **1** | `static.loc` only |
| CODESTREAM | **3** | `tests.total`, `tests.passed`, `runtime.stack_overflow` (coincidental key matches) |
| PROGPEDIA | 63 | already normalized by its lane |

So the model was not under-tuned — it was starved. The merge contract
already allows backfilling blocks a lane shipped raw (`FEATURE_SCHEMA.md`
§v0 interface).

**Fix.** New `tracelearn_features/normalize.py`, called from
`merge_dataset.merge()` after dedupe (step 6b), before flatten/PSI:

- tier0: `static.source_code` → full `static` block via the pinned
  extractor; `warnings.compile_warnings` gcc text → canonical warning
  counts; `runtime.tests_{total,passed,failed}` → `tests.*`;
- tier1a: merge-resolved own code → `static`; raw `-Wflag` count keys →
  canonical warnings; sandbox runtime (`any_crash` / `sanitizer` /
  `valgrind`) → canonical runtime; `status` test results → `tests.*`
  (presentation failures counted as failed, not wrong-answer);
  `statement_chars` / `tests_total` → `context`;
- tier1b: untouched (already canonical; a null there is a real lane gap and
  stays visible in the availability report).

Discipline: lane-supplied values are never overwritten; missing evidence
stays NaN (an empty CodeStream warnings dict means "not mined", not
"zero"); no label-derived metadata (`mutation_op`, `seed_ref`) is used.
Tests: `tests/test_normalize_lane_features.py` (13) + two merge
integration tests.

**Coverage after the fix** (same 311-row merged dataset):

| source | canonical columns populated | added |
|---|---|---|
| SYNTHETIC | **47** | static (20), warnings (21), tests (5) |
| CODESTREAM | **68** | static (20), warnings (20), runtime (12), tests (7), context (3) |
| PROGPEDIA | 63 | unchanged |

Still honestly NaN: tier0 `cpg`/`context`/`runtime` (the lane never carried
that evidence; sanitizer detail was not persisted in the proofs), tier1a
`cpg` (no CPG export for CodeStream), and `tests.boundary_fail_count`
(no per-test boundary metadata).

**Retrained metrics (seed 7, 274 train / 4 dev-gold):**

| metric | before T9b | after T9b |
|---|---|---|
| CV macro-F1 (grouped) | 0.1024 +/- 0.0155 | **0.1783 +/- 0.0660** |
| majority baseline | 0.0691 | 0.0691 |
| CV margin | 0.0333 | **0.1092** |
| OOF macro-F1 (full) | 0.1125 | **0.1921** |
| OOF macro-F1 (common) | 0.1125 | **0.2241** |
| ECE (full, OOF) | 0.2678 | 0.2287 |

Per-class OOF now: ARRAY_BOUNDS 0.923, ASSIGN_VS_COMPARE 0.571,
OFF_BY_ONE 0.235, STALE_EXIT 0.267, LOOP_BOUNDARY 0.091; five classes
still 0 (INT_OVERFLOW, MISSING_BASE_CASE, RANGE_CHECK, UNINITIALIZED_VAR,
WRONG_LOOP_DIR). G8 still **FAIL** on CV margin (0.109 < 0.25) and
synthetic mass (0.89 > 0.50); gold-not-in-train, class-mass and weight
clip PASS.

**Why the remaining reds are not fixable in the merge/trainer:** every
zero-F1 class is confined to one or two problem clusters
(MISSING_BASE_CASE and WRONG_LOOP_DIR: `clu-000` only; RANGE_CHECK:
`clu-000` + one row). Grouped CV by cluster therefore holds the *only*
cluster containing the class out of fold-train, so OOF F1 is structurally
0 regardless of feature quality. Fixing it needs lane-A supply across
clusters (more real/mutant rows per class), not model tuning. Synthetic
mass is the Layer-3 weight formula (synthetic confidence 0.93 vs
weak-label caps 0.2-0.6); the plan says caps are recorded, never silently
enforced.

---

## Rulings & decisions log (binding for this lane)

- G0 labeled pool = CODESTREAM + PROGPedia only; G0b/G0c explicit nulls.
- Certain = exec-verified synthetic + repair_verified + human; silver = weak_rule ∧ synthetic-unverified.
- Single-linkage clustering; fallback split when <41 clusters.
- DEADLYSIGNAL ≠ stack-overflow evidence.
- **Java is excluded** from the pg labeling lane (user ruling); pg rules cover C/C++, Python gets pg-2 only.
- pg-3 literal rule: LITERAL value = token, else code; `#define` macro sizes resolved from sibling source.
- Single-firing exclusivity: multi-rule rows go to the review pool, not annotations (both=0 measured).
- `label_confidence` ships at §3.4 caps, provisional until G5 audit.
- `pipeline_run_id="label_weak_progpedia/1.0.0"` (deterministic); `problem_cluster=null` until T8.
- Multi_signal review pool lives at `data/misconception_dataset/review/multi_signal.jsonl` (outside verify's scan dir).
- Raw corpus spans TWO dirs (`progpedia/` and `progpedia (1)/`); labeler resolves per-row via `source_code_path`. Detector measurements on one dir alone undercount (98 vs 335 pg-3).
- **G1 proof-join** (`095878c`): template SYNTHETIC orphans are excused iff a committed mutant proof matches `(problem_id, mutation_op, label)` — evidence-based, never blanket; all other sources keep the strict normalized join.
- **Cluster extend** (`e879f2e`): frozen CodeStream rows byte-stable; new problems join a frozen cluster's split (leakage-safe); all-new clusters are train (silver = training material; dev/test budget stays CodeStream's gold); a union cluster spanning frozen splits raises — never silently re-split.
- **Dedupe basis split** (T8): code-bearing rows by token 5-gram Jaccard ≥0.8 (keep-first by row_id); SYNTHETIC rows by identity `(seed_ref, mutation_op, problem_id, label)` — seed code must never drive mutant dedupe.
- **G7 exit semantics** (T8): structural leakage (cluster/seed straddles, cross-split twins) fails the merge CLI; PSI drift is reported loudly but non-gating at merge time (its train/val gate runs at T9/T10).
- **Lane gate scans inputs only** (`c25dff0`): `verify_dataset` excludes the merge's derived `labels.jsonl` — else per-class floors double-count.
- **Trainer discipline** (T9): gold-not-in-train asserted in-script; ONE global threshold + temperature on dev-gold only (isotonic banned; <10 dev-gold rows → explicit uncalibrated fallback, never an overfit calibrator); Layer-3 caps recorded as findings, never enforced by silent re-weighting.

## Environment notes

- WSL Ubuntu gcc/g++ 13.3.0 (12 cores) substitutes for the host compiler; Docker daemon down (real sandbox runs blocked → build/test on fixtures only).
- Manifests/scripts write `newline="\n"` — CRLF broke bash `[ -f ]` on every path (exit 127); regression test added.

## T9c — Schema v1.1, semantics extractor, XGBoost fixes, best variant (`feat/xgb-model-improvements`)

Branch: `feat/xgb-model-improvements` (Eman, 2026-10-24). Eight commits:

### `dcbb231` — Semantics block wired into extractor interface

`FEATURE_BLOCKS["semantics"]` (15 int features) was already in `schema.py` and
`tracelearn_features/semantics.py` was written, but `extract_features()` in
`extractor.py` was not returning the block — breaking `test_extract_features.py`
(3 failures). Fixed by importing `extract_semantics` and adding `_compute_semantics(source)`
between the `cpg` and `context` blocks in the return dict. Empty source degrades
to `available=False` / NaN per the §6 null policy, never raises.

Also removed two pre-existing unused variables flagged by ruff (`comment_lines`, `indent`).

### `82f5d71` — XGBoost 2.x `save_model()` compatibility

XGBoost ≥2.0 changed `XGBClassifier.save_model()` to call `self._get_type()` via
the sklearn API, raising `TypeError: _estimator_type undefined` when the model
was fit without the full sklearn initialization path. All four model saves now
use `model.get_booster().save_model(path)` (native booster format, works across
all 2.x releases). Fixed 9 failing tests in `test_train_xgb_misconception.py`.

### `a1aea62` — Best variant model + 3-repeat CV

First run of `train_xgb_misconception.py --cv-repeats 3` with the `best` variant
(`BEST_PREFIXES = static + warnings + semantics`). Saves `xgb_best_v1.json`.
Metrics below are **pre-semantics** (features.csv predates the extractor fix;
semantics block all-NaN until merge reruns with submissions.csv):

| variant | CV macro-F1 | G8 margin |
|---------|-------------|-----------|
| full    | 0.174 ± 0.063 | 0.105 |
| common  | 0.200 ± 0.097 | — |
| best    | 0.200 ± 0.097 | — (same as common: semantics NaN) |

Expected after merge rerun with semantics: best CV ~0.232 (prototype result).
G8 margin target = 0.25; current = 0.105 (FAIL — honest, not tuned).

**Blocked on**: `submissions.csv` + raw source files on Rayaan's machine for
`merge_dataset.py` rerun, and WSL g++ for `expand_mutants.py` pilot.
All 114 targeted tests pass (now 298 suite-wide). Ruff clean.

### `8e52c08` — Skip raw-corpus path test when G: drive not mounted

`test_extract_warnings.py::test_build_jobs_resolves_path_under_raw_root_and_flags_missing`
was failing on any machine without G: drive mounted. Added `@_raw_missing`
pytest skip guard (`pytest.mark.skipif(not Path(RAW).exists(), ...)`). Test
now skips cleanly on dev machines, still runs on the dataset machine.

### `4af2664` — Semantics integration tests (NaN contract + source computation)

Two tests in `test_extract_features.py`:
- `test_semantics_block_computed_from_source`: verifies `loop_lt`, `init_zero`,
  `increment` set from a real source string; `assign_in_cond` and `recursion` = 0
- `test_semantics_block_nan_for_empty_source`: all 15 semantics ints are NaN
  for empty source; confirms no `available` gate exists in the semantics block

### `e9530fa` — Edge-case tests: recursion, base_case, idx offsets

- `test_semantics_recursion_and_base_case`: fib(n) → recursion=1, base_case=1, loop_lt=0
- `test_semantics_idx_offset_features`: a[i-1]/a[i+1] → idx_minus1=1, idx_plus1=1

### `0401372` — Cover assign_in_cond and decrement flags

`test_semantics_assign_in_cond_and_decrement`: `while(n--)` + `if(x=*p++)`
triggers assign_in_cond=1, decrement≥1.

---

## T9d — Post-semantics retrain on 448-row dataset (`main`, 2026-10-24)

Pulled Rayaan's commit `1d866ee` (pilot mutant expansion: 8 new SYNTHETIC rows
for CPP_MISSING_BASE_CASE + CPP_RANGE_CHECK, re-merge to 448 rows). Re-ran
`train_xgb_misconception.py --cv-repeats 3`. Semantics block now populated from
real source for SYNTHETIC and CODESTREAM rows.

| variant | OOF macro-F1 | ECE |
|---------|-------------|-----|
| full    | 0.729       | 0.063 |
| common  | 0.754       | 0.046 |
| **best** | **0.757**  | 0.066 |

CV (3×StratifiedGroupKFold): **0.704 ± 0.048** vs majority 0.053 (margin **0.651**).
Synthetic multiplier CV-selected at 1.0 (all grid values ≥0.69; synthetic rows
now carry full quality semantics evidence, down-weighting hurts).

**G8 status:** gold-not-in-train ✅ · CV-margin ✅ · class-mass ✅ · **synthetic mass FAIL** (0.59 > 0.50)

Synthetic mass failure is a data constraint: 265/448 rows are SYNTHETIC. Cannot
be fixed by reweighting — cap is on weighted mass, not row count, and the
synthetic multiplier CV-selects to 1.0. Fix requires more real labelled rows
(G5 audit → G6 gold annotation) or a larger PROGPedia/CODESTREAM weak-label
run.

Commits: `0cec479` (metrics) · `e895bc8` (full+masked) · `22197e3` (common) · `3d2dc9b` (best)

---

## Next actions

1. **Full expansion** for 9 structurally starved classes — `expand_mutants.py`
   full run (needs Rayaan's G: drive + WSL g++). Classes: CPP_MISSING_BASE_CASE,
   CPP_RANGE_CHECK, CPP_WRONG_LOOP_DIR, CPP_INT_OVERFLOW, CPP_STALE_EXIT,
   CPP_UNINITIALIZED_VAR, CPP_ASSIGN_VS_COMPARE, CPP_LOOP_BOUNDARY, CPP_OFF_BY_ONE.
2. **T10** dataset scaffold docs (README, DATASET_CARD; adopt Umaima's
   ANNOTATION_GUIDELINE.md).
3. **G5 audit** (human, ≥50 fires per rule) to move silver → certain and
   set final confidences; **G6** gold annotation (needed before any
   test-gold evaluation and before calibration is meaningful).
4. **Reduce synthetic mass**: run `extract_progpedia_warnings.py` to pull
   more real PROGPEDIA rows into the dataset (PROGPedia weak labels on
   10k+ submissions would shift balance below 50%).
