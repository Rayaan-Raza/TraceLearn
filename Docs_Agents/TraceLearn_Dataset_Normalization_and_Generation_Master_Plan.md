TRACELEARN | DATASET ENGINEERING MASTER PLAN 

**TRACELEARN** 

# Dataset Normalization & Synthetic Data Generation Master Plan 

Source ingestion • canonical schema • labels • quality checks • synthetic C++ data 

Prepared 9 October 2026 | Current implementation direction: C++ 

## **How to use this document** 

This plan is based on the TraceLearn Master Design and Implementation Blueprint, the FYP-1 mid-evaluation materials, the current C++ implementation direction, and public dataset source pages. It distinguishes blueprint-derived facts from recommended engineering decisions. 

Scope conflict to resolve: the blueprint's original executive summary says Python is primary and treats C/C++ as a contingency. Your current project direction is C++. This document follows the current C++ direction. Update the blueprint, presentation, report, taxonomy and dataset register so they agree. 

## **Executive recommendation** 

- Start with a small reproducible normalized release, not every large archive. 

- Prioritize CodeStream for attempt history, PROGpedia for source/structural data, a narrow Project CodeNet C++ subset for code/status, and a TraceLearn C++ pilot for human-reviewed labels. 

- Use McMining to inform taxonomy and detector methodology; it is Python-focused and is not C++ ground truth. 

- Keep source labels, mapped labels, model predictions and human adjudications in separate fields. 

- Synthetic data is for controlled software tests and development. Never represent it as real learner ground truth or mix it into a real-student holdout set. 

## **1. What the final dataset should represent** 

TraceLearn needs more than code snippets. Each submission attempt should link to a problem, execution/test outcomes, extracted evidence, optional misconception annotations and, when real ordered history exists, prior attempts and learnerstate annotations. The blueprint distinguishes an observed error, a misconception hypothesis, structured evidence, current diagnosis and longitudinal learner state. 

|**Layer**|**Stores**<br>i|**Interpretation**|
|---|---|---|
|Raw source|Original files, source IDs, original<br>labels/metadata,version,licence|Immutable source material; no inferred<br>TraceLearn labels.|
|Normalized submission|One canonical row per attempt linked to<br>problem/source|Source label may exist; otherwise<br>misconception label remains null.|
|Execution/test results|Compile/runtime status, test-level<br>outcomes,resource metrics|Outcomes are evidence, not proof of a<br>misconception.|
|Evidence|Versioned static/runtime/test/temporal<br>observations supporting or conflicting with<br>hypotheses|Structured support; not proof of a learner's<br>belief.|
|Annotations/diagnosis|Source label, mapped label, human-reviewed<br>label,modelprediction/confidence|Keep each origin distinct and auditable.|



Working document • Preserve provenance and label semantics 

TRACELEARN | DATASET ENGINEERING MASTER PLAN 

Ordered attempts, hints, reviews and state Trajectory/state transitions 

Only when history and annotation support it. 

## **2. Dataset register: where to download and how to use each** 

These are the sources named in Appendix D of the TraceLearn blueprint. Verify the current licence, access conditions and redistribution rules before use. 

### **Project CodeNet** 

**Project CodeNet official page:** https://github.com/IBM/Project_CodeNet 

**Download:** https://codait-cos-dax.s3.us.cloud-object-storage.appdomain.cloud/dax-project-codenet/1.0.0/ Project_CodeNet.tar.gz 

Priority/role: PRIMARY C++ CORPUS. Large source-code submission corpus with problem metadata, verdict/status and CPU/memory/code-size metadata. Official README lists 7.8 GB compressed. 

How to use: Start with the official mini sample or a narrow subset. Filter C++; retain problem/submission IDs, source path, status, CPU, memory, code size and problem description. Accepted/wrong answer/runtime/compile errors are outcomes, not misconception labels. 

### **CodeStream** 

**CodeStream official page:** https://data.mendeley.com/datasets/n77t7z9zcr/1 

Priority/role: HIGH PRIORITY: HISTORY. Dataset article describes 5,482 submissions from 202 participants across 46 problems in C, C++ and Java, with attempt order and sequential verdict traces. 

