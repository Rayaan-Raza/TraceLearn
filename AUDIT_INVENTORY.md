# TraceLearn raw dataset audit

Audit date: 9 October 2026
Auditor: Dataset audit agent
Raw root: `G:\TraceLearn\Datasets_RAW`
Method: Direct file system inspection. No file was changed.

This document records only facts confirmed from real files. It states the source of every count.

---

## 1. Workspace paths

The agent can read these paths.

| Path | Purpose |
|---|---|
| `G:\TraceLearn` | Project root |
| `G:\TraceLearn\Datasets_RAW` | Downloaded raw sources. Read-only. |
| `G:\TraceLearn\Docs_Agents` | Project design documents |
| `G:\TraceLearn\scripts` | Ingestion and audit scripts |
| `G:\TraceLearn\data\intermediate\normalized` | Normalized output tables |

### 1.1 Raw folders found

| Folder | Files | Size |
|---|---:|---:|
| `Project_CodeNet` | 241,512 | 316.63 MB |
| `progpedia` | 13,849 | 150.27 MB |
| `progpedia (1)` | 12,545 | 145.86 MB |
| `CodeStream A Dataset of Iterative Programming Subm` | 3 | 5.99 MB |
| `poc_data` | 42 | 0.03 MB |
| `TraceLearn_Dataset_Starter` | 10 | 0.00 MB |

### 1.2 Archive formats

The agent searched for `.zip`, `.tar.gz`, `.tgz`, `.tar`, `.parquet`, `.jsonl`, `.7z` and `.rar` files.

The search returned **no matches**. Every archive is already extracted. No extraction step is required.

---

## 2. Sources with complete problem statements

These sources hold a written problem statement and at least one sample test.

### 2.1 Project CodeNet

| Property | Verified value |
|---|---|
| Path | `Datasets_RAW\Project_CodeNet\Project_CodeNet` |
| Statement files | 3,999 HTML files |
| Statements parsed | 3,973 |
| Statements with sample tests | 3,266 |
| Total sample tests | 7,571 |
| Character encoding | Valid UTF-8 in all 3,999 files |
| Non-English statements | 1,311 files hold CJK text |

Each statement holds an `<H1>` title and `<H2>` sections. The sections are Input, Output, Constraints, Sample Input and Sample Output. Sample cases sit inside `<pre>` blocks.

Two problems hold no statement file: `p02509` and `p02511`.

### 2.2 PROGpedia

| Property | Verified value |
|---|---|
| Paths | `Datasets_RAW\progpedia` and `Datasets_RAW\progpedia (1)` |
| Problem folders | 16 (9 + 7) |
| Statements present | 15 |
| Format | Markdown |
| Character encoding | Valid UTF-8 in all 15 files |

Each statement holds Title, Task, Input, Output and Example sections. Sample cases sit in fenced code blocks under `### Input` and `### Output`.

Folder `progpedia (1)\00000035` holds no statement. The agent logged one `missing_statement` exclusion.

The Master Plan predicted 16 PROGpedia exercises. The download matches that figure exactly.

### 2.3 CodeStream

| Property | Verified value |
|---|---|
| Path | `Datasets_RAW\CodeStream A Dataset of Iterative Programming Subm` |
| Problem rows | 46 |
| Problems with sample tests | 46 |
| Total test cases | 317 |
| Statement language | Markdown inside CSV |
| Character encoding | Valid UTF-8 in both CSV files |

`Problem Data.csv` holds three columns: `problem_id`, `problem_description`, `evaluation_test_cases`. The test cases column holds a JSON array. Each array element holds `test_case_no`, `input` and `output`.

The Master Plan predicted 5,482 submissions, 202 participants and 46 problems. The download matches all three figures exactly.

---

## 3. Sources with submissions or analytics only

These sources hold code or activity records without a complete written statement.

### 3.1 Project CodeNet submission tree

| Property | Verified value |
|---|---|
| Path | `Datasets_RAW\Project_CodeNet\Project_CodeNet\data` |
| Problem folders | 70 |
| Language folders | 53 |
| C++ source files | 139,799 |
| C++ file size | 176.3 MB |
| Zero-byte C++ files | 0 |
| C++ files per problem | min 2, median 430, max 15,915 |

**Critical gap.** The full CodeNet archive ships four parts: `data`, `metadata`, `problem_descriptions` and `derived`. This copy holds only two.

| Part | Present |
|---|---|
| `data` | Yes |
| `problem_descriptions` | Yes |
| `metadata` | **No** |
| `derived` | **No** |

The agent searched for CSV files under CodeNet and found **zero**. The `metadata` folder is the only home of verdicts, user ids, timestamps, CPU time, memory and code size. Its absence means **no CodeNet row can carry a verdict**.

A CodeNet C++ file name holds a problem id and a submission id only. Nothing else survives.

### 3.2 PROGpedia submission tree

