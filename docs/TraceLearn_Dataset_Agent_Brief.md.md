# TraceLearn: Dataset Intelligence, Normalization & ML Implementation Brief

## 1. Project Overview

**Project name:** TraceLearn
**Primary programming language:** C++
**Proposed ML model:** XGBoost
**Primary objective:** Identify likely beginner C++ programming misconceptions from code submissions and provide evidence-based, targeted educational feedback.

You are an AI coding and research agent working on TraceLearn. Before writing code, inspect the existing project repository, understand the current implementation, and inventory all downloaded datasets.

Your responsibility is to build a reliable data pipeline that connects programming submissions to observable evidence, validated misconception labels, machine-learning predictions, and useful educational feedback.

**Do not simply merge all downloaded datasets into one CSV and train XGBoost.** The datasets may have different schemas, languages, licenses, label definitions, and intended purposes. Some may contain generic source code or programming outcomes without any labels that identify misconceptions.

Your first job is to establish what each dataset actually contains and how it can contribute to TraceLearn.

### Mandatory rules

1. Inspect the actual downloaded files before making claims about their contents.
2. Never invent dataset columns, labels, row counts, test results, or licensing information.
3. Preserve original datasets unchanged.
4. Keep a record of the origin of every normalized record.
5. Distinguish source-provided labels, human annotations, rule-generated labels, and synthetic labels.
6. Do not assume that a wrong submission reveals the student's underlying misconception.
7. Do not use synthetic-only evaluation results as evidence of real-world performance.
8. Use C++ as the target language unless the current approved project specification says otherwise.
9. Keep the misconception taxonomy explicit and versioned.
10. Prevent training/test leakage through duplicate code, related submissions, shared problems, or synthetic variants.
11. Prefer deterministic analysis when it can reliably identify a defect.
12. Report uncertainty and limitations honestly.
13. Do not run downloaded code without a sandbox and resource limits.
14. Do not redistribute downloaded datasets without checking their licenses and usage restrictions.
15. If the downloaded data is not accessible in your workspace, ask for its actual location or for the files. Do not pretend to have access to the user's computer.

---

## 2. What TraceLearn Is Trying to Achieve

TraceLearn is a C++ learning platform intended to help students understand why their code may be incorrect.

Traditional programming judges commonly report outcomes such as:

* Accepted
* Wrong Answer
* Compilation Error
* Runtime Error
* Time Limit Exceeded

These outcomes tell us what happened, but they do not necessarily explain the underlying conceptual issue.

TraceLearn aims to go further by identifying observable patterns that may indicate a beginner misconception and using those patterns to offer relevant feedback.

### Intended system pipeline

1. A student submits C++ code for a programming problem.
2. TraceLearn associates the code with the problem and any available attempt history.
3. The code is compiled, analyzed, or executed against appropriate tests.
4. The system extracts structured features and observable evidence.
5. XGBoost predicts one or more likely misconception categories from those features.
6. The feedback layer uses the prediction and supporting evidence to select an explanation or hint.
7. The system records predictions and outcomes for later evaluation.

This describes the intended architecture. Inspect the existing repository to determine which parts have already been implemented and which remain planned.

### What XGBoost is supposed to predict

The initial proposed prediction task is:

> Given structured features extracted from a C++ submission and its context, predict the most plausible beginner misconception category or categories.

This is a supervised-learning problem only if suitable target labels are available.

Before implementation, decide whether the model will use:

* **Single-label classification:** one primary misconception per example.
* **Multi-class classification:** one mutually exclusive class from a set of classes.
* **Multi-label classification:** several misconceptions can coexist in one submission.

Do not treat these formulations as interchangeable.

A single-label baseline may be simpler for an initial prototype, but the system must acknowledge that real submissions can contain multiple problems.

### What XGBoost cannot do automatically

XGBoost does not directly understand raw C++ source code in the way a human instructor does. The source code must first be converted into structured features.

It also cannot infer reliable misconception labels merely from:

* A wrong-answer verdict.
* A compilation error.
* A runtime error.
* The problem ID.
* A code repository tag.
* A generic source-code example.

A prediction is an estimate of a likely conceptual difficulty, not proof of the student's thought process.

---

## 3. Dataset Inventory: Sources and Intended Uses

The following datasets were identified during planning. Their descriptions are initial context, not confirmation of the exact contents of the downloaded copies.

The agent must verify each source using its actual files, README, data dictionary, associated publication, and license.

## 3.1 Project CodeNet

**Source repository:**
https://github.com/IBM/Project_CodeNet

**Previously identified archive:**
https://codait-cos-dax.s3.us.cloud-object-storage.appdomain.cloud/dax-project-codenet/1.0.0/Project_CodeNet.tar.gz

### Why it matters

Project CodeNet is a large programming-submission corpus with submissions in multiple languages and associated problem/submission metadata.

It is a potential source for C++ code examples, code analysis, feature extraction, and problem-level experiments.

### Potentially useful data

Depending on the downloaded version, investigate whether it contains:

* C++ source submissions.
* Problem identifiers.
* Submission identifiers.
* Language information.
* Verdicts or submission outcomes.
* Submission metadata.
* Problem metadata.
* Attempt relationships or timestamps.

Do not assume all of these fields exist in every downloaded component.

### Recommended use in TraceLearn

Use CodeNet as a candidate source for C++ submissions and code-feature development.

It may help the team:

* Test C++ parsing and feature extraction.
* Investigate patterns associated with incorrect solutions.
* Develop a bounded corpus for experiments.
* Group code by problem.
* Test deduplication and ingestion pipelines.

### Important limitations

A submission verdict is not a misconception label.

For example, a wrong answer could result from a misunderstanding of an algorithm, a missing edge case, an implementation mistake, an incorrect interpretation of the problem, or another issue.

Do not automatically convert `Wrong Answer` into a misconception such as `CPP-M01`.

### Required audit

1. Inspect the archive structure and metadata.
2. Identify the fields used to associate submissions with problems.
3. Count the C++ submissions actually present.
4. Count unique problems and submissions.
5. Determine whether test cases are included.
6. Determine whether verdicts and their definitions are documented.
7. Check exact and near-duplicate code.
8. Check source documentation and applicable licensing conditions.
9. Record archive completeness and extraction errors.

**Initial role:** Candidate source for C++ submissions, metadata, and feature development.

---

## 3.2 CodeStream

**Previously identified source page:**
https://data.mendeley.com/datasets/n77t7z9zcr/1

### Why it matters

CodeStream was identified as a candidate programming-education dataset.

Its actual usefulness depends on the downloaded files and whether they contain source code, attempts, learning activity, outcomes, labels, or other relevant metadata.

### Recommended use

Investigate whether it can contribute:

* Programming submissions.
* Attempt histories.
* Problem context.
* Student learning activity.
* Error or outcome information.
* Educational annotations.

These are possibilities to verify, not guaranteed fields.

### Required audit

1. Read the dataset description and associated publication.
2. Inventory all files and file formats.
3. Inspect every relevant table's columns and key relationships.
4. Determine the programming languages represented.
5. Establish whether submissions can be linked to sequential attempts.
6. Identify what any outcome or label actually means.
7. Determine whether labels are human-assigned or automatically generated.
8. Verify licensing and redistribution conditions.
9. Assess whether its records can be mapped into TraceLearn's canonical schema.

**Initial role:** Potential source of programming-education data and submissions, subject to schema and label verification.

---

## 3.3 PROGpedia

**Previously identified source page:**
https://zenodo.org/records/7449056

### Why it matters

PROGpedia was identified as a candidate programming-education resource.

Its contribution to TraceLearn must be established by inspecting the actual downloaded files and documentation.

### Recommended use

Investigate whether it provides:

* Source code.
* Programming problems.
* Error or outcome information.
* Educational annotations.
* Student attempts.
* Relevant metadata.

If annotations are available, determine their meaning and reliability before mapping them to TraceLearn labels.

### Required audit

1. Read the dataset record and associated paper.
2. Inspect the data dictionary and license.
3. Inventory all downloaded files.
4. Determine the unit represented by each row.
5. Identify the programming languages represented.
6. Establish whether labels are source-provided, human-assigned, or automatically inferred.
7. Preserve source-native labels.
8. Document any mapping from source labels to TraceLearn's taxonomy.
9. Leave labels unmapped when their meanings do not match.

**Initial role:** Potential source of structured programming-education data, depending on verified contents.

---

## 3.4 McMining / McMiner

**Previously identified repository:**
https://github.com/taisazero/mcminer

### Why it matters

McMining/McMiner was identified as a resource to investigate for programming misconception patterns, code examples, and taxonomy development.

Do not assume that the repository contains a ready-made dataset suitable for supervised C++ misconception classification. First establish whether it contains data, a tool, rules, examples, or a combination.

### Recommended use

Potential uses include:

* Investigating how misconceptions are defined.
* Identifying observable patterns related to programming errors.
* Designing candidate taxonomy categories.
* Developing rule-based evidence detectors.
* Creating carefully reviewed examples.

### Required audit

1. Read the repository documentation.
2. Identify the associated research paper, if available.
3. Determine whether the downloaded artifact is a dataset, tool, or both.
4. Identify the programming languages covered.
5. Determine how patterns and labels were produced.
6. Distinguish human-validated annotations from automatically detected patterns.
7. Verify the license.
8. Map only concepts that genuinely align with TraceLearn's taxonomy.

**Initial role:** Taxonomy inspiration and possible evidence-pattern development. Direct training use must be justified separately.

---

## 3.5 ProgFeed

**Previously identified repository:**
https://github.com/umass-ml4ed/progFeed-dataset-public

### Why it matters

ProgFeed was identified as a possible source of programming-learning or feedback-related data.

The actual files must be examined before deciding whether it contributes source code, learner activity, feedback, outcomes, or other information.

### Recommended use

Investigate whether the data can help with:

* Understanding how feedback is represented.
* Studying programming-learning interactions.
* Developing feedback evaluation methods.
* Supporting relevant educational experiments.

Do not assume feedback text is equivalent to a validated misconception label.

### Required audit

* Read the README, associated publication, and license.
* Inspect the actual data files.
* Determine programming-language coverage.
* Identify whether source code and attempt histories exist.
* Distinguish feedback text from classification labels.
* Establish whether the data is compatible with the C++ target task.
* Document restrictions and limitations.

**Initial role:** Potential feedback research or supporting educational data.

---

## 3.6 CSEDM 2019 / ITAP

**Previously identified repository:**
https://github.com/thomaswp/CSEDM2019-Data-Challenge

### Why it matters

This source was identified as a possible programming-education dataset for learning analytics, event data, or related experimental methods.

### Recommended use

Investigate the original task and target variable before considering any data for TraceLearn.

