# Rayaan Raza — Mid-Evaluation Technical Preparation Pack

Prepared from: the mid worksheet (Member 1 column), the mid report, the slides, `docs/`, and the actual code in this repository.
Evaluation: 12 October 2026 · Supervisor: Dr. Ali Zeeshan Ijaz · Panel 3 · Project F26-186-TraceLearn.

**How to use this file.** Sections 1–3 are your spoken words (written in ASD-STE1000 Simplified Technical English). Section 4 is your live-demo runbook. Section 5 is your live-code-modification runbook. Section 6 is the viva Q&A bank. Section 7 lists numbers you must not mix up, and the discrepancies I found in the repo that you must reconcile tonight.

---

## 1. What is assigned to you (Member 1 column)

| Item | Your part |
|---|---|
| Technical ownership | Evidence extraction, diagnosis, the learner-state model; the C++ diagnostic problem bank; the dataset audit and ingestion |
| Live demo steps | **Step 4** (evidence and diagnosis panel) and **Step 5** (corrected code, learner-state history) |
| Report sections | §1.1–1.2 problem formulation / R&D; §3.1 architecture; testing evidence (with Eman) |
| Live modification | The worksheet states you will **add a ninth C++ misconception, end to end, during the meeting** |
| GenAI disclosure | L4 for the C++ bank data content; L2 for your engineering artefacts |
| Technical growth questions | (1) real AST vs regex for C++; (2) correct verdict vocabulary for a judge; (3) cross-language misconception identity |

Your demo steps sit between Umaima's step 3 (wrong submission) and step 5/6. When Umaima submits the faulty code (index equal to vector size), **you** explain what the system found and why. When you submit the corrected code, **you** show the learner-state history.

---

## 2. The story in five sentences (memorise this first)

1. Beginners write similar wrong code for different reasons.
2. A pass/fail mark cannot tell the reasons apart.
3. TraceLearn turns one submission into weighted evidence about a hidden misconception.
4. It then updates a learner state over time, and it shows its reasoning to the teacher.
5. My research question is: does the history of a student give a better diagnosis than the current submission alone?

---

## 3. Your spoken script (ASD-STE1000)

Rules used: one idea per sentence. Max 20 words per sentence. Active voice. Present tense. Present tense verbs. Short sentences. Technical words are allowed (misconception, evidence, diagnosis, learner state, sandbox, confidence). Between brackets you find stage directions. Do not read the stage directions aloud.

### Turn 1 — Opening: the problem and the research question (60 seconds)

> I am Rayaan. I built the evidence pipeline, the diagnosis, the learner state model, and the C++ problem bank.
>
> [Pause.]
>
> The problem is simple. Beginners write similar wrong code for different reasons. The same weak belief also shows in different code, on different problems, over time.
>
> A pass/fail mark cannot tell these reasons apart. It only says the answer is wrong.
>
> TraceLearn changes this. The system takes one C++ submission. It compiles and runs the code in a sandbox. It then turns the result into structured evidence.
>
> The evidence can support a misconception. It can also conflict with a misconception. The system keeps both.
>
> [Point at the slide if you want.]
>
> My research question is: does the history of a student give a better diagnosis than the current submission alone?
>
> To answer it, the system runs two diagnosis engines on every submission. One engine sees only the current submission. The other engine also sees the history. We compare them.
>
> I will now show the core module, and then I will demonstrate two steps live.

### Turn 2 — The core module and the data flow (90 seconds)

> One submission moves through three phases.
>
> Phase one is execution. `POST /api/submissions` stores the submission. The service `SubmissionService.run_and_analyze` starts the work.
>
> `g++ -std=c++17 -O2 -Wall` compiles the code. The sandbox limits CPU, memory, output and time. The wall-clock limit is 2,000 milliseconds. The memory limit is 256 megabytes.
>
> Each test case runs on its own. We compare the output token by token. Whitespace does not matter.
>
> Phase two is analysis. Five analyzers make evidence items.
>
> The static analyzer reads the source. For C++, it uses regular expressions and `g++` warnings. It runs in a separate process with a 3-second budget.
>
> The test analyzer reads the test results. A failing diagnostic test is strong evidence. A visible or hidden test is weak evidence.
>
> The runtime analyzer reads the execution status. The diff analyzer compares this attempt with the last attempt on the same problem. The history analyzer reads evidence from other problems.
>
> Phase three is diagnosis. `apply_evidence_weights` reads `config/evidence_weights.yaml`. The static weight is 0.30. The diagnostic weight is 0.35.
>
> `fuse_diagnosis` sums the weights for each misconception. The top result is the primary diagnosis. The second result is the alternative. We store confidence, uncertainty, and the full explanation.
>
> The current-only engine ignores history evidence. The history-aware engine uses it. Only the history-aware engine updates the learner state.
>
> The state model has six states: NEW, PERSISTENT, IMPROVING, RESOLVED, RECURRED, and REQUIRES_TEACHER_REVIEW.
>
> One rule matters most: one failure never makes a state PERSISTENT. Support on at least two different problems is required.
>
> Every change writes a row in `learner_state_history`, with a reason. The history is append-only. We never delete a row.

### Turn 3 — Demo Step 4: the evidence and diagnosis panel (about 2 minutes, spoken while you click)

> [You are now on the result page of the wrong submission. Umaima submitted it. You explain it.]
>
> The code compiles. Some tests fail. Now I open the evidence and diagnosis panel.
>
> Here you see three things: the evidence items, the two diagnoses, and the hint.
>
> Each evidence item has a source, a misconception code, a direction, and a weight.
>
> Direction is `support` or `conflict`. Support raises the score. Conflict lowers it.
>
> [Show one item and read it aloud. Use the real row on the screen — see section 4.3 for the exact expectation for the index-equal-to-size submission.]
>
> This item comes from a diagnostic test. The diagnostic tag is `index_equal_to_size`. The mapping table in `cpp_mapping.py` maps it to the backend code `CPP_ARRAY_BOUNDS`. The weight is 0.35.
>
> This item comes from static analysis. The pattern is `CPP_ARRAY_AT_SIZE`. The weight is 0.30.
>
> [Show the two diagnoses.]
>
> Here are the two diagnoses. The first is current-only. The second is history-aware. Both show the code, the confidence, and the uncertainty.
>
> The primary code is `CPP_ARRAY_BOUNDS`. The confidence is [read the real number from the screen]. The uncertainty is [low / medium / high].
>
> Confidence is the sum of the weighted evidence, clamped between 0 and 1.
>
> Uncertainty is high if confidence is below 0.35. It is also high if two scores are within 0.10, or if conflict evidence exists.
>
> [Show the hint.]
>
> The hint comes from the template bank. The confidence level selects the hint level. A hint never shows the solution.
>
> [If a panel member asks about history: read the second diagnosis.]
>
> On this submission, the history-aware engine [adds / does not add] evidence, because the student [has / has not] an earlier problem with this belief.