| Property | Verified value |
|---|---|
| Code files | 9,099 |
| Languages | Java 4,362 · Python 2,198 · C 1,880 · C++ 659 |
| Verdict folders | `ACCEPTED`, `RUNTIME_ERROR`, `WRONG_ANSWER` |
| Empty code files | 12 |

Every submission sits under a verdict folder. The folder name is the only outcome label.

Code property graph files sit beside the code. Coverage is incomplete.

| Language | Files | With graph | Without graph |
|---|---:|---:|---:|
| C++ | 659 | 518 | 141 |
| C | 1,880 | 1,620 | 260 |
| Python | 2,198 | 1,231 | 967 |
| Java | 4,362 | 649 | 3,713 |

### 3.3 CodeStream submission table

| Property | Verified value |
|---|---|
| Rows | 5,482 |
| Columns | 8 |
| Users | 202 |
| Languages | C 2,112 · Java 2,086 · C++ 1,284 |
| Empty source code | 1 |

Verdict distribution across all languages:

| Verdict | Count |
|---|---:|
| Wrong Answer | 1,656 |
| Accepted | 1,649 |
| Compilation Error | 1,043 |
| Presentation Error | 732 |
| Runtime Error | 339 |
| Time Limit Exceeded | 62 |
| Memory Limit Exceeded | 1 |

The table holds `attempt_number` and `verdict_sequence_trace`. CodeStream is the only local source with ordered attempt history.

---

## 4. Sources absent from the workspace

The agent searched the whole project tree for these names and found nothing.

| Source | Status |
|---|---|
| McMining / McMiner | Not downloaded |
| ProgFeed | Not downloaded |
| CSEDM 2019 / ITAP | Not downloaded |
| HELP-DKT | Not downloaded |
| FalconCode | Not downloaded |

The agent logged one `source_not_downloaded` exclusion for each.

### 4.1 Internal folders, not public sources

| Folder | Content |
|---|---|
| `TraceLearn_Dataset_Starter` | 10 files. Schema templates and 3 synthetic fixtures. Mostly empty. |
| `poc_data` | 42 files. 6 Python problems and Python sequences. No C++. |
| `TraceLearn_Initial_Dataset_Summary.csv` | 10 rows. Claims 8 problems and 48 submissions. |

`poc_data\problems\problems.json` holds 6 problems with `designed_misconception` values `M01_LOOP_BOUNDARY`, `M02_INDEX_VALUE` and `M03_MISSING_RETURN`. All code is Python. These labels do not apply to C++.

`ground_truth.json` holds an empty submissions list. It contains no reviewed labels.

---

## 5. Source comparison

| Property | CodeNet | PROGpedia | CodeStream |
|---|---|---|---|
| Problem statements | 3,973 | 15 | 46 |
| Sample test cases | 7,571 | 22 | 317 |
| Submissions | 139,799 C++ | 9,099 | 5,482 |
| C++ submissions | 139,799 | 659 | 1,284 |
| Verdict labels | None | Folder name | `final_verdict` column |
| Attempt order | No | No | Yes |
| Learner identity | No | No | Yes, 202 users |
| Code property graphs | No | Partial | No |
| Statement language | English + CJK | English | English |

### 5.1 What each source can support

| Source | Can support | Cannot support |
|---|---|---|
| CodeNet | Large C++ corpus. Feature development. Problem bank. | Any labelled training. No verdicts survive. |
| PROGpedia | C++ code with verdicts. Structural features from graphs. | Ordered attempts. Full test suites. |
| CodeStream | Attempt history. Verdict traces. Per-test results. | Large C++ volume. Only 1,284 C++ rows. |

### 5.2 The label gap

The agent confirms the gap stated in the Agent Brief.

**No local source carries misconception labels.** The strongest label available anywhere is a judge verdict. A verdict states an outcome. It does not state a belief.

TraceLearn must create its own labels. The agent recommends human annotation of a reviewed sample. Rule-generated and synthetic labels stay separate from human labels.

---

## 6. Project CodeNet suitability

The user asked where CodeNet can be used. The agent answers with the verified counts.

### 6.1 For the student problem set

CodeNet is the strongest local source for this purpose.

| Asset | Count |
|---|---:|
| Problems with a parsed statement | 3,973 |
| Problems with sample tests | 3,266 |
| Problems with C++ submissions | 70 |
| Problems with both C++ code and sample tests | 57 |

The agent measured the C++ subset against the statement bank.

- 68 of the 70 C++ problems hold a parsed statement.
- 57 of those hold sample tests.
- 59 hold an input specification.
- 59 hold an output specification.
- 32 hold a constraint section.

**Recommendation.** Build the first student problem set from those 57 problems. They hold a written statement, sample tests and C++ reference solutions in one place. The agent set a `student_ready` field on each problem record to mark this group.