How to use: Download from Mendeley Data; inspect both submission and problem/test tables; filter C++ after verifying language fields. Preserve attempt order and verdict traces. Use for longitudinal experiments, not automatically misconception ground truth. The record lists CC BY 4.0. 

### **PROGpedia** 

**PROGpedia official page:** https://zenodo.org/records/7449056 

Priority/role: HIGH PRIORITY: STRUCTURE. Submissions for 16 programming exercises, including source code and code property graphs stored as CSV. 

How to use: Download progpedia.zip. Inspect schema and language per record; link CPG nodes/edges to source submissions via native IDs. Use structural features as evidence, not as misconception labels. 

### **McMining / McMiner** 

**McMining / McMiner official page:** https://github.com/taisazero/mcminer 

Priority/role: HIGH PRIORITY: TAXONOMY. Repository describes 67 Python misconceptions and 1,063 code samples exhibiting misconceptions. 

How to use: Inspect dataset/ and licence. Preserve original Python labels and code. Map only concepts with a defensible C++ analogue, with rationale/reviewer/status. Use for taxonomy and detector test design, not C++ ground truth. 

### **ProgFeed** 

**ProgFeed official page:** https://github.com/umass-ml4ed/progFeed-dataset-public 

Working document • Preserve provenance and label semantics 

TRACELEARN | DATASET ENGINEERING MASTER PLAN 

Priority/role: OPTIONAL: FEEDBACK. Blueprint lists it as Python data for attempts, autograder results and feedback behavior. 

How to use: Use to study attempt→feedback→next attempt and hint/intervention methodology. Keep separate from C++ code training unless doing an explicit cross-language study. 

### **CSEDM 2019 / ITAP** 

**CSEDM 2019 / ITAP official page:** https://github.com/thomaswp/CSEDM2019-Data-Challenge 

Priority/role: OPTIONAL: TEMPORAL METHODS. Chronological programming events and correctness/knowledge-tracing data; access may require DataShop. 

How to use: Check access requirements. Use for event-schema and temporal modelling methodology; do not reinterpret correctness/knowledge labels as TraceLearn misconceptions. 

### **HELP-DKT** 

**HELP-DKT official page:** https://github.com/liangyubuaa/HELP-DKT 

Priority/role: OPTIONAL: ATTEMPT HISTORY. Blueprint lists 9,119 Python submissions with buggy/correct labels and ordered student/problem attempts. 

How to use: Preserve student/challenge/attempt IDs and source labels. Use only for attempt-history methodology if needed; buggy/correct is not a misconception label. 

### **FalconCode** 

**FalconCode official page:** https://huggingface.co/datasets/koutch/falcon_code 

Priority/role: OPTIONAL: COURSE DATA. Python course data with programs, assignments and test/skill metadata; access/distribution must be checked. 

How to use: Verify access approval, licence and allowed use before ingestion. Not needed for the first C++ mid-evaluation slice. 

## **3. Recommended download order** 

|**Order**|**Action**<br>i|**Acceptance condition**|
|---|---|---|
|1|Download CodeStream and inspect files,<br>columns,language and licence.|You can identify C++ rows, problem links and<br>source-backed attempt order.|
|2|Download PROGpedia and inspect<br>language/CPG schema.|You can map source submissions to CPG<br>records without danglingIDs.|
|3|Use CodeNet mini sample or a narrow C++<br>subset before full archive.|Parser works end-to-end; disk usage and<br>selected subset are known.|
|4|Download McMining for taxonomy/examples.|Every proposed mapping has rationale and<br>keeps the original Python label.|
|5|Only then consider ProgFeed/CSEDM/HELP-<br>DKT/FalconCode.|A concrete temporal/feedback experiment<br>needs the data; permissions are clear.|



Do not commit raw archives to GitHub. Commit parsers, manifests, small permitted fixtures, schemas, reports and checksums instead. 

## **4. Recommended repository layout** 

TraceLearn/ 

data/ 

Working document • Preserve provenance and label semantics 

#### TRACELEARN | DATASET ENGINEERING MASTER PLAN 

raw/{codenet,codestream,progpedia,mcmining}/  # gitignored 

