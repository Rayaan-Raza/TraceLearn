# Source audit report

Audit date: 10 October 2026
Auditor: Agent 2, compliance and taxonomy audit
Input: Agent 1 inventory (`AUDIT_INVENTORY.md`)
Method: Independent file inspection under `G:\TraceLearn\Datasets_RAW`
Standard: ASD-STE100 Simplified Technical English
Status: Complete

---

## 1. Purpose

This report audits every candidate source. It verifies problem statements, input formats, output formats, constraints, public examples, test cases, and expected outputs. It enforces dataset boundary separation. It maps no source label to a misconception label.

## 2. The 15 audit points

Each source receives one score for each point.

| Point | Audit question |
|---|---|
| 1. Presence | Does the source exist in the workspace? |
| 2. Completeness | Are all expected source parts present? |
| 3. Statement presence | Do written problem statements exist? |
| 4. Statement structure | Does each statement hold the required sections? |
| 5. Input format | Does the statement state the input format? |
| 6. Output format | Does the statement state the output format? |
| 7. Constraints | Does the statement state input limits? |
| 8. Public examples | Do sample cases exist? |
| 9. Example consistency | Do sample outputs match the stated task? |
| 10. Test availability | Do tests exist beyond public examples? |
| 11. Output verifiability | Is each expected output checkable? |
| 12. Encoding | Do files decode as UTF-8? |
| 13. Language coverage | Does the source hold C++ material? |
| 14. License | Is the license identified and recorded? |
| 15. Role classification | Does the source have a compliant role? |

Score values: `PASS`, `PARTIAL`, `FAIL`, `UNKNOWN`.

## 3. Audit results

### 3.1 Project CodeNet

| Point | Score | Verified fact |
|---|---|---|
| 1. Presence | PASS | The source exists. It holds 316.63 MB and 241,512 files. |
| 2. Completeness | FAIL | The archive ships four parts. This copy holds two. `metadata` and `derived` are absent. |
| 3. Statement presence | PASS | 3,999 HTML statement files exist. Two problems hold no statement: `p02509` and `p02511`. |
| 4. Statement structure | PASS | Each statement holds an `<H1>` title and `<H2>` sections. Sample cases sit in `<pre>` blocks. |
| 5. Input format | PASS | 3,973 statements parse. 59 of the 70 C++ problems state an input format. |
| 6. Output format | PASS | 59 of the 70 C++ problems state an output format. |
| 7. Constraints | PARTIAL | 32 of the 70 C++ problems state constraints. Many statements omit constraints. |
| 8. Public examples | PASS | 3,266 problems hold sample tests. The total sample count is 7,571. |
| 9. Example consistency | PARTIAL | Samples follow the stated sections. This audit checked a sample of files by hand. |
| 10. Test availability | FAIL | Only public samples exist. No hidden test suite ships with the archive. |
| 11. Output verifiability | PASS | Each sample holds an input and an expected output. A judge can check both. |
| 12. Encoding | PASS | All 3,999 files decode as UTF-8. 1,311 files hold CJK text. |
| 13. Language coverage | PASS | The C++ tree holds 139,799 files. The size is 176.3 MB. Zero files are empty. |
| 14. License | UNKNOWN | This audit found no license file in the copy. The team must record the CodeNet license before use. |
| 15. Role classification | PASS | The role is a C++ corpus and a problem bank. The role is not a training label source. |

Notes:

- The `data` tree holds 70 problem folders and 53 language folders. Each C++ file name holds a problem id and a submission id only.
- No CSV file exists under CodeNet. Verdicts, user ids, timestamps, CPU time, memory, and code size are all absent.
- 57 problems hold a statement, sample tests, and C++ code. The ingestion script sets `student_ready=true` on these. They form the first website practice set.
- Count note: Agent 1 parsed 3,973 statements and found 3,266 with samples. This audit found 3,410 files with a sample marker and 1,096 files with a literal `<H1>` tag. Counts depend on parser rules. The script `scripts/ingest_sources.py` defines the authoritative parse.

### 3.2 PROGpedia