### Turn 4 — Demo Step 5: corrected code and the learner state (about 1 minute)

> I now submit the corrected code. This is attempt 2.
>
> [Submit. Wait for the result.]
>
> All tests pass. The status is `success`.
>
> The test analyzer emits `TEST_ALL_PASSED`. The fusion gives NO_MISCONCEPTION with confidence 0.80. No review is required.
>
> [Open the learner state history.]
>
> Here is the learner state history. Every row has a state, a confidence, a reason, and a link to a submission.
>
> The reason field shows the counts: cross-problem support, recent successes, and the evidence that was used.
>
> The state changed [describe the real change you see: for example, from NEW to IMPROVING, or no change]. This follows the rule order: teacher review first, then RECURRED, then IMPROVING, then RESOLVED, then PERSISTENT, then NEW.
>
> The history is append-only. The system never overwrites an old state. The teacher can add a correction row, and the original diagnosis stays.

### Turn 5 — Validation and the failure case (60 seconds, only if the panel asks you for testing)

> The C++ bank has 40 problems. It has 305 test cases, 32 misconception variants, 4 hard negatives, and 120 hints.
>
> Five problems target each misconception, from CPP-M01 to CPP-M08. Five problems are needed so we can test recurrence on different problems.
>
> The reference verification runs every test three times. It checks the limits and the sanitizers. The verification report shows [quote the number you verified tonight — see section 7].
>
> The hard negatives are correct programs that look suspicious. All 4 pass all tests, and all 4 get NO_MISCONCEPTION. This is our protection against false positives.
>
> [If asked for the failure case — use the recursive factorial.]
>
> Our failure case is a recursive factorial with no base case. The sandbox stops it at 2,000 milliseconds. The return code is -9. The status is `timeout`. The API continues to work. The next submission runs without any change.
>
> A timeout is one signal. It is not a diagnosis by itself.

### Turn 6 — Close: limits and next work (30 seconds)

> I will state our limits clearly.
>
> The evidence weights are team values. We have not validated them with real data.
>
> The C++ static analysis uses regular expressions and compiler warnings. It is not a full abstract syntax tree.
>
> All our data is synthetic. We make no claim that the system helps real students yet.
>
> My next committed work is a machine-readable misconception registry. The taxonomy is now string constants and a mapping table. The registry will hold the code, the title, the description, and the category for every misconception. The target date is 31 October 2026.
>
> Thank you. I am ready for your questions.

---

## 4. Live demo runbook — Steps 4 and 5

### 4.1 Rehearse tonight, on the demo machine

1. Confirm `g++ --version` works in the terminal you will use. Without `g++`, the demo fails.
2. Start the backend and the frontend with the exact commands in `README.md` §21–23.
3. Log in as the demo student. Run steps 3, 4 and 5 once, end to end, without interruption.
4. Record the **real** confidence numbers you see. Replace every `[read the number]` in your script with the real number.
5. Have the database open in a second window (`sqlite3 tracelearn.db` or DB Browser). Know the query you will run.

### 4.2 The queries you may need (run them once tonight)

```sql
-- Step 4: evidence items of the latest submission
SELECT id, source_type, misconception_id, code, direction, weight
FROM evidence_items WHERE submission_id = <id> ORDER BY id;

-- Step 4: the two diagnoses
SELECT mode, primary_label, primary_confidence, uncertainty_level, requires_review
FROM diagnoses WHERE submission_id = <id>;

-- Step 5: learner state history
SELECT id, submission_id, state, confidence, reason_json, created_at
FROM learner_state_history ORDER BY id DESC LIMIT 5;
```

### 4.3 What you expect to see for the demo submission (step 3: index equal to vector size)

The step-3 submission uses `v[v.size()]`. Expect this chain:

| Stage | Value |
|---|---|
| Compile | `success` (`g++ -std=c++17 -O2 -Wall`) |
| Tests | visible pass, hidden fail, diagnostic `index_equal_to_size` fails |
| Static evidence | `CPP_ARRAY_AT_SIZE`, direction `support`, weight 0.30 |
| Diagnostic evidence | `DIAGNOSTIC_INDEX_EQUAL_TO_SIZE_FAIL` → `cpp_mapping.py` maps tag `index_equal_to_size` → `CPP_ARRAY_BOUNDS`, weight 0.35 |
| Primary diagnosis | `CPP_ARRAY_BOUNDS`, score ≈ 0.65 before any history evidence, uncertainty low |
| Hint | level selected by confidence; from the problem's hint rows under bank code `CPP-M04` |

If the demo student already has a CPP-M04/CPP_ARRAY_BOUNDS evidence item on a **different** problem, the history-aware engine adds `CROSS_PROBLEM_RECURRENCE` (weight 0.20, decayed by 0.80^age), and the state can move to PERSISTENT after the second problem. Check this before the meeting: if you want to show PERSISTENT, prepare a student with one prior problem. If you want to show NEW, use a fresh student.

For step 5 (corrected code): `TEST_ALL_PASSED` → `NO_MISCONCEPTION` at confidence 0.80, `requires_review = false`. Show the new `learner_state_history` row with its `reason_json`.

### 4.4 Demo failure fallbacks

| If this fails | Do this |
|---|---|
| The site is down | Run locally: backend on `localhost:8000`, frontend dev server. Show the same page. |
| No `g++` | Do not demo. Show the pre-recorded result rows in the database and `docs/PROBLEM_VERIFICATION_REPORT.md`. |
| The sandbox has no bubblewrap | The server runs in limits-only mode. Say it out loud: "This is not safe for untrusted code. In production, `REQUIRE_SANDBOX` stops execution." |
| The page is slow | Open the database tables instead. The rows are the real evidence. |
| You blank on a number | Say the number you know for certain (40 problems, 305 tests, 2,000 ms, 256 MB). Never guess a decimal. |

---

## 5. Live modification runbook — add a ninth C++ misconception

The worksheet says you will do this **during the meeting**. Practise it three times tonight. Target time: under 8 minutes.

The misconception you will add — agreed example: **CPP-M09: a `while` loop uses `=` instead of `==` against the sentinel** is already covered by CPP-M06. Choose one that does not exist. Recommended for the demo: **CPP-M09 — "the student believes integer division keeps the decimal part"** (backend code `CPP_INT_DIVISION`). Any new code works; what matters is that you show the four places that must agree.

### Step 1 — add the code to the taxonomy (30 seconds)

File: `backend/app/diagnosis/taxonomy.py`

```python
CPP_INT_DIVISION = "CPP_INT_DIVISION"
```

Then append it to `CPP_MISCONCEPTIONS` (line 23–28). `SCORED_MISCONCEPTIONS` is derived from that list, so you do not touch it.

**Say aloud:** "This list is what the aggregator and the learner model read. If I skip this, the evidence is silently dropped. That was a real bug I fixed in commit 12c3c26."