The source may be useful for learning analytics methodology even if it is not suitable for direct C++ misconception training.

### Required audit

1. Read the challenge documentation and paper.
2. Determine the original prediction target.
3. Identify the unit of observation.
4. Determine language and course context.
5. Inspect the original train/test split rules.
6. Identify whether code-level features and misconception labels exist.
7. Do not rename the original target as a TraceLearn misconception without evidence.

**Initial role:** Supporting research and methodology unless the verified schema directly supports the target task.

---

## 3.7 HELP-DKT

**Previously identified repository:**
https://github.com/liangyubuaa/HELP-DKT

### Why it matters

HELP-DKT was identified as a potentially relevant knowledge-tracing or learning-related resource.

Knowledge tracing and misconception classification are different tasks.

A knowledge-tracing dataset may represent learner responses, skills, or knowledge states rather than source-code misconceptions.

### Recommended use

Investigate whether the source offers useful learning analytics methodology or contextual data.

### Required audit

* Distinguish the research implementation from the dataset itself.
* Determine whether data is included or must be downloaded separately.
* Identify the original model's inputs and prediction target.
* Establish whether the target means correctness, skill mastery, knowledge state, or something else.
* Determine whether the target task and data unit align with TraceLearn.

**Initial role:** Supporting learning analytics research unless direct suitability is established.

---

## 3.8 FalconCode

**Previously identified dataset page:**
https://huggingface.co/datasets/koutch/falcon_code

### Why it matters

FalconCode was identified as a candidate code corpus.

General-purpose code corpora may be useful for code-processing experiments, but they may not represent student submissions or contain educational annotations.

### Recommended use

If the downloaded files primarily contain general code, investigate their suitability for:

* Parser testing.
* Language-identification checks.
* Feature-extraction stress tests.
* General code-processing experiments.

Do not treat generic code examples as labeled learner submissions.

### Required audit

1. Inspect the dataset card and actual downloaded configuration.
2. Identify the programming languages.
3. Determine the provenance of code examples.
4. Identify whether records represent student submissions or general code.
5. Inspect labels and determine what they mean.
6. Check licensing and redistribution restrictions.
7. Decide whether the data is relevant to the target educational task.

**Initial role:** Supporting code-processing experiments if appropriate, not automatically direct misconception training.

---

## 3.9 Dataset prioritization

After auditing the files, classify each source according to its actual contribution.

| Category                   | Meaning                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| Direct supervised training | Has appropriate features and trustworthy target labels               |
| Human annotation candidate | Has useful code but needs qualified labeling                         |
| Feature development        | Useful for developing or validating feature extraction               |
| Problem metadata/tests     | Supplies problem statements, test cases, or context                  |
| Taxonomy inspiration       | Helps define concepts but is not a direct training source            |
| Feedback research          | Helps study feedback representation or evaluation                    |
| Synthetic pipeline testing | Used for controlled pipeline validation                              |
| Exclude                    | Task mismatch, licensing, quality, or provenance makes it unsuitable |

Do not combine every source merely because it has been downloaded.

---

## 4. How the Dataset Supports XGBoost

XGBoost requires structured input features and target labels.

The dataset is not simply a collection of C++ files. It must eventually support a relationship between observable evidence and a defined outcome.

### Example training row

The following is illustrative, not a claim that these columns already exist:

| Feature                                   | Example value |
| ----------------------------------------- | ------------: |
| `has_out_of_bounds_access_evidence`       |             1 |
| `loop_upper_bound_matches_container_size` |             1 |
| `loop_has_progress_update`                |             1 |
| `compile_error_count`                     |             0 |
| `failed_boundary_tests`                   |             2 |
| `is_cpp17`                                |             1 |
| `label`                                   |     `CPP-M04` |

The feature values describe observable code or execution behavior. The label represents the target category.

A reliable pipeline must explain how every feature is calculated and how every target label was assigned.

### Core distinction

**Features (X):** Information available at prediction time, such as code patterns, compiler diagnostics, or test outcomes.

**Target (y):** The validated misconception label that the model is trained to predict.

**Metadata:** Source IDs, file paths, dataset names, problem IDs, learner IDs, and other provenance information. Metadata is not automatically a valid model feature.

**Evidence:** The observable reason supporting an interpretation, such as a failing boundary test or a relevant source-code location.

Never include the target label or information derived from it as a feature. That would create label leakage.

### Candidate feature families

#### A. Submission context

Potential features:

* Programming language.
* C++ standard.
* Problem category, if reliably defined.
* Submission sequence information, if available and allowed.
* Relevant problem characteristics.

For a generalization experiment, do not allow problem or source IDs to become shortcuts for memorization.

#### B. Compilation features

Potential features:

* Whether compilation succeeded.
* Number of compiler diagnostic categories.
* Normalized diagnostic types.
* Relevant warnings.

Record compiler name, version, and flags because diagnostic behavior can vary between environments.

#### C. Static code features

Potential features:

* Loop types and bounds.
* Array, vector, and string indexing patterns.
* Use of `.size()` and comparison operators.
* Assignment versus equality comparison in relevant contexts.
* Recursion structure and progress toward base cases.
* Return statements versus output statements.
* Boolean-expression structure.
* Abstract syntax tree metrics.
* Control-flow information.

Prefer parsing and structured analysis over brittle regular expressions when feasible.

#### D. Execution and testing features

Potential features:

* Number of passed and failed tests.
* Failure categories, if defined by test metadata.
* Crash and timeout indicators.
* Sanitizer findings.
* Observed versus expected outputs.
* Loop iteration counts or runtime traces, if deliberately instrumented.

Only populate execution fields if they were actually measured.

#### E. Attempt history

If reliable, permitted attempt histories exist, possible features include:

* Previous attempt outcomes.
* Changes between attempts.
* Hints shown before an attempt.
* Relevant prior feedback.

Do not use future attempts or future outcomes to predict an earlier submission.

### Start with baselines

Before evaluating XGBoost, establish simple baselines:

1. Majority-class baseline.
2. Rule-based baseline, where appropriate.
3. A simple statistical classifier, if appropriate.
4. XGBoost.

If XGBoost does not outperform simpler approaches under leakage-safe evaluation, investigate the features and labels before increasing model complexity.

---

## 5. Proposed Canonical Schema

The purpose of normalization is to make data from different sources interoperable without erasing their original meaning.

Keep source-native data intact and map only verified fields into a shared schema.

The schema below is a proposal. Modify it based on the real data and existing project architecture.

### 5.1 `problems`

One row per programming problem.

Suggested fields:

* `problem_id`
* `source_dataset`
* `source_problem_id`
* `title`
* `statement_text`
* `input_description`
* `output_description`
* `constraints`
* `language_scope`
* `difficulty`
* `source_license`
* `provenance_ref`

Only include fields that exist or can be responsibly derived.

### 5.2 `submissions`

One row per submission/version.

Suggested fields:

* `submission_id`
* `source_dataset`
* `source_submission_id`
* `problem_id`
* `learner_id`
* `submitted_at`
* `language`
* `language_standard`
* `source_code_raw_ref`
* `source_code_sha256`
* `is_synthetic`
* `generator_version`
* `source_verdict`
* `source_verdict_definition`
* `annotation_status`
* `provenance_ref`

Use nullable fields where information is absent. Do not invent learner identities, timestamps, or submission histories.

### 5.3 `test_cases`

One row per available test case.

Suggested fields:

* `test_case_id`
* `problem_id`
* `source_test_case_id`
* `input_ref`
* `expected_output_ref`
* `test_category`
* `test_source`
* `provenance_ref`

Do not fabricate test cases for datasets that do not include them.

### 5.4 `test_results`

One row per submission/test-case result.

Suggested fields:

* `submission_id`
* `test_case_id`
* `observed_output_ref`
* `passed`
* `exit_status`
* `runtime_ms`
* `memory_bytes`
* `timed_out`
* `crashed`
* `sanitizer_category`
* `compiler_name`
* `compiler_version`
* `execution_environment`
* `result_source`

Only include results that were actually observed or supplied by the source.

### 5.5 `evidence_items`

One row per observable evidence item.

Suggested fields:

* `evidence_id`
* `submission_id`
* `evidence_type`
* `evidence_code`
* `description`
* `source_span_start`
* `source_span_end`
* `related_test_case_id`
* `observed_value`
* `tool_name`
* `tool_version`
* `reproducible`
* `provenance_ref`

Examples include compiler diagnostic categories, failed boundary tests, invalid indexing evidence, or loop-control observations.

Evidence is not the same as a misconception label.

### 5.6 `annotations`

One row per annotation event or label assignment.

Suggested fields:

* `annotation_id`
* `submission_id`
* `taxonomy_version`
* `label_id`
* `annotation_source`
* `annotator_id_pseudonym`
* `confidence`
* `rationale`
* `adjudication_status`
* `created_at`

Possible annotation sources include:

* Instructor.
* Trained annotator.
* Source-provided label.
* Rule-generated label.
* Synthetic generator.

Do not collapse disagreements between annotators without recording the adjudication process.

### 5.7 `trajectories`

Optional table for linked attempts.

Suggested fields:

* `learner_id`
* `problem_id`
* `attempt_index`
* `submission_id`
* `event_time`
* `previous_submission_id`
* `hint_count_before_attempt`
* `outcome`

Only create trajectories when identity and ordering are supported by the source.

### 5.8 `hint_events`

Optional table for feedback exposure and subsequent outcomes.

Suggested fields:

* `hint_event_id`
* `submission_id`
* `learner_id`
* `label_id`
* `hint_id`
* `shown_at`
* `feedback_version`
* `subsequent_attempt_id`
* `outcome`

Do not claim that feedback caused improvement without an appropriate evaluation design.

### 5.9 `provenance`

One row per source file or ingested source unit.

Suggested fields:

* `provenance_id`
* `source_dataset`
* `source_version`
* `source_url`
* `downloaded_at`
* `file_path_relative`
* `file_size_bytes`
* `sha256`
* `license`
* `license_evidence_ref`
* `parser_version`
* `ingestion_run_id`
* `notes`

### 5.10 `label_mapping`

A mapping between source-native labels and TraceLearn labels.

Suggested fields:

* `source_dataset`
* `source_label`
* `source_label_definition`
* `target_label_id`
* `mapping_type`
* `mapping_rationale`
* `review_status`
* `reviewer`
* `mapping_version`

Possible mapping types:

* `exact`
* `partial`
* `related_only`
* `unmapped`

Do not force incompatible source labels into the TraceLearn taxonomy.

---

## 6. Initial C++ Misconception Taxonomy

The following taxonomy was proposed during earlier planning. It must be compared against the latest approved project specification and reviewed before being treated as final.