intermediate/ normalized/{problems,submissions,test_results,evidence,annotations,trajectories}/ synthetic/{seed_problems,generated_submissions,fixtures_for_ci}/ splits/ 

manifests/{source_manifest.csv,file_checksums.csv} 

reports/{ingestion_report.json,data_quality_report.csv} scripts/{inspect_sources,ingest,normalize,validate,generate_synthetic,build_splits}/ schemas/{canonical_schema.json,taxonomy.csv,label_mapping.csv} tests/{test_ingestion,test_normalization,test_synthetic_generation,test_no_leakage}.py 

Use Parquet for large normalized tables; CSV is fine for starter data and annotation review. Store code in immutable files/blob storage and refer to it with a path plus SHA-256 hash. 

## **5. Canonical normalized schema** 

### **5.1 Submissions table: one row per attempt** 

|**Field**|**Example/type**|**Rule**|
|---|---|---|
|submission_id|TL-SUB-000001|TraceLearn-generatedprimarykey.|
|dataset_source|CODENET / CODESTREAM / PROGPEDIA /<br>TRACELEARN_SYNTHETIC /<br>TRACELEARN_REAL|Controlled vocabulary.|
|source_record_id|original source ID or null|Never discard the source-native ID.|
|source_problem_id|originalproblem ID|Preserve alongside canonical ID.|
|problem_id|TL-P002|Foreign keyto canonicalproblems table.|
|source_learner_id|source ID or null|Onlyif supplied and allowed bysource.|
|learner_id|CODESTREAM:<source-id> or null|Namespace within dataset; never cross-link<br>same-lookingIDs across sources.|
|attempt_order|integer or null|Only source-backed order; never<br>manufacture chronology.|
|timestamp|ISO-8601 or null|Preserveprecision/timezone semantics.<br>i|
|language|C++17|Also retain original language field/version.|
|source_code_path|relativepath/object key|Immutable code artifact.|
|source_code_sha256|hash|Integrityand exact-duplicate detection.|
|compile_status|success/error/unavailable|Onlywhen observed or available.|
|runtime_status|success/error/timeout/unavailable|Onlywhen observed or available.|
|correct|true/false/null|Onlyif source verdict semantics support it.|
|source_verdict|original string|Preserve source's exact verdict.|
|test_results_ref|reference or null|Storeper-test rows separately.|
|concept_tags|array/stringor null|Source tags or documented mappings.|
|source_misconception_label|original label or null|Never overwrite.|
|tracelearn_label|CPP-M01 or null|Onlymapped/annotated when defensible.|
|label_status<br>i|unlabelled/source_label/mapped/<br>human_reviewed/adjudicated/<br>synthetic_controlled|Records label provenance.<br>i|
|label_confidence|numeric or null|Onlywith a defined annotationprotocol.|
|state_label|NEW/PERSISTENT/IMPROVING/RESOLVED/<br>RECURRED/TEACHER_REVIEW or null|Requires valid trajectory evidence.|
|hint_event_ref|reference or null|Link to hint/feedback table.|
|split|train/validation/test/external_eval/<br>synthetic_dev|Set through versioned manifest.|
|provenance_id|PROV-...|Required reference to<br>source/version/transformation.|



### **5.2 Related tables** 

|**Table**|**Minimum fields andpurpose**|
|---|---|
||**i**<br>problem_id, dataset_source, source_problem_id, statement,|
|problems|input/output specification, constraints, concept_tags, difficulty,<br>source_url, provenance_id|



Working document • Preserve provenance and label semantics 

#### TRACELEARN | DATASET ENGINEERING MASTER PLAN 