### Step 2 — map the bank code and the diagnostic tag (1 minute)

File: `backend/app/diagnosis/cpp_mapping.py`

Add to `BANK_TO_BACKEND` (line 58):

```python
"CPP-M09": CPP_INT_DIVISION,
```

Add the new diagnostic tag to `TAG_TO_CODE["cpp"]` (line 93):

```python
"integer_division": CPP_INT_DIVISION,
```

**Say aloud:** "This module is the only place that joins the two vocabularies: the bank codes CPP-M01 to CPP-M09, and the backend codes. Before it existed, C++ evidence was dropped by `aggregate_scores`."

**Note:** diagnostic tags get weight 0.35 automatically, because `confidence.py` loops over `TAG_TO_CODE`. If you add a *static* code instead, you must add it to the tuple in `confidence.py` (line 46–51), or it silently takes 0.05.

### Step 3 — add a hint template (45 seconds)

File: `backend/app/hints/templates.py`

```python
HINTS["CPP_INT_DIVISION"] = {
    1: "What does each operand of / produce here, and what do you expect?",
    2: "Integer division drops the decimal part. Think about the types of both operands.",
    3: "Cast one operand to double, or store the result in a double, to keep the decimal part.",
}
```

**Say aloud:** "Every scored code needs a fallback hint. The bank's own hints override these when a problem provides them."

### Step 4 — run the tests that protect this path (2 minutes)

```bash
python -m pytest backend/tests/test_cpp_end_to_end.py -v
python -m pytest backend/tests/test_state_transitions.py backend/tests/test_history_model.py -v
```

**Say aloud:** "`test_cpp_end_to_end.py` reads the bank at run time. It fails if any tag or misconception has no mapping. This is how I made sure this class of bug cannot fail silently again."

Explain the rejected alternative: you could map a new belief onto a near-neighbour code. You reject it. It keeps the label set small, but the diagnosis then answers a question the student was not asked.

### 5.1 If you want the full version (only if the panel pushes — this is the 30-minute version)

Following `docs/CPP_DIAGNOSTIC_BANK_METHOD.md` §8: add a definition to `scripts/cpp_defs/m09_new.py`, register it in `scripts/cpp_defs/__init__.py` `MODULES`, then run:

```bash
python scripts/build_cpp_diagnostics.py
python scripts/verify_cpp_diagnostics.py
python scripts/seed_cpp_diagnostics.py
```

Warning: the bank tests hard-code 40 problems and the set CPP-M01…M08 (`test_cpp_diagnostics_bank.py` asserts `40/305/32/120`). Adding a 40→41 problem change means updating those assertions. **Do not attempt this live.** Do the four-step version live; describe the full version verbally.

### 5.2 Safety rules for the live edit

- Work on a scratch branch: `git checkout -b demo-live-m09`.
- Start with a clean `git status`. The panel must see only your changes.
- If anything breaks: `git checkout -- backend/app` and say, honestly, "The edit did not complete. The same change is committed on branch `demo-live-m09`, and I can walk you through the diff." Then show the diff.
- Never edit `data/` live. Never edit a test file to make it pass.

---

## 6. Viva Q&A bank — the questions you must be able to answer

### Q1. You declared L4 for the problem bank. Does that mean the AI did your work?

> The bank **data** — the 40 problems, their 305 expected outputs, the 32 variants, and the 120 hints — was produced by a generator script that I directed and reviewed. I did not hand-author that content, and I disclose it as L4.
>
> The **engineering** around it is L2 and mine: the verifier `verify_cpp_reference.py`, the bank tests, `cpp_mapping.py`, `api/bank.py`, the loader and the seeder, and the per-test limits. I specified each requirement, wrote or rewrote the logic, and checked every result against an independent source.
>
> My verification is not trust. For the expected outputs I built a second, independent model in the tests. It recomputes every expected output from the problem statement and compares it byte by byte with the committed file. It caught a real defect: a whole class of files had lost the trailing newline. I fixed the normaliser in commit 60f6ffe. SHA-256 manifests protect the files from silent edits afterwards.

### Q2. Why is the C++ static analysis a regex and not a real AST?

> Because of the container. A real AST needs libclang, and we did not want a native dependency in the image. `clang -Xclang -ast-dump=json` is a possible answer, and I have recorded it as a technical growth question.
>
> I state the limit clearly: a regex cannot see structure. It can miss a `<=` inside a macro, and it can match inside a comment. My mitigation is that the regex evidence is never alone: it runs with `g++ -Wall -Wextra` warnings, and with test and runtime evidence. The fusion needs agreement, not one signal.
>
> My plan is to prototype both parsers against the 32 variants and count the disagreements. Target: 7 November 2026.

### Q3. The history-aware engine did not change any prediction in your experiment. So what is the point?

> I report this number honestly. In the current synthetic export, `history_changed_predictions` is 0. The two engines produced the same top labels on these 15 labelled submissions.
>
> What history **does** change today is the learner state and the confidence, through cross-problem recurrence and decay. The persistent count is 5, and the false-persistent count is 0 in both modes.
>
> I do not claim history improves the top label. That is exactly what the research question tests. The synthetic sequences are small and clean. The real test needs student data, which is Iteration 2 and the FYP-I pilot.

### Q4. Your weights are made up. Why should we trust the confidence?

> We do not claim they are correct. They are fixed team values, version `poc-v1`, and the file is frozen before any holdout evaluation, so we cannot tune on the test set.
>
> The value they give us now is **consistency and explainability**: every number on the screen traces to a named weight and a named evidence row. When labelled data arrives, we replace the rule-based fusion with XGBoost and compare against these transparent baselines. If XGBoost does not beat them, we will report that too.

### Q5. RESOLVED is in your state diagram but the code cannot reach it. Is the design wrong?

> The code can reach it in principle: the rule is PERSISTENT state, at least two recent successes, and confidence below 0.25. In practice the confidence rarely drops that low, because passing tests emit `TEST_ALL_PASSED` at 0.80 for NO_MISCONCEPTION and the state update skips it.
>
> I documented this honestly in the report rather than hiding it. The fix is a design decision to take with the supervisor: either lower the resolution threshold, or let a success actively subtract from a standing misconception score. That is an Iteration 2 decision.

### Q6. Why do two languages share some misconception codes and not others?

> The rule is: if the **belief** is identical, the code is shared. CPP-M02 and M02_INDEX_VALUE are the same belief, so the learner model can see one cross-language pattern. If the belief is new, I add a code instead of overloading a near neighbour. CPP-M05 and CPP-M08 had no backend code, so they gained `CPP_RANGE_CHECK` and `CPP_STALE_EXIT`.
>
> I recorded the open question myself: the asymmetry for CPP-M01 versus M01_LOOP_BOUNDARY is not yet justified by a written criterion. My growth question is to write that criterion and test it against all eight bank codes. Target: 14 November 2026.

### Q7. What does a timeout prove about a misconception?