These are proposed concepts, not confirmed labels from the downloaded datasets.

| ID        | Proposed misconception                               | Evidence to investigate                                               | Caution                                                               |
| --------- | ---------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `CPP-M01` | Treating an exclusive upper bound as inclusive       | Boundary failures or an incorrect range endpoint                      | The intended range must be known                                      |
| `CPP-M02` | Confusing an element/value with an index/position    | Values used incorrectly as indexes or indexes treated as values       | Context determines correctness                                        |
| `CPP-M03` | Treating printing as equivalent to returning a value | Function prints when the caller requires a returned value             | Only relevant when the function contract requires a return            |
| `CPP-M04` | Treating an index equal to container size as valid   | Access at index `size()` or a loop that permits that index            | Must confirm container and operation                                  |
| `CPP-M05` | Misunderstanding a compound boolean comparison       | Condition does not implement the intended mathematical range check    | C++ chained comparisons differ from mathematical chained inequalities |
| `CPP-M06` | Confusing assignment with equality comparison        | Assignment appears where an equality test was intended, or vice versa | Assignment in a condition can be intentional                          |
| `CPP-M07` | Recursion or iteration fails to make progress        | Recursive call or loop state does not approach termination            | Analyze the actual control flow                                       |
| `CPP-M08` | Loop fails to update its exit condition              | Relevant condition remains unchanged on an execution path             | Textual patterns alone may be insufficient                            |

### Taxonomy requirements

For every category:

1. Write a precise definition.
2. Define inclusion and exclusion criteria.
3. Create positive examples.
4. Create negative and hard-negative examples.
5. Record the observable evidence required.
6. Define when the label must remain unknown.
7. Check whether annotators can apply the label consistently.
8. Version the taxonomy.

Distinguish between an **observable defect** and an **inferred misconception**.

For example, an out-of-bounds access may be directly observable. Concluding that the student misunderstands zero-based indexing is a further interpretation.

Provide an `unknown`, `insufficient_evidence`, or equivalent pathway. Do not force every wrong submission into one of eight categories.

---

## 7. Dataset Normalization Workflow

### Phase 1: Locate and preserve data

First locate the actual directory containing the downloaded datasets.

If the directory is not accessible in the agent's workspace, ask the user to provide the path or upload the data. Do not assume access to the user's local computer.

Create a recursive inventory that records:

* Relative file path.
* File size.
* File type.
* Archive membership.
* Dataset association.
* SHA-256 hash.
* Whether the file appears to be documentation, metadata, code, labels, or another artifact.

Before extracting large archives, estimate the disk-space requirement.

Never overwrite the original files.

### Suggested directory layout

```text
tracelearn-data/
  raw/
    project_codenet/
    codestream/
    progpedia/
    mcminer/
    progfeed/
    csedm2019/
    help_dkt/
    falcon_code/
  metadata/
    dataset_inventory.csv
    source_register.md
    license_register.csv
    schema_notes/
  interim/
    parsed/
    filtered/
    deduplicated/
  processed/
    canonical/
    features/
    annotations/
    splits/
  reports/
    audit/
    quality/
    model_evaluation/
  synthetic/
    generator/
    generated/
    manifests/
```

Adapt this structure to the existing repository. Avoid creating a second competing structure if the project already has one.

### Phase 2: Audit each source

For every dataset:

1. Read its documentation.
2. Inventory its files.
3. Inspect a small sample safely.
4. Determine the unit of each record.
5. Identify the schema and key relationships.
6. Establish language coverage.
7. Identify available labels and their definitions.
8. Measure missingness and duplicates.
9. Verify licensing and usage restrictions.
10. Document suitability for TraceLearn.

### Phase 3: Build source-specific adapters

Each dataset should have a source-specific ingestion adapter.

An adapter must:

* Read raw files without modifying them.
* Validate required source fields.
* Map verified fields to the canonical schema.
* Preserve source-native values.
* Assign stable TraceLearn IDs.
* Attach provenance.
* Log parsing and validation errors.
* Be safe to rerun without duplicating records.
* Have unit tests and small test fixtures.
* Record adapter version and ingestion run ID.

Do not assume every dataset has the same schema.

### Phase 4: Filter for C++

For the initial C++ task:

* Use documented language metadata where available.
* Use code inspection or a language detector as a fallback.
* Record uncertainty when language identification is ambiguous.
* Preserve the original language value.
* Track C++ standards where known.
* Quarantine empty, truncated, or malformed code rather than silently deleting it.
* Record every exclusion reason.

A `.cpp` extension is useful evidence but should not be the only language-identification method when stronger metadata is available.

### Phase 5: Deduplicate

Use multiple levels of duplicate detection:

1. Exact hash of the raw source.
2. Normalized-source hash where appropriate.
3. Source IDs and problem IDs.
4. Optional near-duplicate detection.

Do not merge records simply because their code is identical. The same code can belong to different learners, problems, or attempts.

Preserve all source records and create duplicate-group metadata.

### Phase 6: Create normalized outputs

Produce versioned, documented outputs such as:

* `problems`
* `submissions`
* `test_cases`
* `test_results`
* `evidence_items`
* `annotations`
* `provenance`
* `label_mapping`
* `dataset_inventory`

Parquet is a useful option for large typed tables if the environment supports it. CSV may be sufficient for small or interchange datasets.

Store source code separately when necessary and use stable references rather than forcing large code blobs into every table.

