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
| T8 | `merge_dataset.py`: concat, MinHash dedupe, joins, grouped split, G7 | 🚧 next | — |
| T9 | `train_xgb_misconception.py` baseline on fixtures | ⏳ after T8 | — |
| T10 | Dataset scaffold docs (README, DATASET_CARD, ANNOTATION_GUIDELINE) | ⏳ | — |

Real merge/train and gates G3/G4/G5b/G6–G10 remain blocked on Eman's
`tier0_mutants.jsonl` and Umaima's `tier1a_codestream.jsonl` + sandbox_runner.
All independent Rayaan work proceeds in the meantime.

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

## Environment notes

- WSL Ubuntu gcc/g++ 13.3.0 (12 cores) substitutes for the host compiler; Docker daemon down (real sandbox runs blocked → build/test on fixtures only).
- Manifests/scripts write `newline="\n"` — CRLF broke bash `[ -f ]` on every path (exit 127); regression test added.

## Next actions

1. **T8** `scripts/merge_dataset.py`: schema validation, concat tiers, MinHash
   dedupe, join cluster ids, grouped split (G7), gate checks — on fixtures.
2. **T9** `scripts/train_xgb_misconception.py` baseline on fixtures.
3. **T10** dataset scaffold docs.
4. On lane outputs arriving: real merge, G3/G4/G5b/G6–G10 gates, G5 audit
   pass to set final confidences.