> Nothing on its own. A timeout is one execution signal. It can support CPP-M07, but it can also come from a large input or a slow machine.
>
> That is why the fusion treats it as one weighted item. The diagnosis needs agreement between evidence families. A timeout plus a no-progress static pattern plus a failing diagnostic test is a strong case. A timeout alone stays uncertain.

### Q8. How do you stop a student from reading the hidden tests?

> The API never serialises hidden expected outputs. `test_students_never_see_hidden_expected_outputs` and `test_no_diagnostic_test_is_public` enforce it. Each stored `test_result` links to a `test_case` row, and the response builder filters by test type.

### Q9. You used a lot of AI. What did you personally do?

> Three things. I set the requirements for each tool output. I reviewed and corrected the output against independent sources. And I wrote the logic where correctness mattered.
>
> One example of correction: a GenAI change stopped sending disagreeing submissions to teacher review. It broke our labelled case SYN005. I rejected the change and kept the original rule.
>
> Another example: the AI-generated planning documents had a Python scope. I changed them to C++. The AI-generated expected outputs were checked by an independent model, which found the newline defect.

### Q10. What is your next committed work, and when?

> A machine-readable misconception registry: `backend/app/diagnosis/registry.py`, holding the code, the title, the plain description and the category for M01–M03 and CPP-M01–M08, with a test that fails when a scored code has no registry entry. Target: 31 October 2026.

### Q11. Your growth question says your execution statuses are wrong. Explain. (Worksheet growth question 2)

> Our `ExecutionStatus` has five values, and two of them are used incorrectly today. A link failure — a program with no `main` — reports as `syntax_error`, although the code compiled. A wrong answer can report as `runtime_error`, although the program ran and produced output.
>
> So the status field cannot yet separate "did not compile" from "compiled and crashed" from "compiled, ran, and was wrong". The teacher review page and the evidence weighting both read this field, so the error propagates.
>
> My plan is written in the worksheet: I read the standard judge verdict set — AC, WA, CE, RE, TLE, MLE, OLE — map each one onto our internal states, then add a diagnostic test that produces a wrong answer and assert the new verdict. Target: 7 November 2026.
>
> I record this as a known defect rather than defend the current behaviour.

---

## 7. Numbers — the master table, and the discrepancies you must fix tonight

### 7.1 Numbers that are safe to quote (verified in this repo tonight)

| Number | Where it comes from |
|---|---|
| 40 problems, 305 test cases, 32 variants, 4 hard negatives, 120 hints | `data/cpp_diagnostics/manifest.json` |
| 8 problems, 77 test cases, 12 variants + 4 hard negatives | `data/cpp_problems/` (original bank) |
| 5 problems per misconception, CPP-M01…CPP-M08 | `docs/CPP_DIAGNOSTIC_BANK_METHOD.md` §3.1 |
| Verification exports: 133 checks / 0 failed (problems bank); 501 checks / 0 failed (diagnostics bank) | `data/cpp_problems/exports/verification_report.json`, `data/cpp_diagnostics/exports/verification_report.json` |
| Weights: static 0.30, diagnostic 0.35, runtime 0.15, general test 0.10, previous same problem 0.10, cross problem 0.20, related success −0.20, conflicting diagnostic −0.20, decay 0.80 | `config/evidence_weights.yaml` |
| Thresholds: review 0.35, margin 0.10, no-misconception 0.80, min cross-problem 2, RECURRED ≥0.45, IMPROVING <0.5, RESOLVED <0.25 | same file + `learner_model/updater.py` |
| 2,000 ms wall clock, 256 MB, 64 KB source, compile 30 s / 2 GB, 4 concurrent executions | `config.py`, test plan §6 |
| Committed experiment export: accuracy 0.3333 both modes, `history_changed_predictions` 0, learner-state accuracy 0.4667, 5 persistent detected, 0 false persistent | `data/exports/experiment_summary.json` |

### 7.2 Discrepancies — reconcile these before tomorrow

1. **Experiment accuracy.** The mid report QA table says "synthetic experiment accuracy 0.47 → 0.87". The committed export says **0.3333 for both modes** on 15 labelled submissions. Decide tonight which run you quote. My advice: re-run `python scripts/run_synthetic_experiment.py`, commit the fresh export, and quote only the committed number. If the panel opens the file and sees 0.33 while your slide says 0.87, that is a credibility problem.
2. **Verification check counts.** Worksheet and `PROBLEM_VERIFICATION_REPORT.md` say 149/149 (Part A) and 581/581 (Part B). The committed `verification_report.json` files say **133** and **501**. The difference is likely the sanitizer and repeat-run checks. Know the reason before you quote either number.
3. **Cited evidence that is not in the repo.** The worksheet cites `bank_e2e_results.json` and `docs/qa/` — neither exists in this checkout. Either commit them or change the citation. A supervisor who clicks a dead link marks it as unverifiable.
4. **Evaluation version.** The worksheet front page says `12c3c26`. Worksheet section 7 says "v0.1.0-mid at main fb94119". The slides say "v0.2.0-mid1 / fb94119". Three answers to one question. Agree one tag, tag it, and use it everywhere.
5. **Planned vs completed ownership.** Report Table 1.2 gives the sandbox to Eman and RBAC to Umaima; Table 1.3 and slide 8 reverse them. Expect a question like "who actually built the sandbox?" Have one sentence ready: "The plan was revised during Iteration 1; the completed table is the truth."
6. **Windows demo risk.** Your own growth questions state that Windows has no memory limit and no file isolation. If the panel asks "can the code on this demo machine read tracelearn.db?", the honest answer today is "yes on Windows". Have that answer ready; do not let them discover it.

### 7.3 Say-this-not-that

| Do not say | Say instead |
|---|---|
| "The AI built my problem bank." | "A generator script that I directed produced the bank data. I disclose it as L4, and I verified it with independent models." |
| "The sandbox is secure." | "The sandbox isolates on Linux with bubblewrap. On Windows there are limits only, and I state that as a limitation." |
| "History improves the diagnosis." | "That is what we are testing. On the current synthetic data, history changes the state and the confidence, not yet the top label." |
| "191 tests pass" without context | "191 of 191 on Linux with g++ and bubblewrap, CI run 38061789808, commit fb94119." |
| "The system detects misconceptions." | "The system finds evidence that supports a misconception hypothesis, and it shows its reasoning. Human review is still required." |
| "It helps students learn better." | "We have no real students yet. All data is synthetic." |

---

## 8. Worksheet Member 1 — cell-by-cell defense map

The supervisor may ask you to **locate, explain, test, or modify** any claimed contribution. Below, every Member 1 worksheet row maps to where it is prepared, and the drill for defending it.

### 8.1 The map