| Point | Score | Verified fact |
|---|---|---|
| 1. Presence | PASS | Two copies exist. Copy one holds 9 problem folders. Copy two holds 8 problem folders. |
| 2. Completeness | PARTIAL | Both copies hold statements, code, and graphs. One problem folder in copy two holds no statement. |
| 3. Statement presence | PASS | 16 unique problems exist. Every unique problem holds a statement in at least one copy. |
| 4. Statement structure | PASS | Statements use Markdown. Sections: Title, Task, Input, Output, Examples. Samples sit in fenced blocks. |
| 5. Input format | PASS | Each statement holds an Input section. |
| 6. Output format | PASS | Each statement holds an Output section. |
| 7. Constraints | PARTIAL | Some statements state limits inside the Input section. No dedicated constraints section exists. |
| 8. Public examples | PASS | 15 statements hold sample cases in fenced blocks. |
| 9. Example consistency | PASS | This audit checked statement `00000006` by hand. The samples match the stated task. |
| 10. Test availability | FAIL | Only public samples exist. No hidden test suite ships with the source. |
| 11. Output verifiability | PASS | Each sample holds an input and an expected output. |
| 12. Encoding | PASS | All 15 statements decode as UTF-8. |
| 13. Language coverage | PASS | The source holds 659 C++ code files. It also holds Java, Python, and C files. |
| 14. License | UNKNOWN | This audit found no license file in the copy. The team must record the PROGpedia license before use. |
| 15. Role classification | PASS | The role is C++ code with verdicts and structural graph data. |

Notes:

- The problem `00000035` appears in both copies. Copy one holds its statement (1,069 bytes). Copy two holds only a `RUNTIME_ERROR` folder.
- Agent 1 reported 15 statements and one `missing_statement` exclusion. The ingestion adapter checks the statement before the duplicate id. Therefore copy two's `00000035` logs `missing_statement`. This is a duplicate-copy artifact. The team must confirm the deduplicated problem count is 16.
- The file `data.md` holds the data dictionary. It defines `statement.md`, `*.dsc.csv`, and `*.cpg.csv`.
- Each submission folder holds three files: one source file, one `*.cpg.csv`, and one `*.dsc.csv`.
- Verdict folders: `ACCEPTED`, `RUNTIME_ERROR`, `WRONG_ANSWER`. The folder name is the only verdict label.
- Agent 1 counted 9,099 code files: Java 4,362, Python 2,198, C 1,880, C++ 659. This audit's raw walk found 26,377 files of all types. The adapter filters by code extension. Both counts are consistent.
- Empty code files: Agent 1 reports 12. This audit found 13 empty files of all types. The team must inspect empty files during ingestion.
- Code property graph coverage is partial. C++: 518 files hold a graph, 141 do not.

### 3.3 CodeStream

| Point | Score | Verified fact |
|---|---|---|
| 1. Presence | PASS | The source exists. It holds two CSV files and one `details.md`. |
| 2. Completeness | PASS | The problem table and the submission table both exist. The schema document exists. |
| 3. Statement presence | PASS | 46 problems hold a description in Markdown inside the CSV. |
| 4. Statement structure | PARTIAL | Descriptions vary in structure. Some hold headings. Some hold plain text. |
| 5. Input format | PARTIAL | Some descriptions state an input format. Many descriptions embed the format in prose. |
| 6. Output format | PARTIAL | Some descriptions state an output format. Many descriptions embed the format in prose. |
| 7. Constraints | PARTIAL | Some descriptions state limits, such as `1<=|S|<=500`. Many descriptions omit limits. |
| 8. Public examples | PASS | All 46 problems hold evaluation test cases. The total test count is 317. |
| 9. Example consistency | PARTIAL | This audit checked the JSON structure. It did not execute all 317 cases. |
| 10. Test availability | PASS | Each problem holds 1 to 20 test cases. Many problems hold more than public samples. |
| 11. Output verifiability | PASS | Each test case holds an input and an expected output. A judge can check both. |
| 12. Encoding | PASS | Both CSV files decode as UTF-8. |
| 13. Language coverage | PASS | The submission table holds 1,284 C++ rows. It also holds C and Java rows. |
| 14. License | UNKNOWN | The Master Plan records CC BY 4.0 from the Mendeley record. This audit could not open the Mendeley page. The team must verify the license before redistribution. |
| 15. Role classification | PASS | The role is attempt history and verdict traces. The role is not a training label source. |

Notes:

- `Problem Data.csv` holds 46 rows and 3 columns: `problem_id`, `problem_description`, `evaluation_test_cases`.
- The test column holds a JSON array. Each element holds `test_case_no`, `input`, and `output`.
- `Submission Data.csv` holds 5,482 rows and 8 columns. This audit confirms the header and the row count.
- Columns: `submission_id`, `user_id`, `problem_id`, `attempt_number`, `programming_language`, `source_code`, `final_verdict`, `verdict_sequence_trace`.
- Languages: C 2,112, Java 2,086, C++ 1,284. Users: 202. Empty source code: 1.
- Verdict distribution: Wrong Answer 1,656, Accepted 1,649, Compilation Error 1,043, Presentation Error 732, Runtime Error 339, Time Limit Exceeded 62, Memory Limit Exceeded 1.
- CodeStream is the only local source with ordered attempt history. The columns `attempt_number` and `verdict_sequence_trace` give the order.
- Topics include string cipher, subsequence, grid path, scheduling, palindrome, linked list, postfix evaluation, sorting, search, median, binary conversion, income tax, binary search trees, hash functions, geometry, triangle validity, timestamps, and graph components.