|test_cases|test_case_id, problem_id, category, input_ref, expected_output_ref,<br>visibility, origin, provenance_id; never expose hidden tests in student<br>UI|
|---|---|
|test_results|submission_id, test_case_id, outcome, actual/expected output refs,<br>stderr ref,environment,duration_ms,memory_bytes|
|evidence_items|evidence_id, submission_id, source_type, detector_id/version,<br>misconception_id, direction=support/conflict, strength, explanation,<br>source span,created_at|
|annotations|annotation_id, submission_id, annotator, taxonomy_version, label,<br>uncertainty,rationale,adjudication status,timestamp|
|trajectories|trajectory_id, namespaced learner_id, problem/concept, ordered<br>submission IDs,source and temporal validity|
|hint_events|hint_event_id, submission_id, hint_level/type, delivered_at, response<br>reference|
|provenance|provenance_id, source/version, download date, URL, licence,<br>checksum,transformation version,notes|
|label_mapping|source_name, source_label, taxonomy_version, target label, mapping<br>method,reviewer,rationale,status|



## **6. Normalization pipeline: repeatable stages** 

### **0. Register source** 

Before download, record canonical URL, version/date, licence/terms, language, expected files/tables, permitted use and intended TraceLearn role. 

### **1. Immutable raw storage** 

Keep original archive and extracted files unchanged. Record SHA-256, file size, download date and version. Raw files are gitignored. 

### **2. Inspect source** 

Generate inventory, row counts, column names, missingness, language/label distributions, ID uniqueness and licence notes before coding a parser. 

### **3. Source-specific parser** 

One parser per dataset. Emit intermediate records while retaining source-native IDs and relevant original columns. 

### **4. Canonical IDs** 

Create TraceLearn IDs plus mapping tables. Namespace learner IDs by source. Never assume identical-looking IDs identify the same person across datasets. 

### **5. Normalize fields** 

Normalize language spellings, verdicts, booleans, timestamps, missing values and concept tags; preserve original values in parallel. 

### **6. Source-code handling** 

Preserve code, record hash, detect exact duplicates and flag near-duplicates. Do not silently rewrite code. 

### **7. Label mapping** 

Keep source label, TraceLearn mapping, model prediction and human review separate. Uncertain mappings remain null. 

Working document • Preserve provenance and label semantics 

TRACELEARN | DATASET ENGINEERING MASTER PLAN 

### **8. Evidence extraction** 

Run versioned C++ static, compile/runtime/test and history extractors. Store each evidence item with version, direction, rationale and source span where available. 

### **9. Quality checks** 

Validate schema, keys, duplicates, missingness, label validity, outcome consistency and split leakage. Emit a report; fail CI on critical errors. 

### **10. Split creation** 

Use versioned split manifest. Group learners for history-aware evaluation; hold out problems for generalization; forbid future information in earlier-event features. 

### **11. Frozen release** 

Record release ID, taxonomy/mapping versions, parser commit, checksums and quality report. Every experiment must cite this release. 

## **7. Source-specific rules** 

### **Project CodeNet** 

Keep original verdict and normalize only known values. Preserve CPU/memory/code-size units. Accepted means accepted by the source judge, not misconception-free. Online-judge users are not necessarily novice classroom learners, so do not claim classroom representativeness. 

### **CodeStream** 

Preserve sequential verdict traces and attempt order. Verify whether order is per learner, per problem or per learner/problem. Link problem/test tables using source-native IDs. Never shuffle away chronology for temporal experiments. 

### **PROGpedia** 

Retain code property graph files and source-code links. Validate referential integrity from graph records to submission/exercise. CPG-derived features are structural evidence, not misconception labels. Verify language per record. 

### **McMining** 

Keep original Python source and label. Map only when the C++ semantic analogue is defensible. Python-specific behavior must not be translated to a C++ label by name similarity alone. 

### **Optional Python datasets** 

ProgFeed, CSEDM, HELP-DKT and FalconCode can inform feedback/history methodology. Keep them separate from C++ training unless a clearly defined cross-language transfer experiment is being conducted. 

## **8. C++ taxonomy and label governance** 

The existing starter pack has CPP-M01–CPP-M08 as a draft taxonomy. Before large-scale labelling, add a belief statement, positive pattern, counter-evidence, diagnostic tests, C++ semantic justification, known false positives and uncertainty rules for each label. 

|**ID**|**Draft label**|**Evidence signal**|**Caution**|
|---|---|---|---|
|CPP-M01|Exclusive upper bound treated as<br>inclusive|i <= n while iterating n elements|Boundary bug may be a typo, not<br>a stable belief.|



Working document • Preserve provenance and label semantics 