| Worksheet row (Member 1 section) | Prepared at | Drill |
|---|---|---|
| Primary technical ownership | §1, Turn 1 | **Locate:** name the 4 directories — `analysis/`, `diagnosis/`, `learner_model/`, `data/cpp_problems`. |
| Most substantial contribution (bank: 8 problems, 77 tests, 149/149) | §7.1, Turn 5, Q1 | **Test:** run `python -m pytest backend/tests/test_cpp_problem_bank.py -v`. Know that 8/77/149 is the *original* bank and 40/305/501 is the *extended* bank — say which you mean. |
| Problem personally resolved (bank unreachable by students) | §8.2 below | **Locate + explain:** open `api/bank.py`, run the seed scripts live. |
| Highest GenAI level (L4 bank data, L2 engineering) | Q1 | **Explain:** the boundary sentence in §8.2.4. |
| AI-generated output reviewed (305 expected outputs) | Q1 | **Explain:** the independent model, the newline bug, commit `60f6ffe`, SHA-256 manifests. |
| Error or limitation identified (all C++ diagnosed UNCERTAIN 0.2) | §8.3 below | **Explain:** the five causes and the before/after measurements. |
| Substantive modification made (flat tag table → language-keyed) | §8.4 below | **Locate:** `test_analyzer.py:25,46`, `cpp_mapping.py:83`. **Test:** run the two `test_every_*_bank_tag_maps_to_a_scored_code` tests. |
| Task demonstrable without GenAI (run the pipeline, explain every record) | §8.5 below | **Demonstrate:** the record-by-record walkthrough with no AI tool open. |
| Live modification readiness (9th misconception) | §5 | **Modify:** the four-step edit, timed, three rehearsals. |
| Next committed work (misconception registry) | Turn 6, Q10 | **Explain:** registry contents + the test that enforces it + 31 Oct date. |
| Contribution table (commits, tests) | §8.6 below | **Locate:** every hash verified to exist — table below. |
| Technical growth question 1 (AST vs regex) | Q2 | **Explain:** the plan and the 7 Nov date. |
| Technical growth question 2 (verdict vocabulary) | Q11 below | **Explain:** the mapping plan and the 7 Nov date. |
| Technical growth question 3 (cross-language identity) | Q6 | **Explain:** the criterion plan and the 14 Nov date. |
| Member declaration checkboxes | §8.7 below | Pre-flight: each tick must have a visible artefact. |

### 8.2 "Problem personally resolved" — the bank-not-reachable story (60 seconds, verbatim)

> When I finished the bank, `data/cpp_problems` held 8 curated problems, but nothing wrote them into the `problems` table. The README said it plainly: "No loader writes them to the problems table. A student cannot practice on them." The bank was research data with no path to the practice site. I traced the gap to three places that had to agree.
>
> First, the schema. I added request and response models in `backend/app/schemas/bank.py` — commit 649ed3a.
>
> Second, the loader. `scripts/load_problem_bank.py` and `scripts/seed_cpp_diagnostics.py` turn JSON into `problems`, `test_cases`, `problem_hints` and `problem_solutions` rows — commit f117bc4.
>
> Third, the API. `backend/app/api/bank.py` exposes the bank and runs a reference solution, and it never sends `problem_solutions` to a student — commits 0fcaa27 and 1a5bbeb.
>
> I also added per-test execution limits, because a diagnostic test for CPP-M07 must run to the full timeout while a normal test must stop sooner — commits 8f0ec5e and e76e6bc.
>
> I verified all of it from a clean database: `seed_database.py` loaded 6 problems and 36 tests, `seed_cpp_diagnostics.py` loaded 40 problems, 305 tests, 120 hints and 40 solutions — 46 problems total. Then I registered a real student, submitted a correct solution to CP01, and called `POST /api/submissions/{id}/run-and-analyze`. It compiled with g++, ran all 9 tests, returned `execution_status: success`, and wrote the `test_results` and `evidence_items` rows. Every foreign-key check reported zero orphans.

**If they say "show me":** run the two seed scripts and open `api/bank.py` at the response model that excludes `problem_solutions`.

### 8.3 "Error identified" — the bug that killed every C++ diagnosis (90 seconds, verbatim)

> The bank was complete, the runner worked, the evidence was extracted — and every C++ submission was diagnosed UNCERTAIN with confidence 0.2. I found this myself, by running the real variant files through the live API and reading the `evidence_items` rows.
>
> There were five causes. One: `rules.aggregate_scores` built its score dictionary from `ALL_MISCONCEPTIONS`, which held only the three Python codes, so every C++ record was silently dropped. Two: `apply_evidence_weights` had no mapping for `CPP_*` codes, so they all took the 0.05 default. Three: `LearnerStateUpdater.update_from_diagnosis` returned early for anything outside the list, so no learner state was ever written. Four: `TestAnalyzer.TAG_TO_MIS` knew four tag names, and the C++ bank emits eight different ones. Five: the taxonomy had no CPP-M01 to CPP-M08 codes at all.
>
> Measured before the fix: 8 of 8 misconception variants diagnosed UNCERTAIN, zero rows in `learner_states`, zero rows in `learner_state_history`.
>
> My fix was one module: `backend/app/diagnosis/cpp_mapping.py`, the single place that knows both vocabularies, with a comment that states why each row exists. I added `CPP_RANGE_CHECK` and `CPP_STALE_EXIT`, because two beliefs had no backend code. I added `SCORED_MISCONCEPTIONS`, which the diagnosis, the aggregator and the learner model all read. And I added `test_cpp_end_to_end.py`, which reads the bank at run time and fails if a new tag or misconception has no mapping — so this class of bug cannot fail silently again.
>
> Measured after, from the live API: CP01 → CPP_LOOP_BOUNDARY at 1.0, CP02 → M02_INDEX_VALUE at 1.0, CP03 → M03_MISSING_RETURN at 1.0. Commit 12c3c26.

**If they say "show me":** `git show 12c3c26 --stat`, then run `python -m pytest backend/tests/test_cpp_end_to_end.py -v`.

### 8.4 "Substantive modification" — the tag table you rewrote (60 seconds, verbatim)

> `TestAnalyzer` resolved a failing diagnostic test through one flat dictionary, `TAG_TO_MIS`, that knew four tag names. The C++ bank emits eight others — `inclusive_upper_bound`, `value_not_position`, `print_in_place_of_return`, `index_equal_to_size`, `chained_comparison`, `assignment_in_condition`, `no_progress`, `exit_condition_not_updated`. None were in the table, so a failed diagnostic test produced an evidence record with `misconception_id: None` and direction `neutral`. The test had fired correctly and then thrown the result away.
>
> The tag names are also genuinely ambiguous across languages. `upper_boundary` means a Python M01 test in one bank and a C++ M01 test in the other. One flat table cannot be correct for both.
>
> I replaced it with a language-keyed table: `TAG_TO_CODE["python"]` and `TAG_TO_CODE["cpp"]`, resolved through one function, `code_for_diagnostic_tag(language, tag)`. While writing it I caught a concrete data bug: the Python bank emits `index_value`, but the old table held `index_vs_value`, so four Python diagnostic tests were silently producing no evidence. Both spellings are mapped now. The tests `test_every_cpp_bank_tag_maps_to_a_scored_code` and `test_every_python_bank_tag_maps_to_a_scored_code` read the banks at run time and fail if a tag in the data has no mapping.