### Phase 7: Validate the pipeline

At minimum, validate:

* Unique canonical IDs.
* Valid relationships between submissions, problems, tests, and results.
* Valid language values.
* Nonempty code where required.
* Documented handling of character encoding.
* Valid taxonomy IDs and versions.
* Provenance attached to each normalized record.
* Raw files remain unchanged.
* Counts before and after filtering are recorded.
* Repeated ingestion produces consistent results.
* No evaluation data is used during training or feature fitting.

Generate both a machine-readable quality report and a human-readable audit report.

---

## 8. The Critical Problem: Label Quality

The most important question is not whether the downloaded datasets contain enough code.

It is whether the available data can tell TraceLearn **which misconception a submission represents**.

### Possible sources of labels

#### A. Human annotations

Instructors or trained annotators apply the taxonomy to submissions using written guidelines.

This can be a strong source of labels when the annotation process is reliable and ambiguous examples are handled explicitly.

#### B. Source-provided labels

A source may contain categories or labels.

Use them only when their definitions genuinely align with the TraceLearn taxonomy.

#### C. Rule-derived labels

A deterministic rule may detect a specific code pattern or observable defect.

This can be useful, but a detected defect is not automatically proof of a student's misconception.

Record the rule and evaluate its reliability.

#### D. Synthetic labels

A generator may create a controlled code mutation associated with a known target category.

This supports pipeline testing and controlled experiments, but synthetic labels do not prove that the same patterns appear in real student code.

#### E. Instructor-authored examples

Instructors may create problems and expected misconception cases for the custom problem bank.

Record the authoring process and validate that the examples genuinely express the intended issue.

### Do not confuse these prediction tasks

These are distinct:

* Predict accepted versus rejected.
* Predict compilation versus runtime versus wrong-answer outcome.
* Predict whether a specific defect exists.
* Predict a likely underlying misconception.
* Predict whether a student will solve the next problem.
* Predict a learner's knowledge state.

A dataset collected for one task cannot automatically be used for another.

If the available datasets lack misconception labels, explicitly report the gap and propose an annotation plan. Do not quietly convert verdicts into misconception labels.

### Annotation quality process

1. Define the unit being labeled.
2. Write annotation guidelines.
3. Create positive, negative, and ambiguous examples.
4. Have qualified annotators independently label a sample, if feasible.
5. Measure agreement.
6. Investigate disagreements.
7. Adjudicate difficult cases.
8. Preserve original annotations and adjudication history.
9. Report class counts and uncertainty.
10. Exclude or separately handle examples that cannot be labeled confidently.

---

## 9. Synthetic C++ Data Generation

Synthetic data should be used to test the pipeline and create controlled examples of known code patterns.

It must remain clearly distinguishable from authentic learner submissions.

### Recommended generation process

For each taxonomy category:

1. Create or select a correct C++ reference solution.
2. Create tests that establish the intended behavior.
3. Apply a documented mutation that introduces the target issue.
4. Compile the generated program.
5. Run tests in a restricted sandbox.
6. Save observed outputs, diagnostics, exit status, and test results.
7. Record the generator's intended label.
8. Create correct control examples and hard negatives.
9. Manually review a sample of generated records.
10. Store generator version, random seed, parent solution, mutation ID, compiler version, and test-suite version.

### Suggested synthetic manifest

* `synthetic_id`
* `parent_problem_id`
* `parent_solution_hash`
* `mutation_id`
* `generator_version`
* `seed`
* `taxonomy_version`
* `intended_label`
* `is_control`
* `compiler_name_version`
* `test_suite_version`
* `compile_status`
* `test_results_ref`
* `human_review_status`

### Positive and negative examples

For each target misconception, aim to create:

* **Positive examples:** the intended issue is present and supported by evidence.
* **Negative controls:** similar code without the target issue.
* **Hard negatives:** code that looks suspicious but is correct in context.
* **Ambiguous cases:** examples that should not receive a confident label.

Do not generate only obvious broken code. A model may learn artifacts of the mutation procedure instead of transferable features.

### Sandbox requirements

Downloaded or generated programs must not be executed without controls.

Use:

* No network access.
* CPU and memory limits.
* Wall-clock timeout.
* Restricted filesystem access.
* Temporary working directories.
* Process limits where available.
* Captured stdout, stderr, and exit status.

### Previously mentioned starter pack

Earlier planning referred to a synthetic starter pack with:

* 8 problems.
* 48 C++17 submission examples.
* 24 tests.
* 48 evidence records.

These counts are provisional until the actual files are located and inspected.

If this pack exists, classify it as **curated synthetic fixtures**, not real student data. Do not use results from this pack alone to claim real-world accuracy.

---

## 10. Train/Test Splitting and Leakage Prevention

A random row split may produce misleading results when records share a problem, learner, template, or underlying code.

### Recommended evaluation strategy

Create separate development, validation, and held-out test sets.

Where feasible, also run:

1. **Problem-grouped evaluation:** Hold out entire problems to test generalization to unseen problems.
2. **Learner-grouped evaluation:** Keep a learner's attempts in one split when evaluating generalization to new learners.
3. **Source-held-out evaluation:** Train on compatible sources and evaluate on a separate source.
4. **Synthetic-to-real evaluation:** Train with synthetic examples and evaluate on a separately annotated real sample.

Each split answers a different question. Document which form of generalization is being measured.

### Leakage checks