TRACELEARN | DATASET ENGINEERING MASTER PLAN 

|CPP-M02|Element/value confused with<br>index/position|Returns maximum value when<br>asked for index; sums i instead of<br>a[i]|Confirm problem contract first.|
|---|---|---|---|
|CPP-M03|Printing treated as equivalent to<br>returning|Helper prints instead of returning<br>the required result|May be valid design unless the<br>contract requires return.|
|CPP-M04|Index equal to container size<br>treated as valid|Accesses a[n] for n elements|Define separately from M01.|
|CPP-M05|Compound boolean comparison<br>misunderstood|lo <= x <= hi used in C++ range<br>test|Validate with below/at/above-<br>bound tests.|
|CPP-M06|Assignment/equality confusion|x = target where x == target is<br>required|Assignment can be deliberate;<br>inspect context.|
|CPP-M07|Recursion/iteration does not<br>progress|Recursive call repeats same<br>state without reachingbase case|Timeout alone is not enough;<br>inspect state change.|
|CPP-M08|Loop expected to terminate<br>without state update|Loop control variable not<br>changed toward exit|Other exit paths may exist.|



A label firing is a hypothesis, not proof of a student's belief. Keep uncertain and conflicting cases; use a written annotation protocol and double-review a pilot subset. 

## **9. Synthetic data generation: how to make it properly** 

The previously created starter pack has 8 problems, 48 C++17 submission examples, 24 tests and 48 evidence records, all marked curated_synthetic. It is a controlled fixture set, not human-validated ground truth. Keep its role explicit. 

### **9.1 Recommended generation procedure** 

1. Define each active misconception as a precise target belief plus positive pattern, counter-evidence, expected symptom and diagnostic test. 

2. Start from a known-correct reference solution and apply one controlled mutation at a time. Avoid generating code first and guessing its label afterward. 

3. Create varied surface forms (variable names, formatting, loop form, helper function) without changing the intended semantic mutation. 

4. Generate three categories: positive target pattern, negative/correct control, and ambiguous/unrelated-bug control. 

5. Compile and execute every generated example in a restricted environment; store compiler/runtime outcomes and pertest results. 

6. Record generator version, random seed, mutation ID, parent solution, target label, test suite version, compiler version and validation status. 

7. Run the same evidence extractor used by the product. Do not hard-code the expected evidence output as if it were an actual extractor result. 

8. Human-review a sample. Injected labels are known labels for controlled tests, not proof that the same code pattern always reveals a real learner's belief. 

### **9.2 Synthetic dataset files** 

|**File**|**Purpose**|
|---|---|
|synthetic_problem_specs.csv|Problem contract,constraints,concepts and reference solution ID.|
|synthetic_mutations.csv|Mutation ID, target label, transformation rule, applicability, expected<br>evidence and falsepositives.|
|synthetic_submissions.csv|Code ID/path/hash, parent solution, mutation ID, target label,<br>generator version/seed and compile/run validation.|
|synthetic_test_cases.csv|Input, expected output, category and misconception distinction being<br>tested.|
|synthetic_execution_results.csv|Per-code/per-test actual output, status, exit code, duration and<br>stderr.|
|synthetic_evidence.csv|Evidence emitted bythe actual versioned extractor.|
|synthetic_review.csv|Human review,disagreements,corrections and notes.|



Working document • Preserve provenance and label semantics 

TRACELEARN | DATASET ENGINEERING MASTER PLAN 

### **9.3 Mutation examples** 

|**Label**|**Mutation**|**Diagnostic checks**|
|---|---|---|
|CPP-M01|Change i < n to i <= n|n=1 and boundary-focused tests; check<br>bounds evidence.<br>f|
|CPP-M02|Return max value when problem asks for its<br>index|Test where maximum value differs from its<br>index.|
|CPP-M03|Print from helper and use void instead of<br>returningresult|Check caller/function contract.|
|CPP-M04|Change a[n-1]to a[n]|Bounds-check/sanitizer test wherepossible.|
|CPP-M05|Change lo <= x && x <= hi to lo <= x <= hi|Values below,equal to and above bounds.|
|CPP-M06|Replace == with = in condition|Cases where target is zero and nonzero.|
|CPP-M07|Call recurse(n)rather than recurse(n-1)|Smallpositive n with timeoutprotection.|
|CPP-M08|Remove/update loop counter incorrectly|Timeout protection plus static inspection of<br>loopstate.|