**If they say "show me":** open `backend/app/analysis/test_analyzer.py` lines 25 and 46, and `backend/app/diagnosis/cpp_mapping.py` line 83. Run the two tests named above.

### 8.5 "Task demonstrable without GenAI" — the record-by-record walkthrough (close every AI tool first)

Do this live, in this order:

1. `backend/app/analysis/pipeline.py` — walk the stages in order: static, test, runtime, diff, history. Then `apply_evidence_weights` and `fuse_diagnosis`.
2. State the design rule out loud: **extraction and interpretation are separate modules.** The analyzers extract; `confidence.py` and `rules.py` interpret.
3. Submit or reuse the off-by-one `for (int i = 0; i <= n; i++)` and show the emitted item: code `CPP_LOOP_LE_BOUND`, `misconception_id: CPP_LOOP_BOUNDARY`, direction `support`, weight 0.30.
4. Open the database and show three tables:
   ```sql
   SELECT id, test_case_id, status, actual_output FROM test_results WHERE submission_id = <id>;
   SELECT code, misconception_id, direction, weight FROM evidence_items WHERE submission_id = <id>;
   SELECT mode, primary_label, primary_confidence FROM diagnoses WHERE submission_id = <id>;
   ```
5. Run `python -m pytest backend/tests/test_history_model.py::test_no_future_history_leakage -v` and explain: the history-aware mode cannot read a submission that happens after the current one.

### 8.6 Contribution table — all your commit hashes are real (verified tonight)

| Hash | Date | Subject as it appears in `git log` |
|---|---|---|
| `bc22b0a` | 23 Aug 2026 | Initial commit: TraceLearn POC |
| `be29457` | 10 Oct 2026 | test(cpp): author misconception diagnostic test cases |
| `93ffdc0` | 10 Oct 2026 | feat(cpp): add verified reference solutions |
| `846c26f` | 10 Oct 2026 | test(cpp): add misconception variants and hard negatives |
| `ec9b8a0` | 10 Oct 2026 | test(cpp): add reference solution and sandbox verifier |
| `ffde987` | 10 Oct 2026 | test(cpp): add problem bank suite and runtime metrics |
| `f117bc4` | 10 Oct 2026 | feat(scripts): add problem bank loader |
| `649ed3a` | 10 Oct 2026 | feat(api): add bank schemas |
| `0fcaa27` | 10 Oct 2026 | feat(api): add problem bank endpoints |
| `1a5bbeb` | 10 Oct 2026 | feat(api): register bank router |
| `8f0ec5e` | 10 Oct 2026 | feat(execution): support per-run memory limit |
| `e76e6bc` | 10 Oct 2026 | feat(execution): apply per-test limits |
| `12c3c26` | 10 Oct 2026 | feat(diagnosis): score the C++ diagnostic bank end to end |
| `60f6ffe` | 10 Oct 2026 | test(cpp): compare variant lines by multiset and normalize model output |
| `fb94119` | 10 Oct 2026 | after QA |

**Anticipated attack:** "All your C++ commits are dated 10 October, seconds apart." Your worksheet already has the answer: the initial `bc22b0a` is the 186-file proposal-stage POC made with AI-assisted scripts; the October commits are the bank work, committed in small steps after one work session. Do not pretend otherwise.

**Three new facts found tonight — fix them before tomorrow:**

1. **No git tag exists.** `git tag -l` is empty. The worksheet says `v0.1.0-mid`; the slides say `v0.2.0-mid1`. Neither exists. Create the real tag tonight and use one version string everywhere.
2. **HEAD is `23b9825`, not `fb94119`.** Your worksheet's evaluation version (`12c3c26`) and section 7 tag (`fb94119`) are both behind main. Agree the evaluation commit, then write it in the worksheet, the slides and the report identically.
3. **The working tree is dirty:** `data/cpp_diagnostics/exports/verification_report.json` is modified and untracked. Commit or stash it — a dirty tree during a repo-evidence review looks bad.

### 8.7 Member declaration — each tick needs a visible artefact

| Tick | Artefact you show if challenged |
|---|---|
| Explain architecture and data flow | Turn 2 script, backed by opening `pipeline.py` |
| Locate and explain my implementation and tests | §8.5 walkthrough; the four directories in §1 |
| Explain a design decision and alternatives | §6 Q3/Q4/Q6, plus the rejected near-neighbour mapping in §5 |
| Disclosed GenAI assistance | Q1; worksheet GenAI register (L4 boundary) |
| Checked citations against sources | Worksheet research table — McMining 67/1,675/1,063; CodeNet data licence CDLA-Permissive-2.0, not Apache-2.0 |
| Reviewed and corrected generated outputs | Q1: independent model, newline bug, `60f6ffe` |
| Can modify my work during questioning | §5 live modification |
| Not represented L4 work as my own | Q1 first sentence |
| Evidence is accurate | §7.2 discrepancies reconciled first |

---

## 10. Beyond your own part — what the pack cannot do for you

### 10.1 Slide-by-slide speaker map (agree this with the team TODAY)

The slides assign no speakers. Agree ownership before you walk in. Based on the worksheet, this is the natural split:

| Slide | Likely speaker | Your line if it falls to you |
|---|---|---|
| 1 Title | Whoever opens (you, per Turn 1) | "We are TraceLearn. Iteration 1 turns a C++ submission into a diagnosis and a hint." |
| 2 Proposal actions | Umaima or you (LLM hints are yours in Iter. 2) | "The panel asked us to use an LLM for user experience. Our answer: the LLM writes the hint text and helps teachers grade. The LLM does not make the diagnosis. Iteration 1 uses no LLM." |
| 3 Iteration plan | You speak **your rows**: schema normalisation, taxonomy, evidence pipeline, deployment | "All my four rows are complete. Evidence: commits 1834765, 12c3c26, b88a962, and the deployed site." |
| 4 Blockers | Shared — know the three: Windows path fix (Eman), C++ scoring (you), attempt race (Umaima) | Yours: "C++ evidence was not scored. I mapped the C++ codes into the scoring in commit 12c3c26." |
| 5 Requirements | Eman/Umaima | — |
| 6 Design evolution | **Image-only slide — no text.** Practise this one aloud; it is the most likely stumble | "This figure shows how the design changed since the proposal: the teacher-review loop was added, the students table was separated, and the C++ bank is new." |
| 7 Core module | You | This is Turn 2, shortened to 60 seconds. |
| 8 Owners/next | Each speaks their row | Yours: "POC core — evidence, diagnosis, learner state; the 40-problem C++ bank; deployment." |
| 9 Next iteration | Shared | Yours: registry (31 Oct), then XGBoost when labelled data exists. |

