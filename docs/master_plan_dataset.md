# TraceLearn Misconception Dataset — Master Plan (v4.1)

> **Status:** execution-ready · **Date:** 19 Oct 2026 · **Version:** v4.1 — supersedes v1–v4; incorporates the 17-point review (§17) **and** its follow-up arithmetic/design audit. Every total in this document is derived from the single floor table in §8.
> **Owners:** Rayaan (ML lead) · Eman (Lane A) · Umaima (Lane B) · **plus one external annotator** (supervisor/TA/classmate, §13.4)
> **Governing skills:** writing-plans · test-driven-development · verification-before-completion (every gate)

**Goal:** Build a class-balanced C/C++ misconception dataset (taxonomy `tl-cpp-v2`: **10 misconception classes + `OTHER_ERROR` = 11 modeled labels**; `NO_MISCONCEPTION` handled deterministically, not modeled) with a locked human gold test set (**220 commitment / 150 floor**) plus a 60-item dev-gold calibration set, then train an XGBoost classifier that predicts which misconception a failing student submission shows.

**Architecture:** One shared sandbox harness (Umaima) and one shared feature library with a **Week-0 v0 release and fixed interface** (Rayaan) — no per-lane reimplementation, no lane blocked on another. Three people each own one raw source's *labeling* end-to-end; JSONL files merge via a frozen, fully-enumerated schema. Leakage controlled by problem-cluster grouping, code dedup, seed grouping, train-side-only mining, and decoy rows. Normalized tables are read-only inputs; new artifacts live in `data/misconception_dataset/`.

**Tech Stack:** Python (3.14 if xgboost/shap/pandas wheels verified, else 3.12 — checked Week 0) · pandas · scikit-learn · xgboost · shap · pinned Docker sandbox (g++ + clang + Valgrind) · pytest · clang-format.

**Spec chain:** this file ← FYP Blueprint §9 + Appendix B ← Dataset Agent Brief ← AUDIT_INVENTORY ← the 17-point review + follow-up audit, folded into §1–§17.

---

## 1. Why this project exists

TraceLearn diagnoses programming misconceptions using hand-written rules with frozen weights. **V1 research question:** does a learned model diagnose misconceptions better than frozen rules *on a single submission*? ("Does attempt history help?" is V2 — §13.6.) Pipeline: student submits failing code → platform runs it → feature vector → XGBoost outputs one of 11 modeled labels + confidence → targeted hint. Deterministic pre-branches handle the cases no model should see: **all tests pass** → `NO_MISCONCEPTION` (no model); **compile error** → compile feedback (no model); **timeout without crash** → infinite-loop hint (no model). Low confidence → rule-engine fallback. Today no misconception labels exist in real data — this plan creates them.

## 2. Data inventory

Raw data at `G:\TraceLearn\Datasets_RAW` (read-only). Normalized index maps raw paths ↔ `submission_id` ↔ `problem_id`.

| Source | Location | Code | Statement | Tests | Verdict | Honest contribution | Lane |
|---|---|---|---|---|---|---|---|
| **C++ diagnostic bank** (~86 reference solutions + variants, 54 problems, 305 tests) | repo | ✅ | ✅ | ✅ | designed | Mutation seeds (≤3 mutants/seed); verified against bank tests | **Eman** |
| **CodeStream** (46 problems, 5,482 subs, 202 users) | G: CSVs | ✅ inline | ✅ + test JSON | ✅ embedded | ✅ verdict + trace | Real rows executed against own tests; Accepted = seeds + executor sanity; wrong→Accepted pairs = reverse-mutation mining (**train-side clusters only**); gold source; discovery mining | **Umaima** |
| **PROGpedia** (2 copies, 17+1 problems, ~9,100 subs) | G: | ✅ C/C++/Java | ✅ | ❌ | ✅ verdict dirs | Weak rows via explicit conjunctions (§3.4); behind a keep/drop rule (§9.3-R4b) | **Rayaan** |
| **Project_CodeNet** (70 problems, 237,512 files) | G: | ✅ | ✅ HTML | ❌ | ❌ stripped | **Excluded from labels** (§2.1) | — |
| Normalized index (`submissions.csv` 153,724 · `problems.csv` 4,035 + 7,910 sample tests) | repo | — | ✅ | — | — | Read-only lookup + statements for every lane | shared |

### 2.1 Why CodeNet is excluded

No verdicts, no tests on disk: we cannot know if a submission is wrong, nor execute it to learn why. Regex-guessing 139k labels would drown the high-quality rows. Accepted-looking rows serve only as **seeds (after human spot-check) and executor sanity material** — they receive no labels of any kind. Tier 1c possible if the small upstream `metadata/` folder is later downloaded (wrong rows only, warning-unambiguous conjunctions, ≤0.65).

### 2.2 The five never-downloaded sources

McMining (67-misconception taxonomy — cross-check `tl-cpp-v2` against it later), ProgFeed, CSEDM, HELP-DKT, FalconCode. No local data → nothing to label today; they matter for the V2 history-aware model.

## 3. Taxonomy `tl-cpp-v2` — 10 misconception classes + OTHER_ERROR (11 modeled labels)

### 3.1 Operational (mutually exclusive) definitions — cause, not symptom

| # | Class | Student's belief | Operational definition (cause) | Signature evidence |
|---|---|---|---|---|
| 1 | `CPP_LOOP_BOUNDARY` | "The loop should include its upper bound" | **The loop-test comparison operator is the cause** (`<=` vs `<`, `< n+1`, `!= n+1`) | boundary test diverges ±1; fixing only the operator fixes all tests |
| 2 | `CPP_OFF_BY_ONE` | "Index/size or initial-value arithmetic off by one" | **The cause is index/count arithmetic** (`a[i+1]`, start at 1, `n` vs `n-1`), operator correct | ±1 diff; ASan at exact-size index with correct loop operator |
| 3 | `CPP_ARRAY_BOUNDS` | "The array is big enough" | **Out-of-bounds by more than one element, or undersized fixed array** | ASan overflow ≥2 past end; gcc `-Warray-bounds` |
| 4 | `CPP_UNINITIALIZED_VAR` | "Declaring gives it zero" | Use-before-init of declared-but-unset variable | gcc `-Wmaybe-uninitialized` at `-O2` ∧ **Valgrind memcheck** report (default detector — clang MSan is optional only, §9.2-U0) |
| 5 | `CPP_INT_OVERFLOW` | "int holds any number" | Overflow-prone arithmetic is the failure cause | UBSan signed-overflow; crash/timeout only on large inputs |
| 6 | `CPP_MISSING_BASE_CASE` | "Recursion always stops" | Unguarded self-call is the failure cause | stack-overflow crash growing with input size |
| 7 | `CPP_ASSIGN_VS_COMPARE` | "`=` and `==` do the same job" | Assignment operator inside a condition is the cause | gcc `-Wparentheses` ∧ AST assignment-in-condition node **where the assigned variable is later used in output-affecting computation** (two distinct signals, §3.4) |
| 8 | `CPP_WRONG_LOOP_DIR` | "Backwards traversal gives the same result" | Decrementing/reversed iteration where task requires ascending | order-reversed output; AST comparison vs reference solution |
| 9 | `CPP_RANGE_CHECK` | "Validating outside the valid range" | Input validation rejects valid or accepts invalid range | failing boundary-pattern tests |
| 10 | `CPP_STALE_EXIT` | "The exit condition updates itself" | Exit condition depends on a variable never updated in the loop | dataflow: loop-condition vars unassigned in body; premature/late exit |
| 11 | `CPP_OTHER_ERROR` | (something else went wrong) | Failing submission with **no** taxonomy signature — **human-confirmed real rows and decoy rows only** (§5-E1d, §8-Layer 4) | executed failure + absence of signatures + human confirmation |
| — | `NO_MISCONCEPTION` | (correct) | **Not modeled** — deterministic branch (§1) | `tests_passed == tests_total` |