### **9.4 Example generator metadata contract** 

submission_id: SYN-SUB-0001 problem_id: SYN-P002 target_label: CPP-M02 label_status: synthetic_controlled mutation_id: RETURN_VALUE_NOT_INDEX parent_solution_id: REF-P002-V1 generator_version: 0.1 seed: 1042 compiler: g++ <version> compile_status: success test_suite_version: P002-tests-v1 evidence_extractor_version: evidence-v1 provenance: TRACELEARN_SYNTHETIC review_status: not_reviewed 

Use deterministic mutation scripts first. LLM-generated variants can be added later, but must be compiled, tested, deduplicated and reviewed. An LLM's own label is not ground truth. 

## **10. Data quality gates** 

|**Check**|**Required rule**<br>i|**Failure behavior**|
|---|---|---|
|Schema|Required fields/types valid|Fail CI on missingkeys/wrongtypes.|
|Provenance|Every row links to source/version or generator<br>run|Fail release if missing.|
|Foreign keys|Submissions link to known problems where<br>possible|Fail on dangling links.|
|Labels|Labels belong to taxonomy version or remain<br>null|Unknown labels fail; uncertain mappings stay<br>null.|
|Outcome consistency|Normalized correctness follows documented<br>source status semantics|Flag contradictions.|
|Duplicates|Hashes and near-duplicate clusters recorded|Fail if duplicates leak across train/test.|
|Chronology|Attempt order is source-backed|Never invent order/timestamps.|
|Leakage|Learners grouped for history-aware<br>evaluation|Fail if same learner appears in train and<br>holdout.|
|Synthetic separation|Synthetic has explicit provenance and is<br>excluded from real holdout|Fail release if mixed.|
|Licence|Licence and allowed use recorded|Unknown/unpermitted redistribution blocks<br>sharing.|



Working document • Preserve provenance and label semantics 

TRACELEARN | DATASET ENGINEERING MASTER PLAN 

## **11. Train/validation/test design** 

- Do not randomly split attempts from the same learner across train and final test when history features can leak identity or trajectory. 

- Primary evaluation: group by learner where stable learner IDs exist. 

- Generalization evaluation: hold out problems/problem families to test transfer beyond templates. 

- Temporal evaluation: only use evidence available at or before the prediction time. Never use later attempts, hints or annotations to predict earlier states. 

- Keep synthetic development/unit-test results separate from real-data performance. Synthetic examples are not a realworld holdout. 

- Freeze taxonomy, mapping, extractor version, feature definitions and split manifest before final evaluation. 

## **12. Final dataset release and example row** 

data_release_id: tracelearn-cpp-v0.1 taxonomy_version: cpp-taxonomy-0.1 parser_commit: <git SHA> created_at: <ISO-8601> sources: CODESTREAM: <version/checksum/licence> PROGPEDIA: <version/checksum/licence> CODENET: <version/checksum/licence> MCMINING: <version/checksum/licence> synthetic_generator_version: <version> quality_report: reports/data_quality_report.csv 

Illustrative row only, not a real student record: 

submission_id=TL-SUB-000001 dataset_source=TRACELEARN_SYNTHETIC source_record_id=null problem_id=TL-P002 learner_id=null attempt_order=null language=C++17 source_code_path=synthetic/generated_submissions/TL-SUB-000001.cpp correct=false source_misconception_label=null tracelearn_label=CPP-M02 label_status=synthetic_controlled state_label=null split=synthetic_dev provenance_id=PROV-SYN-000001 

Synthetic examples should not receive real learner IDs, fabricated attempt histories or real learner-state labels. 

## **13. Milestones and acceptance criteria** 