### 10.2 Thirty-second answers for the OTHER members' areas

The panel can ask anyone about anything. You need awareness-level answers, not depth:

- **Sandbox (Umaima):** "Four layers: bubblewrap namespaces, resource limits, the wall-clock stop, and a concurrency limit of 4. On Windows there are limits only — no isolation — and we state that as a limitation."
- **CI/CD (Umaima):** "GitHub Actions on every pull request: frontend build on Node 22, backend tests on Python 3.11 and 3.12 with g++ and bubblewrap. Known gap: main has no branch protection, so a failing branch can still merge. We recorded that in FR-10 evidence."
- **RBAC (Eman):** "bcrypt password check, HS256 JWT carrying the role, `get_current_user` returns 401, `require_teacher` returns 403. 50 security test cases."
- **Monaco + C++ runner (Eman):** "One compile with g++, each test runs through stdin, output compared token by token, result mapped to a status."
- **Frontend/UI (Umaima):** "React 19 + Vite, student and teacher pages, API client written by hand — the AI's hardcoded version was replaced."

### 10.3 Team rehearsal plan for tonight (90 minutes)

1. **20 min** — full demo steps 1→6, in order, in silence, on the demo machine, twice. Umaima drives; you speak steps 4–5 only.
2. **15 min** — the live modification, timed, three times, with a teammate playing panelist and interrupting you.
3. **20 min** — mock viva: teammates ask you Q1–Q11 in random order. Then you ask each of them the three questions from *their* worksheet row.
4. **15 min** — reconcile the discrepancies in §7.2 (experiment accuracy, tag, evaluation commit, dead evidence links). One decision per item, written into the worksheet.
5. **10 min** — read slide 6 aloud. It has no text and it will be tried live for the first time tomorrow if you do not rehearse it now.
6. **10 min** — agree the slide-by-slide speaker map in §10.1 and send it to the group chat so nobody improvises.

### 10.4 What this document cannot give you

- **Rehearsal.** The script is written; saying it out loud three times is the difference between a 25 and an 80. Your mouth must learn the sentences.
- **Team sync.** Your demo steps depend on Umaima's step 3 producing exactly the `v[v.size()]` submission your script assumes. If she submits different code, your confidence numbers are wrong. Rehearse together or your script is fiction.
- **The real numbers.** Every `[read the real number]` in §4 is still empty. Only a run on the demo machine fills it.
- **Nerves.** Section 7.4 exists because engineers guess numbers under pressure. Sleep is part of the preparation.

---

## 11. Tonight's checklist

- [ ] Rehearse Turns 1–6 aloud, twice, standing up, out loud.
- [ ] Run demo steps 3→4→5 once on the demo machine. Write the real confidence numbers into your script.
- [ ] Practise the live modification three times. Time yourself. Under 8 minutes is the target.
- [ ] Reconcile the six discrepancies in §7.2 with your team, tonight, in one call.
- [ ] Open `backend/app/analysis/pipeline.py`, `diagnosis/confidence.py`, `cpp_mapping.py` and `learner_model/updater.py` and read them once more. These four files are the ones the panel will point at.
- [ ] Prepare the demo student account with the exact prior history your script assumes.
- [ ] Sleep. A tired engineer guesses numbers, and guessing numbers is the only real failure mode tomorrow.

---

## 12. The entire presentation — minute-by-minute run of show

This is the whole event from your chair: room setup, all 9 slides, all 6 demo steps, the live modification, the Q&A, and the close. Timings assume a 20-minute slot plus 10 minutes of questions. Adjust the totals, not the order.

### 12.0 Timing budget

| Phase | Content | Time | Lead |
|---|---|---|---|
| 0 | Room and machine setup | before they call you | Umaima drives, you check evidence |
| A | Slides 1–9 | 8 min | shared; you own slides 1, 3 (your rows), 6, 7 |
| B | Live demo, steps 1–6 | 6 min | Eman 1, Umaima 2–3, **you 4–5**, Umaima 6 |
| C | Live modification (9th misconception) | 5 min | you |
| D | Q&A | 10 min | you answer diagnosis/bank; teammates answer sandbox/CI/UI |
| — | **Total** | **~29 min** | |

If the panel cuts time, cut in this order: slide 9 → slide 4 narration → your Turn 5 validation. Never cut step 5 of the demo and never cut the limitations sentence — honesty is a scoring criterion.

### 12.1 Phase 0 — fifteen minutes before (you, not the team)

| Check | Command / action | Pass condition |
|---|---|---|
| Site up | open https://trace-learn.vercel.app | login page loads |
| Backend healthy | `curl http://localhost:8000/health` (or the deployed URL + `/health`) | `{"status": ...}` returns |
| `g++` present | `g++ --version` on the demo machine | 13.x shown |
| Git clean | `git status` | nothing modified, nothing untracked |
| Evaluation tag | `git tag` | the agreed tag exists and matches the worksheet |
| Demo student | log in, open the step-2 problem | the exact problem Umaima will use is assigned |
| Evidence window | DB browser open on `evidence_items` | second window ready, no typing live |
| Backup | screenshots of a completed run, in a folder | ready to show if the site dies |

Your spoken opening line, once the panel signals you: nothing until the first slide is on screen. Do not talk over the projector.

### 12.2 Phase A — the slides (8 minutes)

**Slide 1 — Title.** Speaker: you.
> "Good morning. We are TraceLearn, project F26-186. Iteration 1 turns one C++ submission into tests, a diagnosis, and a hint. My name is Rayaan; I built the evidence pipeline, the diagnosis, the learner state, and the C++ problem bank."

Hand over: "Umaima will show our proposal actions." Or take slide 2 yourself if agreed (Turn for slide 2 is in §10.1).

**Slide 2 — Proposal actions.** Speaker: Umaima (or you, §10.1 line). Your job: nod, do not touch the keyboard.

**Slide 3 — Iteration plan.** Speaker: shared. When your rows come:
> "My four rows are complete. Schema normalisation: 21 tables with unique attempt numbers, commits 1834765 and fb94119. Taxonomy: 3 Python and 10 C++ codes, commit 12c3c26. Evidence extraction: 5 families, commit b88a962. Deployment: the live site you can open on your phone."

**Slide 4 — Blockers.** Your line when the middle row appears:
> "C++ evidence was not scored, so every C++ submission was flagged uncertain. I mapped the C++ codes into the scoring, commit 12c3c26, and added a no-misconception result when all tests pass, commit fb94119."

**Slide 5 — Requirements.** Eman or Umaima. You prepare silently: mentally run your step 4.

**Slide 6 — Design evolution (image only).** This slide has no text — the figure carries it. Your line, slowly, pointing at the figure:
> "This is how the design moved from the proposal to today. Three changes. One: we added the teacher-review loop, so a teacher can correct a diagnosis without overwriting it. Two: we separated login identity from learner data, so RBAC has classroom assignments. Three: the C++ diagnostic bank is new — it did not exist at the proposal."