**Fixed decisions:** NO_MISCONCEPTION never enters the classifier (trivially separable; absent from wrong-only gold; inflates macro-F1). **"Hard-3" = classes 8, 9, 10**, used everywhere; **class 4 joins the real-data discovery pipeline** (§13.5) because it has no natural real-data LF path but does need real gold items. **Families** (in `label_mapping.csv`; fine + family metrics both reported): `Boundary` (1,2,3) · `ControlFlow` (6,8,10) · `Data` (4,5) · `Logic` (7,9) · `Other` (11). *(v4's stray `CPP_CONTROL_FLOW_OTHER` is removed; the fallback for an unvalidated hard-3 class is: dropped from fine-grained modeling, reported at family level only — §13.5.)*

### 3.2 Labeling rules (binding on all lanes)

1. One **primary label** per row (cause-based); extras in `secondary_labels`.
2. Every label carries `label_source` ∈ {`synthetic`, `weak_rule`, `human`, `repair_verified`} and `label_confidence` (§3.5 — measured).
3. **No forced labels.** Ambiguous → `UNCERTAIN` → review pool.
4. `synthetic` counts only with `verified_by_execution=true` + stored proof. `repair_verified` rows (§5-U2) also count as certain.
5. Tie-break precedence: **"label the misconception that explains the first divergent test."**
6. Class merges decided by pre-registered rules (§9.0-G3), executed as a `label_mapping.csv` join (rows store `mutation_op`, never the derived class).

### 3.3 Multiple misconceptions in one program

- **Design-time (synthetic):** clean seed + exactly one operator + collision check across all 11 signatures → zero multi-misconception synthetic rows by construction.
- **Evidence-time (weak):** one LF fires → label; several for the same class → one label; several for **different** classes → `multi_signal` review pool (human promotion or `UNCERTAIN`; never force-picked). Pool size reported weekly.
- **Human (gold):** checkboxes for all plausible classes; primary per the first-divergent-test rule; secondaries recorded; undecidable → `UNCERTAIN`.
- **V2 escape hatch:** `secondary_labels` populated from day one; multi-label upgrade = pure re-training; `multi_signal` pool is its natural test set.

### 3.4 PROGpedia labeling rules (explicit conjunctions; each needs two distinct signals)

| Rule | Required conjunction | Class | Confidence cap |
|---|---|---|---|
| pg-1 | verdict ≠ ACCEPTED ∧ `-Wparentheses` ∧ AST assignment-in-condition where assigned var feeds output computation | ASSIGN_VS_COMPARE | 0.60 |
| pg-2 | verdict = RUNTIME_ERROR ∧ recursion without guard (AST) | MISSING_BASE_CASE | 0.60 |
| pg-3 | verdict = RUNTIME_ERROR ∧ array write beyond fixed declared size (AST) | ARRAY_BOUNDS | 0.60 |
| pg-4 | verdict ≠ ACCEPTED ∧ `-Wmaybe-uninitialized` ∧ use-before-init AST path | UNINITIALIZED_VAR | 0.55 |

*(v4's pg-3 requiring "output pattern" evidence is removed — PROGpedia has no tests or outputs; pg rules use only syntax, warnings, and verdict.)* Everything else stays unlabeled. Each rule has an `lf_inputs` registry entry and joins the ≥50-fire precision audit pool (§3.5).

### 3.5 Confidence is measured, not assigned

- High-volume LFs need **≥50 audited fires, ≥90% precision** (30 was too few).
- `label_confidence` = **Beta(1,1) posterior lower 80% bound** of audited precision. Source caps hard: CodeStream 0.85 / PROGpedia 0.60 / weak-OTHER 0.60.

## 4. How original code + problem statements are used together

Statements come from the repo's normalized `problems.csv` — nobody re-ingests raw HTML/markdown (fallback-only for the ~26 `empty_statement` gaps: drop the row, log the reason).

| Source | Code is used for… | Statement is used for… |
|---|---|---|
| Bank (Eman) | mutation seeds (≤3/seed; class-specific relaxation possible after G0c audit) | matching mutants to test sets; context features |
| CodeStream (Umaima) | execution vs embedded test JSON; Accepted = seeds + sanity; wrong→Accepted diffs = **reverse-mutation mining, restricted to train-side clusters** (§13.4 split budget); repair-and-rerun verification (§5-U2) | context features; gold forms; reference-solution AST comparison (class 8 detector) |
| PROGpedia (Rayaan) | static/warning features + CPG graph/token features; verdict dirs | context; human spot-checks |

### 4.1 Do we need to generate problem statements / questions?

**For the dataset: no** — all needed statements exist and are normalized (bank 54 + CodeStream 46 + PROGpedia 17 via `problems.csv`). Training rows come from executing existing code against existing tests. **For the platform (targeted practice): eventually, via the bank's proven pipeline** (`build_cpp_diagnostics.py` → `verify_cpp_diagnostics.py`; a generated problem enters the bank only with a green verification report). Optional V2; nothing here blocks on it.

## 5. Work division — three lanes, shared harness, shared library (no lane blocked)

**Shared infrastructure (Week 0, 5 days):**
- **`sandbox_runner` — Umaima owns, everyone imports.** One contract: `(code, lang, tests) → {runtime, tests, warnings}`. Spec in §9.2-U0. **Ship a minimal executor on day 2** (compile + run + capture) before hardening to full isolation — so Eman is never blocked.
- **`tracelearn_features` v0 — Rayaan owns, released end of Week 0 with a fixed, versioned interface** (this closes v4's dependency hole: lanes compute their own JSONL features from day one via this v0; v1 hardening comes later). Time-boxed: if v0 slips past Week 0, the fallback is lanes ship raw-evidence blocks only and Rayaan backfills features at merge (schema allows lane feature blocks to be null and filled by the library post-concat).

### Eman — Lane A (synthetic)
**Owns:** `scripts/generate_mutants.py`, `annotations/tier0_mutants.jsonl`
- **E1 — Operators from real students (reverse mutation):** mine CodeStream wrong→Accepted attempt pairs — **train-side clusters only** (§13.4; Week-0 cluster assignment precedes mining, so test-side error patterns never shape operators) — diff, cluster, adopt the most common real fixes as operators, cluster frequency = sampling weight. **≥4 surface forms per operator.**
- **E1d — Decoy operators:** surface pattern present (e.g., legitimate `i <= n`), failure caused by a non-taxonomy bug → label `OTHER_ERROR`. **Generate ≥100 per class (≥1,100 total), then subsample** so OTHER_ERROR's training contribution stays at its table target (§8) — decoys are also the raw material for E5 audits and future work, so the full generated pool is archived even when not trained on.
- **E2 — Verifier:** seeds pass pre-mutation 100% · 20-item known-clean control rejected 0-FF · all-11-signature collision check · proof artifacts stored · clang-format normalization (randomized presets).
- **Constraints:** ≤3 mutants/seed (relaxable to 5 per class after G0c if seed-starved, logged) · bank-seed share capped **as a guard only** (G0c will likely show the ~86 bank seeds are a minor source regardless — ~260 mutants max — so the binding constraint is CodeStream Accepted seeds, audited in G0c).

### Umaima — Lane B (CodeStream) + harness owner
**Owns:** `sandbox_runner` (Week 0), `scripts/label_weak_codestream.py`, **`scripts/repair_verify.py`**, `scripts/build_annotation_forms.py`, `annotations/tier1a_codestream.jsonl`
- **U1 Executor correctness:** ≥95% of Accepted C/C++ compile · ≥98% of compiled Accepted pass all tests · ≥95% of Wrong-Answer fail ≥1 test · sanitizer/Valgrind passes complete on ≥90% of compilable submissions.
- **U2 LFs + repair-and-rerun:** unit-tested must-fire/must-not-fire fixtures · single-firing rule with multi-signal routing · ≥50-fire audits ≥90% · Beta-bound confidence. **New (review-suggested, adopted): repair verification** — when an LF fires a class on a real row, apply the *inverse* operator and re-run tests; if all pass, the row is **`repair_verified`** and counts toward the **certain floor** (§8-Layer 4). This upgrades a large share of silver rows to certain *and* independently double-checks Eman's operators.
- **U3/U4/U5:** pilot **150 real rows** (§9.0-G3) → scale (§8) → gold + dev-gold forms (§13.4).

### Rayaan — Lane C (PROGpedia) + contracts + merge + training
**Owns:** `tracelearn_features` (v0 Week 0), `scripts/parse_cpg.py`, `scripts/label_weak_progpedia.py`, `scripts/merge_dataset.py`, `scripts/verify_dataset.py`, `scripts/train_xgb_misconception.py`, `scripts/migrate_schema.py`, `annotations/tier1b_progpedia.jsonl`, `label_mapping.csv`, `FEATURE_SCHEMA.md`
- Week 0: contracts + fixtures + feature-library v0 · Week 1: verify + own lane · Week 2: pilot integration + ablation suite · Weeks 5–6: merge, splits, train, evaluate, G10.
- **Backups (bus factor):** Umaima ← merge/training; Eman ← `verify_dataset.py`. CI runs pytest on golden fixtures.

### Anti-collision matrix
CodeStream labels: **Umaima only** (Eman reads seeds + attempt diffs, never writes) · PROGpedia: **Rayaan only** · Bank + mutants: **Eman only** · Matrix/splits/model: **Rayaan only** · Statements: all read-only. Row-ID prefixes `mut-*` / `cs-*` / `pg-*`.

## 6. Frozen schema contract (v1.0, fully enumerated at Week-0 freeze)

`FEATURE_SCHEMA.md` at freeze contains: **explicit list of every feature name and type** · the full warning enumeration · runtime/test/CPG/context fields · the **`tracelearn_features` v0 interface signature** (so lanes can compute features from day one) · the **label-defining feature registry** (`lf_inputs` per LF and operator).

Row shape (JSONL):

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

`null`/NaN = "source cannot provide it", never 0 · `meta` is never a feature · **evolution:** additive changes anytime (`schema_version` bumped); breaking changes only in one scheduled window after G3 via `migrate_schema.py`.

## 7. The merge

```
tier0 (mut-*) + tier1a (cs-*) + tier1b (pg-*) → validate vs schema → concat → dedupe →
join problems.csv (context) + label_mapping.csv (class, family) → labels.jsonl + features.csv →
grouped split → splits.csv → final gates → train
```

**Leakage control:** problem **clusters** (TF-IDF statement cosine > 0.8; rows carry `problem_cluster`; cluster splits only as a unit) · MinHash token 5-gram code dedupe (Jaccard ≥ 0.8; cross-split twins = 0) · **seed grouping** (`seed_ref` intact across splits) · **StratifiedGroupKFold** · **per-class problem-spread ≥15 distinct clusters** (G4) · **mining restricted to train-side clusters** (§5-E1) · **user-sensitivity check** on gold (train-seen vs unseen users).

**Final layout:**

```
data/misconception_dataset/
├── README.md · DATASET_CARD.md · ANNOTATION_GUIDELINE.md · HOURS_LOG.md (§10b)
├── raw_recovery/recovery_manifest.json     # + Docker digest, flags, lockfile, seed-audit (G0c)
├── fixtures/ · annotations/{tier0_mutants,tier1a_codestream,tier1b_progpedia,labels,gold,dev_gold}.jsonl
├── features/{features.csv, FEATURE_SCHEMA.md, label_defining_features.json}
├── splits/splits.csv · models/{xgb_v1, xgb_masked_v1, xgb_common_v1, metrics_v1, label_encoder, calibrator}.json
└── reports/{pilot_ablation.md, selection_report.md, final_evaluation.md}
```

## 8. Class balance — five layers (single source of truth: this table)

**Layer 1 — Supply floors.** Every number in this document is derived from this table:

| Class | Eman floor/target | Umaima floor/target | Rayaan floor/target | Certain floor (≥) |
|---|---|---|---|---|
| 1 LOOP_BOUNDARY | 300 / 400 | 100 / 250 | — | 300 |
| 2 OFF_BY_ONE | 300 / 400 | 100 / 250 | — | 300 |
| 3 ARRAY_BOUNDS | 300 / 400 | 100 / 250 | 100 / 250 *(pg-3)* | 300 |
| 4 UNINITIALIZED_VAR | 300 / 400 | 0 / 150 *(discovery + human-confirm)* | — | 300 |
| 5 INT_OVERFLOW | 300 / 400 | 100 / 200 | — | 300 |
| 6 MISSING_BASE_CASE | 300 / 400 | 100 / 200 | — | 300 |
| 7 ASSIGN_VS_COMPARE | 300 / 400 | 100 / 250 | — *(pg-1 counts toward class 7 target opportunistically)* | 300 |
| 8 WRONG_LOOP_DIR *(hard-3)* | 200 / 300 | 0 / 150 *(discovery + human-confirm)* | — | 200 |
| 9 RANGE_CHECK *(hard-3)* | 200 / 300 | 0 / 150 *(discovery + human-confirm)* | — | 200 |
| 10 STALE_EXIT *(hard-3)* | 200 / 300 | 0 / 150 *(discovery + human-confirm)* | — | 200 |
| 11 OTHER_ERROR | 200 / 250 *(subsampled from ≥1,100 decoys generated)* | 150 / 400 *(human-confirmed real rows only)* | — | 200 |
| **Totals** | **2,900 / 3,950** | **750 / 1,975** | **100 / 250** | **2,900** |

**Derived totals (checked):** Eman floor = 7×300 + 3×200 + 200 = **2,900**; Eman target = 7×400 + 3×300 + 250 = **3,950**. Umaima floor = 6×100 weak + 150 human-confirmed OTHER = **750**; target = 1,400 weak (250+250+250+200+200+250) + 4×150 discovery (classes 4, 8, 9, 10) + 400 OTHER = **2,400** (discovery yields are uncertain; §13.5 fallback handles shortfalls). Rayaan = **100 / 250** (pg rules; never load-bearing). **Grand lane floor = 2,900 + 750 + 100 = 3,750 · grand target = 3,950 + 2,400 + 250 = 6,600.** **Certain floor total = 2,900** (the sum of the last column; Umaima's and Rayaan's weak rows are silver and sit *on top*, never inside it — per Layer 4).

**Notes:** Umaima's discovery rows (classes 4, 8, 9, 10) are human-confirmed → certain, not silver. Her "natural surplus" beyond floors: single-firing rows beyond the floor numbers, soft cap 400/class, recorded in `selection_report.md`. Rayaan's mapping: pg rules contribute opportunistically to classes 3, 4, 6, 7 at ≤0.60; his hard floor is none — the 100 is the pg-3 expectation.

**Layer 2 — Weekly gate:** `verify_dataset.py --per-class-report` prints class × lane × (certain/silver). Under-floor cell = fixed that week.

**Layer 3 — Training weights:** `w = w_balance × w_confidence × w_source`, multiplicatively combined, **clipped max/min ≤ 10**. **Global caps (they cannot hold per-class — hard-3 are synthetic-only by nature):** total synthetic effective weight **≤50% of training mass**; **no single class >15% of training mass** (prevents OTHER_ERROR dominance given the ≥1,100 decoy pool). Synthetic source multiplier (0.5–1.0) is a CV-selected hyperparameter.

**Layer 4 — Certain-floor rule:** a class's floor counts only certain rows: execution-verified synthetic, **`repair_verified` real rows** (§5-U2), and human-confirmed rows (H2 audits, discovery confirmations). Silver (weak-rule) sits on top. Target per class: ≥200 certain + ≥10 human-confirmed. **Unreviewed no-LF-fired rows are NEVER labeled OTHER_ERROR** — they stay unlabeled (see §13.5 for why this matters for the hard-3).

**Layer 5 — Production matching:** `OTHER_ERROR` mirrors production messiness; dev-gold sampled from natural distributions for calibration; **open-set metric:** confident-taxonomy false-alarm rate on gold OTHER_ERROR, **target ≤30%**.

## 9. Verification gates (hard failures)

### 9.0 Master gate table

| Gate | Owner | Exact pass criteria |
|---|---|---|
| **G0 Raw recovery** | Rayaan | CodeNet 70 problem dirs · PROGpedia 9+8 · CodeStream 46+5,482 · 100% of labeled-pool paths resolve · 5%-sample SHA-256 ≥98% |
| **G0b Environment** | Umaima | Docker pinned **by digest**; g++/clang/Valgrind versions, `-std`, stack limit fixed; Python wheel check (xgboost/shap/pandas on 3.14, else pin 3.12); manifest recorded |
| **G0c Seed audit (NEW)** | Eman | **Week 0, before G4 commitment:** per-class seed counts per train-side cluster (recursive seeds, overflow-prone seeds, etc.); bank ~86 seeds ≈ ≤260 mutants — CodeStream Accepted is the binding source; if a class has <150 viable seeds → pre-committed relaxations trigger: per-seed cap → 5 (logged), hand-written seed templates allowed for that class, or floor reduced at H3 with disclosure |
| **G1 Resolvers** | Rayaan | unit tests · labels↔normalized join 0 orphans · enums clean · schema_version present |
| **G2 Pilot features** | Rayaan | ≥95% of pilot rows full vectors · sanitizer/Valgrind pass ≥90% of compilable · NaN profile correct per source · parser fixtures (ASan/UBSan/stack-overflow/Valgrind-uninit/clean) all pass |
| **G3 Pilot go/no-go** (pre-committed; **bootstrap CIs required on every statistic**) | team | (a) pilot-val macro-F1 ≥ 0.40; (b) transfer matrix on held-out **train-side** CodeStream clusters: S+R ≥ R-only, **and** S-only ≥ 0.30 macro-F1 on real rows; (c) adversarial validation AUC (style features only) < 0.75 pass / > 0.85 fail; (d) **behavioral gate:** full model beats runtime+tests-only model by ≥ 0.02 AND beats static+warnings-only model (both prove feature groups carry unique signal; the v4 masked-gap gate is dropped — masking at train but not test is a distribution mismatch, and classes like ASSIGN_VS_COMPARE whose *cause* is the masked feature cannot pass a ≤0.10 gap legitimately — the masked model is still trained and **reported, informational only**); (e) hard-3 + class-4 fallback decision moved to **G3b (end of Week 3, after discovery review)** — see §13.5; (f) pre-registered merges: pair confusion > 30% on pilot-val (CI-lower-bound above 20%) **or** human κ < 0.4 → merged via `label_mapping.csv` join |
| **G3b Discovery fallback (NEW)** | team | end of Week 3: per-class verified-real counts for classes 4, 8, 9, 10 → fallback rule of §13.5 executes now |
| **G4 Tier 0 scale** | Eman | ≥ floor column, class by class (§8) · rejection <50% with logged reasons (intended-signature fail / collision / seed fail) · each class ≥15 problem clusters · decoy pool ≥1,100 generated, training contribution subsampled to target · ≤3 mutants/seed (relaxations per G0c, logged) |
| **G5 Tier 1 weak** | Umaima + Rayaan | Umaima ≥600 weak floor + ≥150 human-confirmed OTHER · Rayaan ≥100 · only single-firing/human-promoted/repair_verified · every LF ≥50 audited fires ≥90% · Beta-bound confidence · **selection report** (single/multi/none-firing fractions per class and per problem; KS/PSI vs rest) |
| **G5b PROGpedia/CPG keep-drop (moved from G3 — v4.1)** | Rayaan | decided **after U4** on full data: PROGpedia stays only if +≥0.02 macro-F1 on held-out **train-side** CodeStream validation; CPG features same rule; failure → analysis-only lane, Rayaan's merge time freed |
| **G6 Gold** | Umaima (coord.) | **220 commitment / 150 floor** = 180 stratified (8 normal classes ×14 · hard-3 ×18 · OTHER ×14) **+ 40 uniform-random prevalence slice** (distractors incl. firing_count 0/1/2+; doubles as §13.5 bias correction) + 60 dev-gold (separate held-out clusters) · gold spans **≥12 of the 15 test-side clusters, ≥30 users** · blind forms (no LF names, no predictions, no stratum; randomized) · intra-rater duplicates ≥8/10 · **Fleiss κ (4 raters: 3 team + external) ≥ 0.6 overall**; per-class κ reported **only for hard-3** (≥12 overlap items each); classes with κ < 0.4 → merge candidate / "human-ambiguous" finding |
| **G7 Splits** | Rayaan | problem-cluster intersection across splits = ∅ · seed groups intact · 0 gold/dev-gold rows in train · MinHash cross-split twins = 0 · train/val PSI < 0.2 |
| **G8 Training** | Rayaan | StratifiedGroupKFold macro-F1 beats majority by ≥0.25 · synthetic mass ≤50% · weight clip ≤10 · class-mass cap ≤15% · `assert gold ∉ train` in-script · **one global threshold + temperature scaling only** (60 dev-gold ≈ 5/class cannot tune per-class thresholds; isotonic banned as overfitting) · ECE reported |
| **G9 Final** | Rayaan | per-class P/R/F1 with Wilson intervals · confusion (fine + family) · **paired-bootstrap difference vs rule baseline (resampled by problem)** · McNemar exact secondary · rule baseline **mapped to `tl-cpp-v2` incl. its UNCERTAIN → OTHER_ERROR abstention behavior, reported** · masked + common-feature model results · open-set false-alarm rate · per-source and per-slice (firing_count) breakdowns · SHAP by group (static >70% mass on rule-labeled classes → flagged) · **scope statement page 1: gold is CodeStream-only** · **pre-registered analysis followed (§13.7); +0.05 MMD below the ~9pp detection limit → reported as "inconclusive-directional" with its interval** |
| **G10 Independent re-run** | *not Rayaan* | clean-checkout rerun of training + evaluation; numbers match within tolerance |

### 9.1 Eman — step gates

| Step | Deliverable | Pass criteria | If it fails |
|---|---|---|---|
| **E1 Operators** | reverse-mutation library (train-side mining) | operators from clustered real diffs (hand-reviewed clusters), frequency-weighted · ≥4 surface forms · unit fixtures 100% · collision check all 11 signatures | <80% fixture firing rate → fixed before use |
| **E1d Decoys** | decoy operators | ≥100 generated per class; OTHER_ERROR label; subsampling plan attached | shortfall → H3 adjusts OTHER floor with disclosure |
| **E2 Verifier** | execution + proofs + format normalization | seeds pass pre-mutation 100% · clean-control 0-FF · proofs stored | stop; nothing it produces is usable |
| **E3 Pilot** | 150 mutants → G3 | schema-valid · all 11 classes ≥5 · week 1 | top up weakest operators |
| **E4 Scale** | ≥2,900 → G4 | G4 incl. rejection-reason logs + cluster spread | fix under-floor classes; never pad with rejects |
| **E5 Audit** | 50-mutant audit → H2 | mislabel <10% · root-caused findings fixed, class re-generated | ≥10% → operator retired |

### 9.2 Umaima — step gates

| Step | Deliverable | Pass criteria | If it fails |
|---|---|---|---|
| **U0 Harness (Week 0, 5 days; minimal executor by day 2)** | `sandbox_runner` + G0b | two compile passes (`-O2 -Wall -Wextra` warnings; `-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined` sanitizers); **uninit detection via Valgrind memcheck by default** (clang MSan optional, only with instrumented libc++; false-positive-prone otherwise); isolation (`--network none`, read-only root, tmpfs, non-root, `--pids-limit 64`, `--memory 512m`, CPU limit); 2 s/test (×3 sanitizer), 1 MB cap, process-group kill; determinism (double-run, flaky dropped, stdin from files, seeds fixed); throughput (~70k runs, hash-cached, parallelized, budgeted in hours); unit-tested parsers with fixture reports | missing isolation/determinism item = rebuild before bulk execution |
| **U1 Executor** | full C/C++ pool | U1 criteria §5 | 10-row divergence investigation before labeling |
| **U2 LFs + repair** | LF library + `repair_verify.py` | fixtures · single-firing · ≥50-fire audits ≥90% · Beta bounds · **repair-and-rerun applied to every LF-fired row; `repair_verified` rows recorded with proof** | <90% → tighten/re-audit; chronic fail → retire LF |
| **U3 Pilot** | **150 real rows** → G3 | schema-valid · ≥5 classes · week 1 | raise LF precision |
| **U4 Scale** | ≥750 floor + surplus → G5 | G5 + selection report · multi-signal pool logged · discovery candidates (§13.5) handed to H2 review | under-floor → tune LFs; never convert review-pool rows |
| **U5 Forms** | 220 gold + 60 dev-gold + 15-item calibration round → G6 | G6 stratification (§9.0) · blind · distractors · guideline decision tree written after calibration round | regenerate before annotation |

### 9.3 Rayaan — step gates

| Step | Deliverable | Pass criteria | If it fails |
|---|---|---|---|
| **R1 Contracts (Week 0)** | `FEATURE_SCHEMA.md` v1.0 **enumerated** + `label_mapping.csv` (classes, families, merges, `lf_inputs`) + `tl-cpp-v2` + **`tracelearn_features` v0 interface** | names/types enumerated · pin + hash in manifest · lanes acknowledge pre-freeze · one post-G3 breaking window scheduled | additive-only after freeze |
| **R2 Foundation** | `verify_dataset.py` + `--per-class-report` → G0, G1 | green on synthetic end-to-end row | nothing downstream on red |
| **R3 CPG parser** | `parse_cpg.py` | ≥95% parse · matches `data.md` · 10 hand-checked · failures logged | <95% → triage; unparsed dropped, never guessed |
| **R4 Pilot + ablations** | pilot matrix + suite → G3 | adversarial validation · transfer matrix (S→R, R→R, S+R→R, CIs via bootstrap) · **behavioral gate (G3d)** · masked model (reported, informational) · **source-shortcut test** (dataset_source from missingness alone >90% → common-feature variant forced) | G3 fail → pre-registered merge via join |
| **R4b PROGpedia/CPG keep-drop** | decision at **G5b** (after U4, full data) | +≥0.02 macro-F1 on held-out train-side CodeStream val, else analysis-only | pre-authorized drop — not a crisis |
| **R5 Merge + splits** | `merge_dataset.py` → G7 | G7 · 0 duplicates · per-source availability + selection + multi-signal reports linked | re-split; never hand-edit |
| **R6 Training** | `train_xgb_misconception.py` → G8 | three variants (full / common-feature / masked) · Layer-3 weights · global threshold + temperature on dev-gold | tune inside train/val/dev-gold only |
| **R7 Evaluation** | `final_evaluation.md` + `DATASET_CARD.md` → G9 | G9 · pre-registered analysis (§13.7) · V2 scope (history, multi-label) recorded | no claim without gold number + interval |

### 9.4 Human gates

| Gate | Who | Pass criteria | If it fails |
|---|---|---|---|
| **H1 Annotation** | ~103 items each (135 single + 45 overlap) + external annotator on the 45 overlap items (4 raters) | G6 counts + κ thresholds · calibration round first · guideline exists | κ < 0.6 → revise + re-annotate · 3-way splits → discussion → unresolved = `UNCERTAIN`, dropped, counted |
| **H2 Audits** | rotate per lane, **stratified by class** | mislabel <10%/lane · **≥10 human-confirmed rows per class** promoted (incl. discovery candidates for classes 4, 8, 9, 10) | ≥10% → rules revised, class re-generated |
| **H3 Merge meeting** | all three | every gate green or waived in `DATASET_CARD.md` · certain vs silver floors confirmed · G0c/G3b fallbacks executed · cut-lines respected (§10) | no merge with a silent floor gap |

### 9.5 Sequencing (v4.1 timing)

```
Week 0 (5 days):  Day 1–2 U0 minimal executor + G0b ‖ R1 contracts start ‖ G0c seed audit
                  Day 3–5 U0 hardening ‖ R1 schema + fixtures + tracelearn_features v0 ‖
                  CodeStream problem clustering → train/dev-gold/test cluster split (§13.4) →
                  E1 mining begins (train-side only)
Week 1:  E1→E2→E3 (150 mutants)   U1→U2→U3 (150 real rows)   R2 (G0,G1) → R3 own lane
         §13.5 discovery detectors built + first candidate mining (classes 4, 8, 9, 10)
Week 2:  R4 pilot integration + full ablation suite (CIs on everything) → G3
Week 3:  E4 scale ‖ U4 scale ‖ discovery candidate review (2h × 4 classes × person) → G3b fallback decision
Week 4:  U5 forms + calibration → H1 annotation (gold + dev-gold) ‖ H2 stratified audits + repair-verification batch
Week 5:  adjudication + κ → H3 merge meeting → R5 (G7) → G5b PROGpedia/CPG keep-drop
Week 6:  R6 (G8) → R7 (G9) → G10 independent re-run → write-up (3 days slack)
```

### 9.6 Rayaan's critical path — independent vs dependent

**Independent (never blocked):** R-I1 G0 · R-I2 contracts + `tracelearn_features` v0 (Week-0 deliverable that unblocks *everyone*, including himself) · R-I3 verify script · R-I4 fixtures · R-I5 scaffold · R-I6 own lane · R-I7 training harness on fixtures.
**Dependent (exact trigger):** R-D1 pilot features ← E3+U3 schema-valid · R-D2 ablations ← pilot matrix · R-D3 floor monitoring · R-D4 merge ← lanes final + gold locked · R-D5 train/eval ← G7 · R-D6 re-run ← G9 · R-D7 G5b ← U4 complete.
**Rule:** if Rayaan is waiting, independent work always exists.

## 10. Timeline, cut-lines, hours

Six weeks + **5-day Week-0 prep** (§9.5). **Cut-lines (decided now):** G4/G5 unmet by end of week 3 → ship at ≥150/class · drop order under pressure: **PROGpedia → CPG → SHAP polish** (PROGpedia is pre-authorized for dropping at G5b) · **the 150-row gold floor is non-negotiable** · merges are cheap (`mutation_op` + `label_mapping.csv` join) · G3 outcomes pre-registered.

### 10b Human effort budget (hours per person, weeks 0–5)

| Task | Rayaan | Eman | Umaima | External |
|---|---|---|---|---|
| Week 0 infrastructure | ~25h (contracts, schema, library v0, fixtures) | ~10h (mining setup, G0c audit) | ~30h (sandbox U0) | — |
| LF precision audits (≥50 fires × ~1.5 min) | ~2h (pg rules) | — | ~5h | — |
| Discovery review (4 classes × 2h) | 8h | 8h | 8h | — |
| Calibration round (15 items) | 1h | 1h | 1h | 1h |
| Gold annotation (~135 single + 45 overlap ≈ 5–7 min/item with evidence reading) | ~11h | ~11h | ~11h | ~4h (overlap only) |
| Dev-gold (~20 items each) | 2h | 2h | 2h | — |
| H2 audits (50 rows, stratified) | 2.5h | 2.5h | 2.5h | — |
| Adjudication + merge meeting | 3h | 3h | 3h | 1h |
| **Total** | **~54h** | **~38h** | **~62h** | **~6h** |

Umaima is the heaviest (harness ownership) — if capacity is unequal, the first thing to redistribute is gold annotation to the external annotator (expand their overlap share) and the H2 audits.

## 11. Training contract (v4.1)

1. **Matrix:** enumerated features, float32, NaN preserved. `y` = LabelEncoder over **11 modeled labels**; mapping in `label_encoder.json`. Allowlist-dropped bookkeeping columns.
2. **Model:** `XGBClassifier(objective="multi:softprob", eval_metric="mlogloss", max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=3, reg_lambda=1.0, n_estimators=2000, early_stopping_rounds=50)`.
3. **Validation:** StratifiedGroupKFold by problem **cluster**, macro-F1; refit on train+val; **one global threshold + temperature scaling on dev-gold only** (ECE reported; isotonic banned; per-class thresholds infeasible at ~5 dev-gold items/class); **one** test-gold evaluation.
4. **Weights:** `w = w_balance × w_confidence × w_source`, clip ≤10; **global** synthetic ≤50%; class-mass cap ≤15%; multiplier CV-tuned (§8-Layer 3).
5. **Required variants, all reported on gold:** **full** · **common-feature** (static+warnings only; forced fallback if the source-shortcut test fails) · **masked** (`lf_inputs` → NaN on weak rows at train time — **reported with the train/test mismatch disclosed; informational, no gate**; the gate is the behavioral/static uniqueness check at G3d) · **optional V1.5 history ablation** (3 features, CodeStream-only, §13.6).
6. **Honesty:** weak-label agreement is never "accuracy." Rules vs. model compared only on gold, with and without history.

## 12. Inference contract (what the model receives)

**Inputs:** (1) submitted source + language; (2) the problem → tests, expected outputs, statement.

```
submission arrives
  ├─ compile fails        → deterministic compile feedback (no model — likely the most common branch)
  ├─ all tests pass       → NO_MISCONCEPTION (no model)
  ├─ timeout, no crash    → deterministic infinite-loop hint (no model), UNCERTAIN fallback to rules
  └─ otherwise (failing, runnable) → sandbox_runner (pinned container)
        warnings pass (-O2) · sanitizer passes (ASan/UBSan -O1; Valgrind uninit) ·
        tests + differential vs expected · tracelearn_features static pass · problem context
        ▼
      feature vector (FEATURE_SCHEMA.md order) → xgb_v1 (or common-feature variant if runtime unavailable)
        ▼
      11 calibrated probabilities (temperature scaling)
        ▼
      max < global threshold (dev-gold-tuned)  → UNCERTAIN → rule-engine fallback
      label = CPP_OTHER_ERROR (confident)      → "a different issue — generic debugging guidance" (+ rules)
      else → {label, confidence, top SHAP evidence} → hint system
```

**Open-set behavior is designed in:** production is full of OTHER_ERROR; the ≤30% gold false-alarm target (§8-Layer 5) is the honest measure of force-fitting.

## 13. Ground truth, gold protocol, statistics

### 13.1 Sufficient ground truth — the honest math

**Training:** certain labels = execution-verified synthetic (≥200/class floor, Layer 4) + `repair_verified` real rows + human-confirmed rows (≥10/class). Silver adds diversity, confidence-weighted, never load-bearing. **Evaluation:** per-class recall margins ≈ ±25% (n=15), ±18% (n=20), ±13% (n=30) → **220 commitment, 150 floor**, Wilson intervals on every per-class number; no claims <15 items.

### 13.2 Dev-gold (60 items)

From **separate held-out clusters** (§13.4 budget); **only** for threshold (one global value) + temperature scaling + calibration diagnostics. This makes the one-shot test discipline achievable.

### 13.3 Human-verified training boost

Every H2-audited confirmed row → `label_source=human`, joins training. Audits **stratified by class** to deliver ≥10 confirmations per class — replacing v3's impossible 50-row sizing.

### 13.4 Gold protocol, blind design, and the 46-problem budget

**CodeStream problem budget (explicit, v4.1 — clusters, not raw problems, since TF-IDF clustering will shrink the count):**

| Pool | Clusters | Use |
|---|---|---|
| Train-side | **≥21** | Umaima training rows · Eman seeds + reverse-mutation mining (train-side only) · Rayaan held-out validation slice |
| Dev-gold | **5** | 60 calibration items |
| Test-side | **15** | gold 220 (spanning ≥12 of the 15, ≥30 users) — **no row from these clusters, including mutants seeded from them, reaches training** |

*If clustering yields <36 clusters total: dev-gold → 4, test → 12, gold spans ≥10; the 150 floor is protected first.*

- **Gold composition:** 180 stratified (8 normal ×14, hard-3 ×18, OTHER ×14) + **40 uniform-random prevalence slice** — the random slice samples all wrong rows including distractors (firing_count 0/1/2+), doubling as the §13.5 selection-bias correction; items matching a class count toward that class's total. **Every gold item tagged `firing_count`; metrics per slice; the single-signal vs multi-signal gap = real-world degradation estimate.**
- **Blind forms:** no LF names, no model predictions, no stratum; raw evidence only; randomized order.
- **Overlap design:** 45 items triple-annotated — **hard-3 ×12 = 36** + 9 (one per remaining class) — annotated by **all three team members + the external annotator (4 raters)** → **Fleiss κ over 4 raters (overall gate ≥0.6)**; per-class κ **reported only for hard-3** (12 items each; anything thinner is noise, as the review noted); other classes get pairwise Cohen κ, descriptive only. 10 blind duplicates kept, reported as **intra-rater**.
- **Calibration round:** all raters label the same 15 items, discuss, write the decision tree into `ANNOTATION_GUIDELINE.md`, then start.
- **Adjudication:** majority vote; 3-way split → discussion → unresolved = `UNCERTAIN`, dropped from test, counted and disclosed.
- **Human–LF agreement reported per class** as a finding about the LFs, not gold quality. Gold scope statement on page 1 of the report: **CodeStream-only**.

### 13.5 Real-data discovery pipeline (classes 4, 8, 9, 10) — and the OTHER_ERROR contradiction fixed

**The design flaw (v4.1 fix):** v4 labeled real no-LF-fired rows as OTHER_ERROR ≤0.6 — but classes 4, 8, 9, 10 have no natural real-data LF, so their *real* instances would be trained as OTHER_ERROR while their synthetic twins carry the real class. The model would learn "realistic-looking hard-3 code → OTHER." **Fix, binding:**
1. **Unreviewed no-fire rows are never labeled — they stay unlabeled.**
2. **REAL `OTHER_ERROR` rows are human-confirmed only** (Umaima's 150/400 floor is human-confirmed, §8).
3. **Hard-3 + class-4 detector candidates are excluded from any OTHER pool** and routed to review instead.

**Pipeline:** candidate detectors (surface, cheap, **not labels**): class 4 — `-Wmaybe-uninitialized` ∧ Valgrind uninit report; class 10 — while-condition vars never assigned in body (dataflow); class 8 — AST comparison vs reference solution (decrement where reference ascends) + order-reversed outputs; class 9 — failing boundary-pattern tests. Candidates also **ranked by pilot-model probability**. **Review budget:** 2h/person/class; **found-per-reviewed recorded = the class's real-world prevalence estimate** (an FYP finding). **Bias correction:** the 40 uniform-random gold slice (§13.4) estimates natural prevalence and measures recall on detector-invisible cases. **Pre-committed fallback (decided at G3b, end of Week 3 — after discovery review, resolving v4's G3/Week-3 contradiction):** <12 verified real examples → the class is **dropped from fine-grained modeling, reported at family level only**, with its synthetic rows retained for family-level training. Decision executes via `label_mapping.csv` join — a join, not a regeneration.

### 13.6 History scope (honesty fix)

V1 claims: *learned model vs frozen rules on a single submission.* History is V2 (`DATASET_CARD.md`). The `meta` block preserves `user_id_hash`, `attempt_index`, `timestamp`, `prev_submission_id` from day one — never features. The rule baseline is reported **with and without history** (its labels mapped to `tl-cpp-v2`, its UNCERTAIN/abstain behavior reported as its OTHER_ERROR strategy). Optional V1.5: 3 history features, CodeStream-only, as an ablation.

### 13.7 Pre-registered statistical analysis (written before gold opens)

- **Power, stated up front:** at n=150 paired items with ~40 discordant pairs, McNemar needs roughly a 27/13 split — **~14 net items ≈ 9 percentage points** — to reach significance. **Pre-registered reading of small results: a point estimate of +0.05 with a CI spanning zero is reported as "inconclusive-directional," never as a win.** 220 is the commitment precisely because of this.
- **Primary:** macro-F1 over the 11 modeled labels; model-vs-rules difference via **paired bootstrap resampling by problem**. **Secondary:** McNemar's exact test.
- **Minimal meaningful difference: +0.05 macro-F1** (directional only, per the above); **detectable difference: ≈+0.09** — both recorded before gold opens.
- **Per-class:** Wilson intervals; no significance claims between model and rules per class; no claims <15 items.
- **One-shot:** all tuning absorbs into dev-gold; test gold touched exactly once.

## 14. Risks and mitigations (v4.1)

| Risk | Mitigation |
|---|---|
| Mutants teach fingerprints, not behavior | real-fix operators · ≥4 surface forms · clang-format normalization · adversarial gate · transfer ablations · synthetic ≤50% global · decoys |
| Labels are a function of features | `lf_inputs` registry · masked model reported · decoys per feature · SHAP group flags · behavioral-unique-signal gate (G3d) |
| **Real hard-3 rows mislabeled OTHER** | no-fire rows unlabeled · OTHER = human-confirmed only · detector candidates excluded from OTHER pool (§13.5) |
| Gold entangled with rule builders | blind forms · distractors · external annotator · κ stats · human–LF agreement separate |
| Single-firing selection bias | selection report · distribution KS/PSI · firing_count slices · multi-signal promotion experiment |
| PROGpedia source shortcut | missingness-only test · keep/drop at G5b on full data · 30-row audit set |
| Seed supply starvation | **G0c audit in Week 0** · pre-committed relaxations (cap→5, templates, disclosed floor cuts) |
| Hard-3 / class-4 no real-data path | discovery pipeline + prevalence ratios + random-slice correction + G3b fallback |
| Stats undetectable below ~9pp | power statement · MMD vs detectable difference both pre-registered · "inconclusive-directional" reading rule |
| Lane dependency drift | harness minimal-executor-first · `tracelearn_features` v0 in Week 0 · fixtures for self-validation · backups + CI + G10 re-run |
| Timeline slip | 5-day Week 0 · pre-committed cut-lines · gold floor non-negotiable |

## 15. Definition of done

- [ ] `verify_dataset.py` green on G0–G10 (incl. independent re-run).
- [ ] ≥2,900 certain rows; every modeled class ≥200 certain + ≥10 human-confirmed; selection, multi-signal, per-source, and repair-verification reports published.
- [ ] 220 gold (150 floor) + 60 dev-gold locked; Fleiss κ ≥0.6 (4 raters); per-class P/R/F1 with Wilson intervals vs. rule baseline (with/without history, mapped to v2 incl. abstentions).
- [ ] Masked, common-feature, open-set, and behavioral-gate results reported; pre-registered analysis followed or deviations disclosed; +0.05-level results labeled inconclusive-directional.
- [ ] `DATASET_CARD.md`: tier claims, CodeStream-only gold scope, V2 scope (history, multi-label), hard-3/class-4 validation status, G0c/G3b fallbacks executed.
- [ ] Every row traceable: `row_id` → lane JSONL → raw file on G:.

## 16. Plain-English summary (for the whole team)

**What are we doing?** TraceLearn today spots student mistakes only through hand-written rules — like a calculator programmed for exact problems only. We are building a labeled dataset: thousands of real and deliberately-broken C/C++ programs, each tagged with the specific misunderstanding behind the error, plus a "something else went wrong" category so the model admits what it doesn't know. From it we train XGBoost — a small, fast, well-understood model — to guess which misunderstanding a failing submission shows. (When all tests pass, or the code doesn't compile, no model is needed at all — those are answered directly.)

**How?** Three people, three separate piles of data, one shared execution machine so results are comparable: **Eman** learns what mistakes real students actually make by diffing their consecutive attempts (only from the training portion of the data, so test cases never leak), then manufactures verified-broken programs that mimic those mistakes — plus deliberate traps ("the pattern looks like the bug, but isn't") so the model can't cheat by pattern-matching tokens. **Umaima** builds the shared sandbox everyone runs code through, mines real student submissions against their own tests with carefully audited rules, and — where a rule fires — *repairs* the suspected bug and re-runs the tests: if the repair fixes everything, the label is proven, not guessed. **Rayaan** keeps the schema honest, mines PROGpedia's code-graphs behind a strict "prove it helps or drop it" rule, merges everything into one balanced dataset, and trains and evaluates the model — including checking that it learned behavior, not our rules. Ambiguity always goes to a review pool; every class's floor must be filled with *certain* labels only. An annotator outside the team plus a 45-item overlap set tell us whether humans even agree — because if humans can't agree on a class, no model can be blamed for failing it.

**End goal?** When a failing student submission arrives, TraceLearn answers not just "wrong" but *"you probably think loops include their upper bound — here's a hint about that specific idea"* — and when it isn't sure, or the bug isn't in our taxonomy at all, it says so and steps aside for the rules. For the FYP, this gives an honest, numbers-backed answer to the research question — measured once, on 150–220 real submissions none of us trained on, with the detection limits of that measurement written down in advance.

## 17. Inconsistency register (v3 → v4 → v4.1 resolutions)

| Issue (found when) | Resolution |
|---|---|
| Floor arithmetic stated ≥2,900; actual 3,600 (v4 review) | one floor table (§8); all totals derived and re-verified |
| Eman target 3,550; actual 3,850 (v4.1 audit) | **3,950** after OTHER rebalance (7×400+3×300+250) |
| Grand target 5,650 → 5,950 → (v4.1) **6,600** (3,950 + 2,400 + 250) | stated once, derived from §8 |
| "≥3,800 certain" included Umaima's silver rows, contradicting Layer 4 (v4.1) | certain floor = **2,900** (last column of §8, synthetic-verified + repair-verified + human-confirmed only) |
| OTHER_ERROR certain floor 100 < Layer-4's 200 (v4.1) | raised to 200 (Eman decoy 200 execution-verified + Umaima 150 human-confirmed) |
| Decoy ≥100/class ≈ 1,100 vs OTHER target 250 (v4.1) | generate ≥1,100, **subsample** to target; full pool archived; class-mass cap ≤15% prevents OTHER dominance |
| Gold stratification overflowed 220 (8×20+3×25[+OTHER]+60 random) (v4.1) | recomposed: 180 stratified (8×14 + hard-3×18 + OTHER×14) + 40 random slice = 220 |
| McNemar "12 items ≈ 8pp" optimistic (v4.1) | **27/13 split, ~14 net items ≈ 9pp**; MMD +0.05 pre-registered as "inconclusive-directional" |
| Real hard-3 rows would train as OTHER_ERROR (v4.1 design flaw) | no-fire rows unlabeled · OTHER real rows human-confirmed only · detector candidates excluded from OTHER pool (§13.5) |
| Class 4 no real-data path but needs gold (v4.1) | class 4 added to discovery pipeline (Valgrind + `-Wmaybe-uninitialized` detector) |
| G3 statistics too thin at 60 real rows (v4.1) | pilot raised to **150 real rows**; bootstrap CIs required on every G3 statistic; PROGpedia/CPG keep-drop **moved to G5b (after U4)** |
| Hard-3 fallback "at G3 (Week 2)" but discovery starts Week 3 (v4.1) | discovery starts Week 1; fallback decided at **G3b, end of Week 3** |
| Gold "≥20 problems" vs G7 cluster-disjoint splits vs 46-problem supply (v4.1) | explicit cluster budget: **21 train / 5 dev-gold / 15 test**; gold spans ≥12 of 15 test clusters |
| Reverse-mutation mining could leak test-side patterns (v4.1) | mining restricted to **train-side clusters**; cluster split decided in Week 0 before mining starts |
| Seed supply unexamined; bank cap near-irrelevant (v4.1) | **G0c Week-0 seed audit** per class per train-side cluster with pre-committed relaxations |
| Shared feature library re-created lane dependency (v4.1) | `tracelearn_features` **v0 due end of Week 0 with fixed interface**; fallback = merge-time backfill; harness ships minimal executor day 2 |
| "11 modeled classes + OTHER" vs table (v4.1) | phrasing fixed: **10 misconception + OTHER = 11 modeled** |
| `CPP_CONTROL_FLOW_OTHER` orphan code (v4.1) | removed; unvalidated hard-3 class → dropped from fine-grained modeling, family-level reporting only |
| §2.1 "Accepted → OTHER_ERROR-pool" nonsense (v4.1) | corrected: Accepted rows are seeds + sanity only, never labeled |
| pg-3 needed outputs PROGpedia doesn't have (v4.1) | replaced with AST fixed-size array-write rule; pg rules use only syntax + warnings + verdict |
| pg-1's two "signals" were one signal (v4.1) | second signal added: assigned variable feeds output computation (AST dataflow) |
| MSan false positives on uninstrumented libc++ (v4.1) | **Valgrind memcheck is the default** uninit detector; MSan optional |
| Compile errors / timeouts had no branch (v4.1) | deterministic pre-branches added (§1, §12) |
| Per-class thresholds on 60 dev-gold infeasible (v4.1) | **one global threshold + temperature scaling only**; isotonic banned |
| Masked-model gate mismatched train/test and punished causal classes (v4.1) | masked model reported, informational; gate replaced by behavioral/static unique-signal checks (G3d) |
| Per-class κ on 4 overlap items = noise; external-annotator role unclear (v4.1) | hard-3 ×12 overlap items; **4-rater Fleiss κ** (3 team + external) with overall ≥0.6 gate; other classes pairwise-only |
| Synthetic ≤50% unenforceable per class for hard-3 (v4.1) | restated as a **global** cap + class-mass cap 15% |
| +0.05 MMD below detection (v4.1) | detection limit ≈+0.09 stated; +0.05 → "inconclusive-directional" reading rule |
| Rule baseline unmapped to v2, abstention unaddressed (v4.1) | mapping via `label_mapping.csv`; UNCERTAIN/abstain reported as its OTHER_ERROR strategy |
| Week 0 = 3 days for too much (v4.1) | **5 days**, minimal executor first |
| Human effort unbudgeted (v4.1) | **§10b hours table**; Umaima heaviest, redistribution options noted |
| **Repair-and-rerun improvement (v4.1, adopted)** | `repair_verified` label source: inverse-operator repair + all-tests-pass → certain-floor credit; also double-checks Eman's operators |