|**Milestone**|**Deliverable**|**Done when**|
|---|---|---|
|M1: contract|Taxonomy v0.1, canonical schema, source<br>manifest,data card|Each active label has positive/counter-<br>evidence and each source has a role/licence.<br>i|
|M2: CodeStream|Parser and small normalized release|Reproducible row counts, field map, C++<br>filter and source-backed attempt order.|
|M3: PROGpedia|Parser and CPG link mapping|Source/CPG referential checkspass and|



Working document • Preserve provenance and label semantics 

TRACELEARN | DATASET ENGINEERING MASTER PLAN 

|||language scope is verified.|
|---|---|---|
|M4: CodeNet|Narrow C++ subset and selection script|Subset is reproducible; raw archive stays<br>outside Git.|
|M5: McMining|Taxonomy extraction and mapping table|Original labels preserved; all proposed<br>mappingsjustified.|
|M6: synthetic suite|Mutation generator, controls, tests and<br>evidence outputs|Each active label has positive, negative and<br>ambiguous examples; all code<br>compiled/tested.|
|M7: quality/splits|Validation scripts, leakage report, frozen split<br>manifest|Critical checks pass; synthetic and real data<br>separated.|
|M8: product integration|Seed data plus submission/evidence API|A live C++ submission produces normalized<br>attempt, test results and evidence with<br>provenance.|
|M9: release|Data card, checksums, quality report and<br>version tag|Release can be reproduced from<br>documented commands and pinned<br>versions.|



## **14. What you can safely claim** 

|**Defensible wording**|**Avoid**|
|---|---|
|CodeNetprovides C++ submissions and source verdict/metadata.|Millions of CodeNet submissions are misconception-labelled.<br>i|
|McMininginforms taxonomyand controlled detector tests.|McMiningvalidates a C++ misconception classifier.|
|CodeStream supports attempt-history/verdict-trace experiments.|A sequence of wronganswersproves apersistent misconception.|
|Synthetic mutations test known injectedpatterns.<br>i|Synthetic accuracy predicts real-world learnerperformance.|
|Human-reviewedpilot data willprovideproject-specific labels.|The taxonomyis validated before annotation/agreement analysis.|
|Diagnosis is a hypothesis supported byevidence.|The detectorproves what a learner believes.|



## **15. Immediate checklist** 

- Resolve the Python-versus-C++ discrepancy across blueprint, slides, report and taxonomy. 

- Create source_manifest.csv with source URLs, versions, licence, download date and checksums. 

- Download CodeStream and PROGpedia; inspect their actual tables before implementing parsers. 

- Use CodeNet mini/narrow subset before the full archive. 

- Download McMining but preserve Python code and original labels. 

- Build one source parser at a time; report row counts and mappings. 

- Freeze canonical schema and taxonomy version. 

- Use the 48-example synthetic starter pack as a CI fixture, then add versioned mutation generation. 

- Automate provenance, key integrity, duplicate, label and split-leakage checks. 

- Keep external, synthetic and human-reviewed pilot data distinguishable in every table/report. 

## **16. Source basis and links** 

Blueprint-derived: Appendix D lists McMining/McMiner, ProgFeed, CSEDM 2019/ITAP, HELP-DKT, FalconCode, CodeStream, PROGpedia and Project CodeNet with roles/limitations. The blueprint also calls for a common normalized schema, nullable misconception labels when unsupported, provenance, and learner/problem/temporal leakage precautions. 

Recommended engineering additions: the tables, parser stages, synthetic mutation workflow, quality gates and milestone criteria are proposed implementation choices, not claims that the original documents already implemented them. 

- https://github.com/IBM/Project_CodeNet 

- https://github.com/taisazero/mcminer 

- 

- 

- https://zenodo.org/records/7449056 

- https://data.mendeley.com/datasets/n77t7z9zcr/1 

Working document • Preserve provenance and label semantics 

TRACELEARN | DATASET ENGINEERING MASTER PLAN 

- https://github.com/umass-ml4ed/progFeed-dataset-public 

- https://github.com/thomaswp/CSEDM2019-Data-Challenge 

- https://github.com/liangyubuaa/HELP-DKT 

- https://huggingface.co/datasets/koutch/falcon_code 

Re-check current licence/access terms before redistribution and cite each original dataset paper/repository in the FYP report. 

Working document • Preserve provenance and label semantics 