If a panel member interrupts here with an architecture question, this is your territory (report §3.1): three layers — student and teacher UI, application services, diagnostic intelligence.

**Slide 7 — Core module.** You. Give the 60-second version of Turn 2: input → sandbox and tests → five analyzers → weighted fusion → two diagnoses → learner state and hint. Stop after the sentence "The current-only engine ignores history; the history-aware engine uses it, and only it updates the learner state."

**Slide 8 — Owners.** Your row:
> "My part: the POC core — evidence, diagnosis and the learner state — the 40-problem C++ diagnostic bank, and the deployment configuration."

If the GenAI line is read here, you add, calmly: "All GenAI use is classified per artefact, L1 to L4, and I disclose one L4 artefact: the bank data. I will show the verification in questions."

**Slide 9 — Next iteration.** Shared close of the slide phase. Your row: the misconception registry, 31 October; XGBoost once labelled data exists.

**Transition to the demo** (whoever holds the keyboard says it, you can say it):
> "That is the design. Now we will show one real submission moving through the whole system, live."

### 12.3 Phase B — the live demo (6 minutes)

The keyboard moves in this order: Eman → Umaima → **you** → Umaima. Practise the handovers; a silent keyboard swap looks like confusion.

**Step 1 (Eman) — sign in as a student.** Expected: the student dashboard opens; teacher pages are blocked. Eman says: "A student cannot reach a teacher endpoint. The API returns 403, proven by 50 security tests." You watch. Do not speak.

**Step 2 (Umaima) — open an assigned C++ problem.** Expected: statement and visible tests only. Umaima says: "Hidden and diagnostic tests never leave the API." You verify silently that this is the same problem your step 4 expects.

**Step 3 (Umaima) — submit incorrect C++** (`v[v.size()]`, index equal to size). Expected: it compiles; some tests fail; status shows `wrong_answer`. Umaima narrates the status and steps aside.

**Step 4 (YOU) — the evidence and diagnosis panel.** Deliver Turn 3, compressed to 90 seconds. The three things to point at, in order: evidence items with direction and weight → the two diagnoses with confidence and uncertainty → the hint level. Then, if nobody interrupts:
> "Notice what the system did not do. It did not guess from one signal. The static pattern and the failing diagnostic test agree, and that is why the confidence is [real number]."

**Step 5 (YOU) — corrected code.** Deliver Turn 4. Submit attempt 2, show `success`, show `TEST_ALL_PASSED` → NO_MISCONCEPTION at 0.80, then open `learner_state_history` and read one row aloud, including its reason field.
> "This is the answer to our research question in miniature: the state is not the mark. It is a record of a belief over time, with its reason, and it is append-only."

**Step 6 (Umaima) — infinite loop and CI.** Expected: timeout at 2,000 ms, the API keeps answering, the CI run passes. Your line when the timeout appears (you own this interpretation, per the worksheet):
> "A timeout is one signal. It is not a diagnosis by itself. The fusion treats it as one weighted item."

**Transition to the modification** (you):
> "Every part I just showed is extensible. I will now add a ninth C++ misconception to the system, live, in four steps."

### 12.4 Phase C — the live modification (5 minutes)

Follow §5 exactly. The spoken frame around it:

1. Before you type: "I add the code to the taxonomy, because the aggregator and the learner model read that list. If I skip it, the evidence is silently dropped — that was a real bug, commit 12c3c26."
2. After the mapping: "This module is the only place that joins the bank vocabulary to the backend vocabulary, and the tests read the bank at run time, so an unmapped tag fails the build."
3. After the hints: "Every scored code needs a fallback hint. The bank's own hints override it."
4. While the tests run: read the output. If green: "The end-to-end suite passes, and the new code now reaches the diagnosis, the learner model and the hints." If anything breaks: the fallback in §5.2 — revert, show the diff on the prepared branch, stay calm.

End the phase with the rejected alternative (§5 step 4), because it shows judgement, not just typing.

### 12.5 Phase D — Q&A (10 minutes)

**Answer ownership.** You answer: evidence, diagnosis, learner state, the C++ bank, GenAI disclosure, research question, datasets and citations. Umaima answers: sandbox, security, CI/CD, frontend, submission logging. Eman answers: RBAC, Monaco, the compile-and-run pipeline, Windows fixes.

**Hand-off phrases** (use them, silence is worse):
- "The sandbox detail is Umaima's work — Umaima?"
- "Eman fixed that Windows path bug; he should tell it."

**Three universal replies:**
- Something is wrong or exaggerated → "That is correct, and we recorded it as a limitation: [one sentence]. The plan is [one sentence]."
- Something you do not know → "I do not know the number. I will measure it and send it after the meeting, by [date]."
- Something already in your Q&A bank → answer with the §6 wording, then stop talking. Do not fill silence with extra claims.

**The question you should hope for** (your best moment): "Show me your evidence." → open `evidence_items` and the two `diagnoses` rows live, or run §8.5. Never claim a number you cannot show.

**The question you must survive**: "Did AI do this?" → Q1, first sentence: "The bank data is L4 and I disclose it. The engineering is mine, and here is the independent verification." Then the newline bug story.

**Closing line** (whoever is asked last, but have it ready):
> "We know what our system does not prove. It does not prove history improves the top label yet, and it has no real students yet. Iteration 2 answers both: labelled data, XGBoost, and the pilot. Thank you."

### 12.6 Your cue card — print this, fold it, keep it in your hand

| Ten numbers | Value |
|---|---|
| Problems / test cases / variants / hints | 40 / 305 / 32 / 120 |
| Misconceptions covered | CPP-M01 … CPP-M08 |
| Limits | 2,000 ms, 256 MB, source 64 KB |
| Weights (static / diagnostic) | 0.30 / 0.35 |
| Review / margin / no-misconception | 0.35 / 0.10 / 0.80 |
| PERSISTENT rule | support on ≥ 2 different problems |
| Correct solutions → NO_MISCONCEPTION | 40 / 40 |
| Hard negatives passing | 4 / 4 |
| History changed predictions | 0 (honestly reported) |
| Evaluation commit / version | [agreed tonight] |

| Four files | Path |
|---|---|
| Pipeline | `backend/app/analysis/pipeline.py` |
| Fusion and weights | `backend/app/diagnosis/confidence.py` |
| Vocabulary bridge | `backend/app/diagnosis/cpp_mapping.py` |
| State rules | `backend/app/learner_model/updater.py` |

| Four sentences that save you | |
|---|---|
| "A timeout is one signal, not a diagnosis." | on execution questions |
| "That is a limitation we recorded, and here is the plan." | on weaknesses |
| "I disclose that as L4; the verification is mine." | on GenAI |
| "I do not know. I will measure it and send it by [date]." | on anything else |