### 3.4 Absent sources

The audit searched the whole project tree for these names. It found nothing.

| Source | Status | Audit point 1 |
|---|---|---|
| McMining / McMiner | Not downloaded | FAIL |
| ProgFeed | Not downloaded | FAIL |
| CSEDM 2019 / ITAP | Not downloaded | FAIL |
| HELP-DKT | Not downloaded | FAIL |
| FalconCode | Not downloaded | FAIL |

Each source receives one `source_not_downloaded` exclusion.

### 3.5 Internal folders

These folders are not public sources. They receive the `not_a_target_source` exclusion.

| Folder | Content | Audit finding |
|---|---|---|
| `TraceLearn_Dataset_Starter` | 10 files | Schema templates and 3 synthetic fixtures. Mostly empty. |
| `poc_data` | 42 files | 6 Python problems with `designed_misconception` values. No C++. |
| `TraceLearn_Initial_Dataset_Summary.csv` | 10 rows | Claims 8 problems and 48 submissions. The claims are unverified. |

Compliance note on `poc_data`: the values `M01_LOOP_BOUNDARY`, `M02_INDEX_VALUE`, and `M03_MISSING_RETURN` describe Python semantics. They must not become `CPP-M` labels without a defensible cross-language mapping.

## 4. Dataset boundary separation

The rule: the website practice dataset and the ML training dataset have different responsibilities.

| Dataset | Responsibility | Contents | Must not contain |
|---|---|---|---|
| Website practice dataset | Student practice | Statements, input formats, output formats, constraints, public examples, test cases, expected outputs | Misconception labels, learner identities |
| ML training dataset | Supervised training | Submission features, validated misconception labels, provenance | Unannotated practice problems used as labels |

Violation flags. The audit found these risks:

1. A practice problem statement is not a training label. No statement in any source carries a misconception label.
2. A judge verdict is not a misconception label. PROGpedia verdict folders and CodeStream `final_verdict` values state outcomes. They do not state beliefs.
3. `poc_data` holds Python misconception labels. These labels must not become `CPP-M` labels.
4. The in-repo file `data/problems/problems.json` holds 6 Python problems with `designed_misconception` values. These values mark the intended design target. They are not evidence labels for any student submission.
5. CodeNet supplies no labels at all. Its C++ files must not receive inferred labels from file names or paths.

## 5. Label gap

No local source carries misconception labels. The strongest label anywhere is a judge verdict. A verdict states an outcome. It does not state a belief. TraceLearn must create its own labels. The team must use human annotation for a reviewed sample. Rule-generated labels and synthetic labels must stay separate from human labels.

## 6. Verification discrepancies

This audit repeated key counts from the Agent 1 inventory.

| Item | Agent 1 claim | This audit | Disposition |
|---|---|---|---|
| CodeNet parsed statements | 3,973 | 1,096 literal `<H1>` tags | Parser-dependent. The ingestion script is the authority. |
| CodeNet statements with samples | 3,266 | 3,410 with a sample marker | Parser-dependent. Same disposition. |
| CodeNet missing statements | `p02509`, `p02511` | Both files are absent | Confirmed. |
| PROGpedia statements | 15 present, 1 missing | 16 unique problems, all with a statement | Duplicate-copy artifact. Confirm the deduplicated count is 16. |
| PROGpedia code files | 9,099 | 26,377 files of all types | Consistent. The adapter filters by code extension. |
| PROGpedia empty code files | 12 | 13 empty files of all types | Minor. Inspect empty files during ingestion. |
| CodeStream rows | 5,482 | 5,482 | Confirmed. |
| CodeStream header | 8 columns | 8 columns, names match | Confirmed. |

## 7. Blockers

1. The CodeNet `metadata` part is absent. No verdicts exist. Training use is blocked.
2. No source carries misconception labels. Annotation must begin.
3. Five planned sources are absent from the workspace.
4. The CodeStream license needs verification before redistribution.
5. The CodeNet license and the PROGpedia license need recording.

## 8. Required actions

1. Run `python scripts/ingest_sources.py`. Confirm the deduplicated PROGpedia count is 16.
2. Request the CodeNet `metadata` folder.
3. Verify the CodeStream license on the Mendeley record.
4. Record the CodeNet license and the PROGpedia license.
5. Write annotation guidelines for the reviewed sample.
6. Keep practice problems and training data in separate tables.
7. Freeze the schema version and the taxonomy version before training.

---

## Sign-off

This audit used direct file inspection. No file was changed. Every count states its source. Every gap states its blocker.