The wider bank of 3,266 tested statements is a reserve. The agent warns that these statements come from online judges. They are not classroom material. A teacher must review each one before students see it.

### 6.2 For XGBoost

CodeNet cannot supply XGBoost targets in its current state.

| Requirement | CodeNet status |
|---|---|
| Input features | Yes. 139,799 C++ programs. |
| Target labels | **No.** Verdicts are absent. |
| Misconception labels | **No.** No source supplies them. |

A classifier needs targets. CodeNet supplies none. The agent states this directly and stops there.

CodeNet still serves three real purposes before training starts.

1. **Feature extractor testing.** 139,799 C++ programs stress the parser. The agent measured a median statement length of 666 characters and a maximum of 19,716.
2. **Deduplication testing.** The size distribution runs from 2 to 15,915 files per problem. This range tests hash-based grouping well.
3. **Reference solutions.** The accepted subset can seed a problem bank, once verdicts are available from another route.

**Blocker.** To use CodeNet for training, the agent must obtain the `metadata` folder. That folder holds `problem_list.csv` and one CSV per problem. Without it, CodeNet stays a feature-development source.

---

## 7. Ingestion adapter

`scripts/ingest_sources.py` version `ingest_sources.py/1.1.0`.

### 7.1 What it does

1. Reads raw files. It never writes to the raw tree.
2. Converts all text to UTF-8 and cleans whitespace.
3. Parses statements into title, input, output, constraints and sample tests.
4. Preserves source-native identifiers on every record.
5. Emits both naming conventions on every record.
6. Writes each table as JSONL and CSV.
7. Writes a README in each output folder.
8. Logs every refused record with one reason code.

### 7.2 Commands

```bash
python scripts/ingest_sources.py
python scripts/ingest_sources.py --with-submissions
python scripts/ingest_sources.py --sources codestream --exclude-without-tests
python scripts/ingest_sources.py --limit 500
```

### 7.3 Output layout

```text
data/intermediate/normalized/
  README.md
  ingest_run_manifest.json
  hash_cache.json
  problems/
    problems.jsonl
    problems.csv
    README.md
  submissions/
    submissions.jsonl
    submissions.csv
    README.md
  exclusions/
    exclusions.jsonl
    exclusions.csv
    README.md
```

### 7.4 Both naming conventions

Three documents specified three different names for the same columns. The user chose to emit both. Every record now carries both.

| Master Plan §5.1 | Agent Brief §5.1 |
|---|---|
| `dataset_source` | `source_dataset` |
| `source_record_id` | `source_submission_id` |
| `source_code_path` | `source_code_ref` |
| `attempt_order` | `attempt_number` |
| `timestamp` | `submitted_at` |
| `label_status` | `annotation_status` |
| `tracelearn_label` | `misconception_label` |
| `provenance_id` | `provenance_ref` |
| `statement` | `statement_text` |
| `input_spec` | `input_description` |
| `output_spec` | `output_description` |

### 7.5 Exclusion reason codes

| Reason | Count in test run | Meaning |
|---|---:|---|
| `source_not_downloaded` | 5 | Planned dataset is absent. |
| `not_a_target_source` | 3 | Folder is internal, not a public source. |
| `empty_source_code` | 13 | Submission holds no code bytes. |
| `missing_statement` | 1 | Problem folder has no statement file. |
| `empty_statement` | 26 | Statement parsed below 80 characters. |
| `no_sample_tests` | 0 | Only logged with `--exclude-without-tests`. |

### 7.6 CodeNet hash cache

The CodeNet C++ walk reads 139,799 files. Measured throughput is about 50 files each second. The first run therefore takes roughly 45 minutes.

`HashCache` stores each digest against the file path, size and modification time. Later runs skip unchanged files. The agent measured this: a second run re-used 100% of cached digests.

### 7.7 Verification performed

The agent ran these checks.

1. **Repeatability.** Two runs produced identical rows after removing the run id.
2. **Unique keys.** 4,035 problem ids, all unique. 14,272 submission ids, all unique.
3. **Referential integrity.** Zero submissions point to a missing problem.
4. **Encoding.** All output files decode as valid UTF-8.
5. **Completeness.** Zero null statements. Zero null code hashes.

---

## 8. Blockers and next steps

### 8.1 Blockers

1. **CodeNet metadata is missing.** No verdicts, no users, no timestamps. Training use is blocked until it arrives.
2. **No misconception labels exist.** No local source supplies them. Annotation must begin.
3. **Five sources are not downloaded.** McMining, ProgFeed, CSEDM, HELP-DKT and FalconCode are absent.

### 8.2 Recommended next steps

1. Build the student problem set from the 57 ready CodeNet problems.
2. Request the CodeNet `metadata` folder.
3. Write annotation guidelines for the reviewed sample.
4. Download McMining for taxonomy work only. Keep its Python labels.
5. Freeze the schema and taxonomy versions before training.