* No exact duplicate code across train and test.
* Check normalized and near-duplicate code groups.
* Keep generated variants of the same parent solution in one split.
* Avoid splitting one learner's attempt history across sets when that leaks identity-specific patterns.
* Keep problem groups together when testing generalization to unseen problems.
* Do not fit preprocessing, feature selection, or calibration using test data.
* Do not use future events to predict past submissions.
* Exclude target-derived features.
* Avoid using source IDs, file paths, or learner IDs as model inputs without a specific justification.

Synthetic and real records must remain distinguishable in every split and report.

---

## 11. Model Evaluation

Do not report accuracy alone, especially if misconception classes are imbalanced.

Report:

* Macro-F1.
* Per-class precision.
* Per-class recall.
* Per-class F1.
* Confusion matrix.
* Number of examples per class.
* Balanced accuracy where appropriate.
* Confidence/calibration analysis if confidence affects feedback.
* Results for each relevant held-out evaluation.

Always compare XGBoost against simpler baselines.

Report synthetic-only results separately from real-data results.

If the real dataset is too small or lacks valid labels, state that the real-world performance of the classifier has not yet been established.

Do not invent metrics or claim success before the experiment has been run.

---

## 12. Evidence-Based Feedback

The feedback system should use both the predicted label and the observed evidence.

A prediction record could include:

* `submission_id`
* Predicted label or labels.
* Confidence/probability.
* Model version.
* Feature extractor version.
* Evidence IDs.
* Feedback template/version.
* `needs_review` or `insufficient_evidence`.
* Prediction timestamp.

### Feedback workflow

1. Check whether the prediction has supporting evidence.
2. Avoid confident claims if evidence is weak or contradictory.
3. Explain the observable issue in plain language.
4. Offer a hint or next learning step.
5. Allow an uncertain or unknown outcome.
6. Focus on the code rather than judging the student.
7. Record feedback outcomes only under appropriate privacy and consent rules.

For example, if a boundary test fails and the code appears to access an invalid index, feedback can explain the boundary issue and suggest reviewing valid index ranges.

It should not automatically state that the student definitely misunderstands arrays.

---

## 13. Reproducibility, Privacy, and Licensing

### Reproducibility

Record the following for every processing and experiment run:

* Dataset versions.
* File checksums.
* Parser and adapter versions.
* Taxonomy version.
* Feature extractor version.
* Compiler and flags.
* Test-suite version.
* Split assignment.
* Model configuration.
* Random seeds.
* Library and runtime versions.
* Commands or scripts used.
* Output artifact checksums.

### Privacy

* Treat learner identifiers as potentially sensitive.
* Pseudonymize IDs where learner-level linkage is necessary and permitted.
* Do not publish personal information.
* Restrict access to learner histories.
* Check dataset terms and relevant ethics requirements.
* Do not assume public availability means unrestricted reuse.

### Licensing

For each source, record the license and where it was verified.

If licensing is unclear, flag the source and avoid redistributing it until the terms are resolved.

Preserve attribution and required notices.

---

## 14. Recommended Implementation Milestones

### Milestone 1: Workspace and dataset audit

* Locate the downloaded datasets.
* Inventory files and archive contents.
* Record file sizes and checksums.
* Read source documentation and licenses.
* Produce a source-by-source audit report.

**Completion criterion:** The team can explain what each source actually contains and what it can legitimately support.

### Milestone 2: Define the task and taxonomy

* Confirm whether the model is single-label or multi-label.
* Define the unit being classified.
* Review the initial misconception taxonomy.
* Write annotation guidelines.
* Determine which source labels, if any, are compatible.

**Completion criterion:** Every training label has a written definition and a defensible origin.

### Milestone 3: Build the canonical schema

* Define the canonical data model.
* Implement source-specific adapters.
* Preserve raw files and provenance.
* Add validation and unit tests.
* Produce normalized tables and quality reports.

**Completion criterion:** Ingestion is reproducible and relationships between records are valid.

### Milestone 4: Develop evidence and feature extraction

* Build C++ parsing and analysis features.
* Collect execution/test evidence where appropriate.
* Document every feature.
* Validate against hand-checked examples.
* Version the feature extractor.

**Completion criterion:** A submission can be transformed into a reproducible feature vector with traceable evidence.

### Milestone 5: Establish labels and synthetic fixtures

* Annotate a small real sample if feasible and permitted.
* Generate controlled synthetic examples.
* Include negative and ambiguous controls.
* Review labels and track uncertainty.
* Preserve the distinction between real and synthetic data.

**Completion criterion:** The origin and reliability of each training label are transparent.

### Milestone 6: Train and evaluate models

* Establish simple baselines.
* Prepare leakage-safe splits.
* Train XGBoost only on eligible labeled examples.
* Evaluate with macro-F1, per-class metrics, and confusion matrices.
* Document limitations.

**Completion criterion:** The results are reproducible and do not overstate what the dataset supports.

### Milestone 7: Integrate feedback

* Connect predictions to evidence.
* Add low-confidence and unknown handling.
* Evaluate feedback quality with instructors or a defined rubric.

**Completion criterion:** Predictions are traceable to evidence and communicated as estimates rather than certainties.

---

## 15. Suggested Repository Artifacts

Adapt these to the current project structure:

```text
docs/
  dataset_intelligence_brief.md
  dataset_audit_report.md
  data_dictionary.md
  taxonomy.md
  annotation_guidelines.md
  model_card.md

data/
  README.md
  raw/
  interim/
  processed/
  synthetic/

scripts/
  inventory_datasets.*
  audit_datasets.*
  normalize_datasets.*
  validate_schema.*
  build_features.*
  create_splits.*
  train_baseline.*
  evaluate_model.*

tests/
  test_ingestion_*.*
  test_schema.*
  test_features.*
```

Do not commit huge datasets, restricted data, learner information, or credentials to a public repository.

Use appropriate ignore rules and retain a non-sensitive data manifest when possible.

---

## 16. Definition of Done

The first defensible data and ML release should satisfy these checks:

* [ ] Actual downloaded files inventoried and checksummed.
* [ ] Each dataset's schema, purpose, license, and limitations documented.
* [ ] Raw files preserved unchanged.
* [ ] Source adapters and canonical schema tested.
* [ ] Provenance retained for every normalized record.
* [ ] C++ filtering documented.
* [ ] Taxonomy definitions and versions documented.
* [ ] Source labels mapped only when meanings align.
* [ ] Human, synthetic, rule-generated, and source-provided labels distinguished.
* [ ] Feature definitions reproducible.
* [ ] Target leakage checked.
* [ ] Duplicate and split leakage checked.
* [ ] Baseline comparisons completed.
* [ ] Held-out evaluation reported.
* [ ] Per-class metrics reported.
* [ ] Synthetic and real results reported separately.
* [ ] Model limitations and uncertainty handling documented.
* [ ] Feedback connected to observable evidence.
* [ ] Privacy and licensing constraints reviewed.

Training XGBoost without errors is not sufficient to declare the pipeline complete.

---

## 17. Immediate Instructions to the Agent

Execute these steps in order.

### Step 1: Locate the datasets

Find the actual downloaded dataset directory.

If it is not visible in the current workspace, ask the user for the path or the files. Do not claim to have inspected inaccessible files.

### Step 2: Generate a file inventory

Create a recursive inventory containing:

* File paths.
* File sizes.
* File types.
* Archive membership.
* SHA-256 checksums.
* Dataset association.

### Step 3: Audit each dataset

For every source, document:

* Verified contents.
* Schema.
* Row counts.
* Language distribution.
* Label definitions.
* Missingness.
* Duplicates.
* License.
* Limitations.
* Recommended role.

Clearly separate verified facts from assumptions.

### Step 4: Identify the label gap

Determine whether any downloaded dataset genuinely contains labels that support C++ misconception classification.

If not, state this directly and propose a realistic annotation strategy.

### Step 5: Map the schemas

Create a data dictionary and map source fields to the proposed canonical schema.

Preserve source-native values and document unmapped fields.

### Step 6: Choose a minimal first dataset

Recommend a small, practical subset that can establish the pipeline without consuming unnecessary storage or compute.

Explain why the subset is suitable for the first milestone.

### Step 7: Implement normalization

Implement source-specific ingestion, validation, provenance tracking, and quality reports.

Do not begin by combining every source into a single undifferentiated table.

### Step 8: Implement feature extraction

Start with a small, hand-checked set of C++ examples.

Verify that the features actually represent the intended code patterns.

### Step 9: Establish labels and splits

Document the target labels and annotation methods. Design splits that prevent leakage.

### Step 10: Train baselines and XGBoost

Only begin supervised training when the labels and features are suitable.

Compare against simple baselines and report held-out results.

### Step 11: Report honestly

Report actual row counts, exclusions, label counts, metrics, and limitations.

Do not invent results or claim real-world validity based on synthetic data alone.

---

## 18. Source Register

These links were identified during planning. Verify the exact version and documentation for each downloaded dataset before making claims about contents or licensing.

* **Project CodeNet:** https://github.com/IBM/Project_CodeNet
* **Project CodeNet archive:** https://codait-cos-dax.s3.us.cloud-object-storage.appdomain.cloud/dax-project-codenet/1.0.0/Project_CodeNet.tar.gz
* **CodeStream:** https://data.mendeley.com/datasets/n77t7z9zcr/1
* **PROGpedia:** https://zenodo.org/records/7449056
* **McMining/McMiner:** https://github.com/taisazero/mcminer
* **ProgFeed:** https://github.com/umass-ml4ed/progFeed-dataset-public
* **CSEDM 2019 / ITAP:** https://github.com/thomaswp/CSEDM2019-Data-Challenge
* **HELP-DKT:** https://github.com/liangyubuaa/HELP-DKT
* **FalconCode:** https://huggingface.co/datasets/koutch/falcon_code

---

## 19. Expected First Response From the Agent

After reading this brief, the agent should respond with:

1. **Workspace access:** Which directories and files it can actually access.
2. **Dataset inventory:** Verified files, sizes, and formats.
3. **Source-by-source findings:** What was confirmed from the real data.
4. **Suitability matrix:** Direct training, annotation candidate, feature development, supporting, or exclude.
5. **Label gap analysis:** Whether target-aligned misconception labels exist.
6. **Proposed next steps:** The smallest useful and defensible implementation plan.
7. **Blockers:** Only questions or access limitations that materially prevent progress.

The agent should not immediately train a model or produce invented dataset statistics.

---

## Final Principle

**The goal is not to maximize the number of rows. The goal is to establish a trustworthy chain from a C++ submission, to reproducible evidence, to a well-defined label, to an evaluated prediction, to useful educational feedback.**

If a dataset does not support a link in that chain, document what it can contribute and use it accordingly.
