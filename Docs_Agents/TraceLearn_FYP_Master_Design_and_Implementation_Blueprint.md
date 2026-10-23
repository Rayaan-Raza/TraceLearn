TraceLearn | FYP Master Design and Implementation Blueprint 

# **TraceLearn** 

**Misconception-Aware Programming Practice Platform** 

### **FYP MASTER DESIGN AND IMPLEMENTATION BLUEPRINT** 

TraceLearn  |  1 

TraceLearn | FYP Master Design and Implementation Blueprint 

## **Contents** 

|1. Executive Summary.............................................................................................................................................5|
|---|
|2. Problem Definition, Research Gap, and Contribution............................................................................................6|
|2.1 Problem statement........................................................................................................................................ 6|
|2.2 Why a database alone is insufficient............................................................................................................... 6|
|2.3 Why XGBoost is useful compared with simple descriptive statistics.................................................................6|
|2.4 Research and engineering contribution...........................................................................................................6|
|2.5 Relation to McMining......................................................................................................................................7|
|3. Full FYP Scope and Product Capabilities..............................................................................................................7|
|3.1 In scope........................................................................................................................................................7|
|3.2 Explicitly not the core scope...........................................................................................................................7|
|3.3 Product roles................................................................................................................................................. 7|
|4. End-to-End Student, Teacher, and System Workflows...........................................................................................8|
|4.1 Classroom lifecycle.......................................................................................................................................8|
|4.2 Student flow.................................................................................................................................................. 8|
|4.3 Teacher flow.................................................................................................................................................. 8|
|5. Full System Architecture......................................................................................................................................9|
|5.1 Layer responsibilities.....................................................................................................................................9|
|5.2 Model responsibility separation....................................................................................................................10|
|6. Browser Code Editor and Server-Side Code Execution.........................................................................................10|
|6.1 Monaco Editor.............................................................................................................................................10|
|6.2 Execution location.......................................................................................................................................11|
|6.3 Current no-Docker assumption....................................................................................................................11|
|6.4 Product execution target..............................................................................................................................11|
|6.5 Test taxonomy.............................................................................................................................................11|
|7. Evidence Extraction and Representation............................................................................................................11|
|7.1 Evidence categories..................................................................................................................................... 11|
|7.2 Evidence item contract.................................................................................................................................12|
|7.3 Evidence fusion principles............................................................................................................................12|
|8. Misconception Taxonomy.................................................................................................................................. 13|
|8.1 Label misconceptions as false beliefs, not only error names..........................................................................13|
|8.2 Proposed initial taxonomy structure..............................................................................................................13|
|9. XGBoost Misconception Classifier.....................................................................................................................13|
|9.1 Role in the final system.................................................................................................................................13|
|9.2 Feature design............................................................................................................................................. 14|
|9.3 What should be excluded from the first XGBoost model.................................................................................14|



TraceLearn  |  2 

TraceLearn | FYP Master Design and Implementation Blueprint 

|9.4 Training strategy...........................................................................................................................................14|
|---|
|9.5 Baselines.....................................................................................................................................................14|
|10. Persistent Temporal Learner Model.................................................................................................................. 15|
|10.1 One shared algorithm, individual student states..........................................................................................15|
|10.2 State semantics......................................................................................................................................... 15|
|10.3 Inputs to temporal update..........................................................................................................................15|
|10.4 Example update formulation.......................................................................................................................16|
|10.5 Transition safeguards................................................................................................................................. 16|
|10.6 Optional learned temporal extension..........................................................................................................16|
|11. Database Architecture and Data Contracts......................................................................................................16|
|11.1 Core tables................................................................................................................................................ 17|
|11.2 Data immutability and auditability.............................................................................................................. 18|
|11.3 PostgreSQL vs SQLite.................................................................................................................................18|
|12. Dataset Strategy and Data Engineering............................................................................................................. 18|
|12.1 What data is needed for each subsystem....................................................................................................18|
|12.2 McMining as a labelled misconception source.............................................................................................19|
|12.3 Public Python longitudinal sources.............................................................................................................19|
|12.4 Local TraceLearn data targets.....................................................................................................................19|
|12.5 Common normalized schema.....................................................................................................................20|
|12.6 Splitting and leakage prevention.................................................................................................................20|
|12.7 C/C++ contingency datasets.......................................................................................................................20|
|13. Adaptive Hints, Remediation, and Transfer.......................................................................................................21|
|13.1 Minimum useful intervention......................................................................................................................21|
|13.2 Remedial and transfer problem graph.........................................................................................................21|
|13.3 LLM boundary............................................................................................................................................ 21|
|14. Teacher Decision Support and Human Correction.............................................................................................21|
|14.1 Evidence-first dashboard............................................................................................................................21|
|14.2 Human correction semantics..................................................................................................................... 22|
|15. Evaluation and Experimental Methodology.......................................................................................................22|
|15.1 Research questions....................................................................................................................................22|
|15.2 Experiments and baselines.........................................................................................................................22|
|15.3 Temporal evaluation labels.........................................................................................................................23|
|15.4 Metrics beyond accuracy............................................................................................................................23|
|16. Security, Privacy, Reliability, and Deployment...................................................................................................23|
|16.1 Security boundary...................................................................................................................................... 23|
|16.2 Privacy.......................................................................................................................................................23|
|16.3 Reliability and observability........................................................................................................................24|



TraceLearn  |  3 

|TraceLearn | FYP Mast|er Design and Implementation Blueprint|
|---|---|
|16.4 Deployment architecture................................................................................|............................................24|
|17. Scaling to Real Classrooms..................................................................................|............................................24|
|17.1 Scaling the temporal model to 100+ students..................................................|............................................24|
|17.2 Concurrency strategy......................................................................................|........................................... 24|
|18. Proposal-Stage POC as a Project Milestone...........................................................|...........................................24|
|18.1 POC objective.................................................................................................|........................................... 25|
|18.2 POC scope.....................................................................................................|............................................25|
|18.3 Why not train XGBoost on only the POC data...................................................|............................................25|
|18.4 POC comparison............................................................................................|............................................25|
|18.5 POC success criteria......................................................................................|............................................25|
|19. Full Development Roadmap.................................................................................|............................................26|
|19.1 Phase plan.....................................................................................................|............................................26|
|19.2 Gating rules....................................................................................................|...........................................26|
|20. Risks, Fallbacks, and Scope Control.....................................................................|............................................27|
|21. Three-Person Work Distribution............................................................................|........................................... 27|
|22. Deliverables and Acceptance Criteria...................................................................|............................................27|
|22.1 Required by December...................................................................................|............................................27|
|22.2 Required by mid-April / final............................................................................|i............................................28|
|23. Defense-Ready Positioning..................................................................................|............................................28|
|Appendix A. Proposed Database Tables.....................................................................|............................................29|
|Appendix B. Initial XGBoost Feature Dictionary...........................................................|............................................29|
|Appendix C. Temporal Transition Rules (Initial, to Validate).........................................|............................................30|
|Appendix D. External Dataset Register........................................................................|...........................................30|
|Appendix E. API / Service Outline................................................................................|...........................................31|
|Appendix F. Terminology............................................................................................|........................................... 31|
|References and Source Basis.....................................................................................|...........................................32|



TraceLearn  |  4 

TraceLearn | FYP Master Design and Implementation Blueprint 

## **1. Executive Summary** 

TraceLearn is a classroom-based programming practice platform for beginner Python students (can be shifted to cpp based on stakeholder analysis, however the main process still remains the same). It is designed to move beyond pass/fail grading by converting each programming attempt into structured evidence about what the learner may misunderstand, how strongly that interpretation is supported, whether the pattern persists across time and related problems, and what intervention should happen next. 

The complete FYP consists of a student coding environment, backend code execution and testing, multi-source evidence extraction, an XGBoost-based misconception classifier, a persistent temporal learner model, adaptive hint/remediation logic, a teacher evidence and correction workflow, a longitudinal data store, and a controlled evaluation framework. The platform is necessary infrastructure; the technical and research contribution lies in the diagnosis and learner-modelling workflow rather than in the editor or dashboard alone. 



<!-- Start of picture text -->
User Layer<br>‘Student Web App Teacher Web App<br>Monaco Esitor* Problems © Hints Classroom + Evidence » Interventions<br>Application Services<br>‘Ath+ ClassroomsFastAPI* SubmissionsBackend + APIs<br>ProblemyTest Service Execition Service<br>‘Visible hidden» agnostic tests Pytnon runner * tests «hits<br>Diagnostic4 on<br>Evidence Extraction ModeiContig tore Postaresu<br>Runtime tests «AST + aif «story<br>XGBoostaftact+ taxonomy * thresholds Users + problems + submissions» evidence * states» reviews<br>XGBoost‘Curent submissionMisconception robabitiesClasiier ™ tor earner state + hist‘ory<br>New+ Persistent»Temporal ImprovingLeammer» ResolvedModet * Recired<br>Hint evel»InterventionremediationPolicy* review<br><!-- End of picture text -->

_Figure 1. Full TraceLearn product architecture. The POC implements only a vertical slice of this larger system._ 

**Central distinction:** XGBoost answers “what misconception best explains the current submission?” The temporal learner model answers “what does the current evidence mean in the context of this student’s prior evidence?” The database stores the history and per-student state; it does not itself perform the inference. 

|**Project dimension**|**Target**|
|---|---|
|Language scope|Python, introductory programming through basic data structures.|
|Misconception scope|Approximately 8–12 well-defined misconception beliefs for the integrated prototype;<br>expand only if data quality permits.|



TraceLearn  |  5 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**Project dimension**|**Target**|
|---|---|
|Problem bank|30–40 integrated problems by the December prototype; 40–60 by the final product target.|
|Learner states|New, Persistent, Improving, Resolved, Recurred, plus Teacher Review/Uncertain where<br>needed.|
|Evidence|Execution, visible/hidden/diagnostic tests, AST/static patterns, attempt diffs, prior history,<br>hint response, and problem context.|
|Evaluation|Classifier performance, evidence ablations, temporal-state validity, hint<br>effectiveness/transfer, teacher agreement/usefulness, reliability.|



## **2. Problem Definition, Research Gap, and Contribution** 

#### **2.1 Problem statement** 

Beginner programmers can produce similar incorrect outputs for very different reasons, while the same conceptual weakness can manifest in different code across multiple attempts and problems. A single failed submission therefore does not provide enough evidence to decide whether the learner made a transient implementation mistake or holds a persistent false belief about a programming construct. 

TraceLearn addresses the computing problem of inferring and continually revising a learner’s latent misconception state from incomplete, heterogeneous, and sometimes conflicting evidence. The system must remain explainable, must lower confidence when later evidence contradicts earlier evidence, must avoid turning one failure into a permanent label, and must support intervention without immediately revealing the full solution. 

#### **2.2 Why a database alone is insufficient** 

Updating a database after every submission is necessary for persistence, but it does not solve the reasoning problem. A database can store that a student failed three loop problems; it cannot, by itself, determine whether those failures are evidence of the same misconception, unrelated mistakes, problem difficulty, insufficient prerequisite knowledge, or a pattern that is already improving. The temporal learner model interprets the stored sequence; the database preserves it. 

#### **2.3 Why XGBoost is useful compared with simple descriptive statistics** 

Descriptive statistics such as failure counts, average attempts, or error frequencies are useful evidence but do not naturally learn nonlinear interactions among runtime signals, diagnostic-test failures, AST patterns, and problem context. XGBoost is suitable as a supervised tabular classifier because TraceLearn’s evidence can be represented as structured features, the model works well on mixed sparse/nonlinear feature relationships, provides featureimportance tools, and does not require the scale of data normally expected by large neural models. 

The project should still retain simple statistical/rule baselines. The contribution is strengthened if XGBoost is shown to improve over transparent baselines rather than being assumed superior by default. 

TraceLearn  |  6 

TraceLearn | FYP Master Design and Implementation Blueprint 

#### **2.4 Research and engineering contribution** 

|**Contribution layer**|**What TraceLearn owns**|**What is not claimed as novelty**|
|---|---|---|
|Methodological|Definition and evaluation of a longitudinal<br>misconception-diagnosis workflow that fuses<br>structured evidence and revises learner state over<br>time.|The existence of XGBoost, temporal<br>modelling, databases, AST parsing, or code<br>editors.|
|System architecture|Integration of execution, evidence provenance,<br>classifier output, temporal state, intervention,<br>teacher correction, and audit history into one<br>closed diagnostic cycle.|Building a web interface, REST API, or<br>dashboard by itself.|
|Data/evaluation|A normalized longitudinal dataset schema,<br>controlled synthetic trajectories, mapped public<br>data, local pilot data, annotation protocol,<br>student/problem-aware splits, and temporal<br>evaluation.|Claiming that synthetic data alone<br>represents real student learning.|
|Educational<br>workflow|Minimum useful intervention, transfer tasks, and<br>teacher correction linked directly to diagnosis<br>confidence/state.|An unrestricted LLM tutor or answer<br>generator.|



#### **2.5 Relation to McMining** 

McMining (Al-Hossami and Bunescu, 2026) is highly relevant prior work because it mines potential programming misconceptions from one or multiple student code samples using LLMs. Its multi-instance result supports the idea that multiple samples can provide stronger evidence than a single sample. TraceLearn must therefore not claim that using multiple code samples is itself novel. The stronger project distinction is the complete operational cycle: structured execution/test/static evidence, learned current-submission diagnosis, persistent temporal state, uncertainty, adaptive intervention, teacher correction, and longitudinal evaluation. 

## **3. Full FYP Scope and Product Capabilities** 

#### **3.1 In scope** 

- Python-only browser coding environment for beginner programming and basic data structures. 

- Classrooms, assignments, problem metadata, visible tests, hidden tests, and diagnostic tests. 

- Server-side execution with execution status, stdout/stderr, timeout handling, and per-test outcomes. 

- Static code analysis using Python AST and targeted structural checks. 

- Attempt-sequence analysis and code-diff features. 

- Current-submission misconception classification using rules/baselines and XGBoost when trained data is ready. 

- Persistent learner modelling for each student–misconception pair. 

- Adaptive hints, remedial problems, and transfer problems. 

- Teacher evidence view, class trends, intervention prioritization, and teacher correction/audit. 

- Public-data ingestion, local pilot data collection, annotation, evaluation, and reproducibility tooling. 

#### **3.2 Explicitly not the core scope** 

- Multi-language IDE support in the first version. 

- Competitive-programming leaderboards, plagiarism detection, full LMS replacement, mobile apps, real-time collaboration, or video-course delivery. 

- Open-ended grading of arbitrary free-form programs. 

- An LLM that directly decides the learner state without structured evidence. 

- Training a deep temporal model simply to make the project look more “AI-heavy” when the data does not support it. 

TraceLearn  |  7 

TraceLearn | FYP Master Design and Implementation Blueprint 

#### **3.3 Product roles** 

|**Role**|**Core capabilities**|
|---|---|
|Student|Join classroom; open assigned problem; write/run/submit Python; view test feedback; request<br>hints; receive remediation; see limited learner-progress information.|
|Teacher|Create classroom/assignment; author or select problems/tests; inspect evidence; review<br>student and class trends; confirm/reject/correct diagnoses; assign intervention.|
|Administrator/<br>Researcher|Manage taxonomy/configuration, model versions, data exports, anonymization, evaluation runs,<br>and system monitoring.|



## **4. End-to-End Student, Teacher, and System Workflows** 

#### **4.1 Classroom lifecycle** 

**1.** Teacher creates a classroom and assigns a set of Python problems with concept tags, prerequisites, visible tests, hidden correctness tests, and diagnostic tests. 

**2.** Student opens a problem in the browser-based Monaco editor and writes code. 

**3.** Run/Submit sends the code to the backend; execution occurs server-side, not inside Monaco. 

**4.** The execution service returns stdout, stderr, runtime status, timeout status, and per-test results. 

**5.** Evidence extractors analyze runtime results, diagnostic test categories, AST/static structure, the difference from the previous attempt, problem context, and prior student history. 

**6.** The current-submission classifier produces misconception probabilities and evidence attribution. 

**7.** The temporal learner model combines those probabilities with prior state/history to update the student– misconception state and confidence. 

**8.** The intervention policy selects the least revealing useful hint, a remedial problem, a transfer problem, or teacher review. 

**9.** All artifacts are persisted with provenance so the teacher can see why a diagnosis/state changed. 

**10.** Future attempts produce new evidence; the learner state can strengthen, weaken, improve, resolve, or recur. 



<!-- Start of picture text -->
Gy ~ —_<br><!-- End of picture text -->

_Figure 2. Per-submission closed diagnostic and learning loop._ 

#### **4.2 Student flow** 

- **Before submission:** Problem statement, examples, constraints, concept-neutral instructions, editor, Run/Submit, and optional hint request. 

- **After Run:** Visible execution result, visible tests, syntax/runtime feedback, but no hidden-test answers. 

- **After diagnosis:** A hint matched to confidence and persistence state; low-confidence cases should use generic guidance rather than a strong label. 

- **After improvement:** The system records whether the relevant evidence weakened, whether the hint appeared useful, and whether transfer to a related problem occurs. 

#### **4.3 Teacher flow** 

- View class-level misconception prevalence and change over time. 

- Drill down from class trend → student → misconception → evidence → exact submissions/test failures/static signals. 

TraceLearn  |  8 

   - TraceLearn | FYP Master Design and Implementation Blueprint 

- 

- 

- 

- See system confidence and alternative explanations instead of only a categorical label. 

- Confirm, reject, correct, or mark a diagnosis uncertain; corrections are appended as human labels rather than overwriting system history. 

- Use intervention-priority views to identify students with persistent/recurred high-confidence patterns. 

## **5. Full System Architecture** 

The complete architecture is layered so that UI, execution, intelligence, and persistence can evolve independently. The execution runner should expose a stable contract to the diagnostic layer; similarly, the temporal learner model should consume classifier probabilities and historical evidence through data contracts rather than querying UIspecific objects. 



<!-- Start of picture text -->
User Layer<br>Monaco StudentFit» WebProblems App * Hints Classroom‘Teacher* EvidenceWeb * AppInterventions<br>Application Services<br>FastAPI Backend<br>‘Auth « Classrooms * Submissions * APIS<br>ProblemvTest Service Execution Service<br>Visible «hidden» agnostic tests python runner» tests lis<br>Diagnostic— Pp<br>Runtime Evidencetests * ASTExtraction «dif * history XGBoost artifactModeliContig+ taxonomyStore* thresholds Users « problems + submissionsPostqresQl + evidence + states» reviews<br>XGBonst‘Curent submissionMisconceptionprobabitesClassitier meereeeNee<br>“Temporal Leamer Model<br>New + Persistent» Improving + Resolved * Recured<br>Intervention Policy<br>Hint evel «remediation * review<br><!-- End of picture text -->

_Figure 3. Full system architecture and major service boundaries._ 

#### **5.1 Layer responsibilities** 

|**Layer**|**Responsibilities**|**Primary technologies / design**|
|---|---|---|
|User layer|Student problem/editor experience; teacher<br>classroom/evidence experience.|React; Monaco Editor; charts/tables for<br>evidence and trends.|
|Application<br>services|Auth, classrooms, assignments, submissions,<br>problem metadata, API orchestration.|FastAPI; REST; Pydantic; service layer.|
|Execution|Run Python, invoke tests, collect<br>stdout/stderr/status/resource data.|Current POC: subprocess for trusted data.<br>Product target: isolated execution worker.|
|Evidence<br>extraction|Runtime parser, test categorizer, AST/static<br>detectors, sequence diff, history/context features.|Python ast, difflib/structured diff,<br>deterministic feature extractors.|



TraceLearn  |  9 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**Layer**|**Responsibilities**|**Primary technologies / design**|
|---|---|---|
|Current diagnosis|Misconception probabilities from current evidence.|Rules/statistical baseline + XGBoost.|
|Temporal learner<br>model|Interpret current diagnosis in student history;<br>maintain persistent state/confidence.|Explicit state/update engine first; optional<br>probabilistic learned extension if data<br>supports it.|
|Intervention|Select hint level, remediation/transfer, teacher<br>review.|Policy based on state, confidence,<br>attempt/hint history.|
|Persistence|Store operational data, evidence provenance,<br>predictions, state history, human reviews.|PostgreSQL; migrations; model/config<br>version IDs.|



#### **5.2 Model responsibility separation** 



<!-- Start of picture text -->
oaCumenttestssubmission+ runtimeevidence* context “What misconceptionthis XGBoostsubmission”best explains, + calibratedCassaaprobabitiesconfidence<br>"SESS Per-stdent eae state<br>Improving,“Is ths Isolated.resolved orpersistent,recurea?” seeence erat<br>roe student history<br>related attempts * successes * hints<br><!-- End of picture text -->

_Figure 4. XGBoost, temporal learner model, and database have separate responsibilities._ 

**Design rule:** Do not feed future information into the diagnosis at time t. The system may only use the current submission and events that occurred before it. This applies to feature generation, state updates, dataset creation, and evaluation. 

## **6. Browser Code Editor and Server-Side Code Execution** 

#### **6.1 Monaco Editor** 

The in-browser editor should use Monaco Editor (for example through @monaco-editor/react). Monaco provides the editing experience such as syntax highlighting, line numbers, indentation, bracket matching, and code text access but it is not the compiler or execution engine. The source code is sent to the backend when the student runs or submits. 

|**Editor capability**|**POC / product setting**|
|---|---|
|Language|Python|
|Line numbers|Enabled|
|Syntax highlighting|Python mode|
|Automatic indentation|Enabled|
|Bracket matching|Enabled|
|Minimap|Disabled initially to reduce clutter|
|Run / Submit|Calls backend API with source, problem ID, and attempt metadata|
|Execution|Never delegated to Monaco|



TraceLearn  |  10 

TraceLearn | FYP Master Design and Implementation Blueprint 

#### **6.2 Execution location** 

Compilation/execution occurs on the server side. For Python, the relevant runtime is CPython: code may be bytecompiled internally, but the product should describe the operation as server-side Python execution rather than as a browser compiler. 



<!-- Start of picture text -->
Execution Worker<br>Current POC: subprocess (trusted only)<br>Target product: isolated runner<br>Browser Application Server Inference Services<br>React + Monaco Fastpl |_| xcBoost + tempora update<br>PostgreSQL<br>shared data + per-student state<br><!-- End of picture text -->

_Figure 5. Runtime/deployment boundary: the browser edits code; the backend executes and reasons over it._ 

#### **6.3 Current no-Docker assumption** 

For the proposal POC, the backend may execute trusted synthetic/demo submissions using subprocess.run or subprocess.Popen in a temporary working directory with captured stdout/stderr and a hard timeout. This is acceptable only for controlled code and must not be described as secure sandboxing. Arbitrary student code should not be exposed to this runner on a public deployment. 

#### **6.4 Product execution target** 

The final product requires an isolated execution boundary. The exact technology can remain an implementation decision—container, restricted worker VM, OS sandbox, or a separate execution service—but the contract should remain stable: source code + test bundle + limits → execution status + test results + resource information. This lets security hardening occur without changing the diagnosis, database, or UI architecture. 

#### **6.5 Test taxonomy** 

|**Test type**|**Purpose**|**Student visibility**|
|---|---|---|
|Visible tests|Basic correctness and examples; immediate formative<br>feedback.|Inputs/expected outcomes can<br>be shown.|
|Hidden tests|Prevent hard-coding and assess general correctness.|Outcome only; details limited.|
|Diagnostic tests|Target misconception-sensitive edge cases or behaviors.|Usually outcome/category, not<br>necessarily full expected<br>answer.|
|Transfer<br>tests/problems|Check whether understanding transfers to a related but non-<br>identical task.|Presented as later<br>practice/evaluation.|



## **7. Evidence Extraction and Representation** 

TraceLearn should treat every inference as evidence-backed. A prediction must be reproducible from stored evidence items, each with a source, direction, strength/weight, affected misconception, extractor/model version, and timestamp. This protects the system from becoming a black box and lets teachers audit why state changed. 

TraceLearn  |  11 

TraceLearn | FYP Master Design and Implementation Blueprint 

#### **7.1 Evidence categories** 

|**Evidence source**|**Examples**|**Role**|
|---|---|---|
|Execution|SyntaxError, IndexError, timeout, return code, stdout/stderr<br>mismatch.|Strong behavioral signals but often<br>non-specific by themselves.|
|Diagnostic tests|Boundary case failed, empty-list case failed, return-value-<br>specific test failed.|Problem-aware evidence designed<br>to distinguish hypotheses.|
|Static AST|range bound form, use of loop variable as index, missing<br>return path, boolean structure, recursion progress.|Structural explanation independent<br>of output alone.|
|Attempt sequence|Lines/AST nodes changed, same suspicious pattern<br>retained, error type changed, number of attempts.|Shows debugging behavior and<br>whether the relevant behavior<br>improves.|
|Historical|Same belief on another related problem, prior<br>state/confidence, related successes, recurrence after<br>resolution.|Primary input for temporal<br>persistence and decay.|
|Context|Concept tags, prerequisites, problem difficulty/category.|Constrains which misconceptions<br>are plausible.|
|Teacher/hint|Teacher correction, hint level used, response after hint.|Human supervision and<br>intervention-response evidence.|



#### **7.2 Evidence item contract** 

|**Field**|**Example**|
|---|---|
|evidence_id|EV_20481|
|submission_id|SUB_8451|
|source_type|diagnostic_test / static_ast / runtime / sequence / history|
|misconception_id|M01_RANGE_UPPER_BOUND|
|direction|support / conflict|
|strength|0.35 (configuration value or learned feature attribution)|
|description|Boundary diagnostic fails when n is expected to be excluded.|
|extractor_version|diag-tests-v3|
|created_at|timestamp|



#### **7.3 Evidence fusion principles** 

- No single weak signal should force a persistent diagnosis. 

- Supporting and conflicting evidence must both be preserved. 

- Current code correctness does not necessarily erase a prior misconception immediately; sustained success is more informative. 

- Repeated same-problem failure can strengthen suspicion but cross-problem recurrence is stronger evidence of persistence. 

- Correct related performance should reduce confidence and can move Persistent → Improving → Resolved. 

- When top hypotheses are close or evidence conflicts, output uncertainty/teacher review rather than a false precise answer. 

TraceLearn  |  12 

TraceLearn | FYP Master Design and Implementation Blueprint 

## **8. Misconception Taxonomy** 

#### **8.1 Label misconceptions as false beliefs, not only error names** 

The McMining paper provides a useful taxonomy-writing lesson: a misconception should state the learner’s incorrect belief about a programming construct in a concise, generalizable form. “Off-by-one error” is a symptom; “the student believes range(n) includes n” is a misconception hypothesis. 

#### **8.2 Proposed initial taxonomy structure** 

|**ID**|**Area**|**Belief-style misconception statement**|**Typical evidence**|
|---|---|---|---|
|M01|Loops / range|Student believes that range(n) includes n as the final<br>generated value.|Boundary diagnostic failure;<br>loop-bound AST; recurrence<br>across loop problems.|
|M02|Iteration / lists|Student believes that the loop variable in “for x in values”<br>represents the index of x.|Subscript using loop value;<br>IndexError; wrong element<br>selection.|
|M03|Functions|Student believes that printing a computed value is<br>equivalent to returning it from a function.|print present; missing return;<br>return-specific diagnostic fails.|
|M04|Indexing|Student believes valid positive list indices include len(list).|IndexError at boundary; n/len<br>used directly as last index.|
|M05|Conditionals|Student believes “x == a or b” compares x against both a and<br>b.|AST boolean structure;<br>diagnostic branches.|
|M06|Assignment/comparison|Student believes assignment and equality comparison are<br>interchangeable in conditions.|Syntax/AST pattern depending on<br>formulation.|
|M07|Recursion|Student believes recursive calls progress automatically<br>without changing the state/argument.|Recursive call with unchanged<br>parameter;<br>timeout/RecursionError.|
|M08|Base cases|Student believes recursive functions do not require a<br>terminating base condition for finite input.|Missing/ineffective base case;<br>recursion diagnostic.|



## **9. XGBoost Misconception Classifier** 

#### **9.1 Role in the final system** 

XGBoost is the planned learned model for current-submission misconception classification. It receives a feature vector describing the current attempt and outputs a probability distribution over the supported misconception classes plus NONE/NO_MISCONCEPTION (and, depending on the evaluation design, an uncertainty threshold handled outside the classifier). It should not directly own the persistent learner-state lifecycle. 



<!-- Start of picture text -->
AST = tests nme > crtext reeoeyion Dest + calrated contdence cemporal Leamer Model Per-student leamer state.<br>see skate. pret tar la<br>improving tesved orcad?<br>cr stent istry<br>foaled wong ssureesees = its<br><!-- End of picture text -->

_Figure 6. XGBoost makes the current-submission diagnosis; the temporal model interprets it longitudinally._ 

TraceLearn  |  13 

TraceLearn | FYP Master Design and Implementation Blueprint 

#### **9.2 Feature design** 

|**Feature group**|**Illustrative features**|
|---|---|
|Execution|syntax_error_type, runtime_error_type, timeout, output_type_mismatch,<br>exception_family|
|Test|visible_pass_rate, hidden_pass_rate, diagnostic_boundary_fail, diagnostic_return_fail,<br>empty_input_fail, min/max_input_fail|
|Static AST|has_return, return_path_count, print_without_return, range_stop_expression_type,<br>loop_value_used_as_index, suspicious_boolean_or, recursive_call_argument_change|
|Current-attempt context|problem_concepts, prerequisite tags, difficulty, attempt_number, code_length/AST<br>counts|
|Optional derived statistics|number of changed AST nodes, error-family indicators, code complexity measures only if<br>justified and stable|



#### **9.3 What should be excluded from the first XGBoost model** 

- Future attempts or future learner-state information. 

- Ground-truth misconception/state labels as features. 

- Student IDs or problem IDs used in a way that encourages memorization instead of generalization. 

- History-derived features in the primary current-only model. A second history-augmented classifier can be evaluated later, but the main comparison should preserve a clean boundary between current diagnosis and temporal reasoning. 

#### **9.4 Training strategy** 

**1.** Map selected McMining misconception labels to the TraceLearn belief taxonomy where the mapping is semantically defensible. 

**2.** Run TraceLearn’s feature extractors on the code rather than copying labels into features. 

**3.** Add negative/no-misconception examples and local annotated examples. 

**4.** Freeze the feature definition and label mapping before final holdout evaluation. 

**5.** Use student-aware and, where possible, problem-aware splits to reduce identity/problem leakage. 

**6.** Handle class imbalance with class/sample weights, targeted data collection, macro-F1 reporting, and per-class metrics rather than accuracy alone. 

**7.** Tune hyperparameters only on training/validation data; never tune after viewing the final holdout. 

**8.** Calibrate confidence (for example using held-out validation calibration) if raw probabilities are used for intervention thresholds. 

#### **9.5 Baselines** 

|**Baseline**|**Purpose**|
|---|---|
|Majority / simple frequency|Sanity check; shows class imbalance.|
|Rule-only evidence engine|Transparent engineering baseline and fallback.|
|Logistic regression / shallow<br>statistical model|Tests whether nonlinear XGBoost interactions are actually needed.|



TraceLearn  |  14 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**Baseline**|**Purpose**|
|---|---|
|XGBoost current-only|Primary learned classifier.|
|Optional history-augmented<br>XGBoost|Ablation/extension only; do not confuse with the persistent state model.|
|McMining-style LLM baseline|External comparison if API cost/privacy permits; not the core production diagnosis<br>path.|



## **10. Persistent Temporal Learner Model** 

#### **10.1 One shared algorithm, individual student states** 

The product does not train or maintain a separate temporal model for every learner. There is one shared state-update algorithm (and, if a learned temporal extension is later added, one globally trained temporal model). The database stores a separate state record for each student–misconception pair. For 100 students and 10 misconceptions, this is roughly 1,000 current state rows plus history—trivial for PostgreSQL. 



_Figure 7. Proposed learner-state lifecycle. Exact thresholds are configuration values to be validated, not fixed truths._ 

#### **10.2 State semantics** 

|**State**|**Meaning**|
|---|---|
|New|Credible evidence has appeared, but there is not yet enough longitudinal support to call it<br>persistent.|
|Persistent|Strong repeated evidence, preferably across related problems or clearly repeated conceptual<br>behavior.|
|Improving|Previously persistent evidence is weakening and recent related successes support conceptual<br>progress.|
|Resolved|Sustained related success and absence of strong supporting evidence reduce the active<br>misconception confidence below the resolution threshold.|
|Recurred|A previously resolved misconception is supported again by strong new evidence.|
|Teacher Review /<br>Uncertain|Evidence is conflicting, confidence is low, or top hypotheses are too close for a reliable<br>automated state.|



#### **10.3 Inputs to temporal update** 

- Current XGBoost misconception probability and current evidence strength. 

- Previous learner state and previous confidence for the same misconception. 

- Number and recency of supporting events. 

- Whether support comes from the same problem or different related problems. 

- Related successful attempts and transfer performance. 

- Hint exposure and whether the relevant evidence changed after hints. 

TraceLearn  |  15 

TraceLearn | FYP Master Design and Implementation Blueprint 

- Teacher corrections or confirmed labels. 

- Time/attempt distance since previous evidence, used for decay where appropriate. 

#### **10.4 Example update formulation** 

A transparent starting formulation can maintain a confidence value C_t for each student–misconception pair. One possible design is: 

##### **C = clip( d·Cₜ ₜ₋₁ + α·P + β·R − γ·S − δ·Q , 0, 1 )ₜ ₜ ₜ ₜ** 

where d is evidence decay, P is the current classifier/evidence support, R captures cross-problem recurrence, Sₜ ₜ ₜ captures related successful evidence, and Q captures conflicting/uncertain evidence. The values are designₜ parameters to be validated; the final report must not present arbitrary thresholds as learned truths. 

#### **10.5 Transition safeguards** 

- One submission must never directly create a high-confidence Persistent state. 

- Repeated failures on the same problem strengthen suspicion but should generally not be as strong as recurrence on a different related problem. 

- Future information is prohibited when computing the state at time t. 

- After Resolution, strong evidence can trigger Recurred; the system should preserve the prior resolved episode in history rather than overwriting it. 

- Teacher corrections append an audit event and can change the active state, but the original automated prediction remains preserved for evaluation. 

#### **10.6 Optional learned temporal extension** 

If enough real longitudinal labels are eventually available, the team can compare the explicit state engine with a probabilistic/learned temporal model such as a calibrated transition model, Bayesian/Markov approach, or other interpretable learner model. A deep LSTM is not required and should not be introduced unless the sequence volume and research question justify it. 

## **11. Database Architecture and Data Contracts** 

The database is the system’s longitudinal memory. It stores raw attempts, derived evidence, model predictions, temporal state history, hint events, and human corrections. The model logic remains shared; only the state/data are individualized. 

TraceLearn  |  16 

TraceLearn | FYP Master Design and Implementation Blueprint 



<!-- Start of picture text -->
USERS<br>student / teacher / admin<br>CLASSROOMS<br>PROBLEMS<br>tudent_id jeacher_id<br>TEST_CASES SUBMISSIONS<br>HINT_EVENTS TEST_RESULTS EVIDENCE_ITEMS DIAGNOSES<br>LEARNER_STATES TEACHER_REVIEWS<br>LEARNER_STATE_HISTORY<br><!-- End of picture text -->

_Figure 8. Simplified database/entity relationship view._ 

#### **11.1 Core tables** 

|**Table**|**Purpose**|**Representative fields**|
|---|---|---|
|users|Student/teacher/admin identity and role.|id, role, pseudonymous_research_id|
|classrooms|Teacher-owned classroom and<br>memberships.|id, owner_id, term/status|
|problems|Problem statement, concepts,<br>prerequisites, difficulty.|id, title, concept_tags, prerequisite_tags|
|test_cases|Visible, hidden, diagnostic test definitions.|problem_id, type, category, input/expected, visibility|
|submissions|Immutable source attempt record.|student_id, problem_id, attempt_no, source_code,<br>created_at|
|test_results|Per-test outcome for a submission.|submission_id, test_id, passed, actual, error_type|
|evidence_items|Explainable diagnostic evidence.|submission_id, source_type, misconception_id,<br>support/conflict, strength, version|
|diagnoses|Classifier/baseline outputs.|submission_id, model_version, class probabilities,<br>primary/alternative label, confidence|
|learner_states|Latest state per student–misconception.|student_id, misconception_id, state, confidence,<br>updated_at|



TraceLearn  |  17 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**Table**|**Purpose**|**Representative fields**|
|---|---|---|
|learner_state_history|Every state transition and reason.|old_state, new_state, trigger_submission_id,<br>confidence_before/after|
|hint_events|Hint exposure and response context.|submission_id/problem_id, level, misconception_id,<br>delivered_at|
|teacher_reviews|Human confirm/reject/correct/uncertain<br>action.|diagnosis_id, teacher_id, action, corrected_label,<br>notes|



#### **11.2 Data immutability and auditability** 

- Submissions are immutable; corrections produce new attempts, not edits to historical rows. 

- Diagnoses carry model/config versions so predictions remain reproducible after retraining. 

- Learner state history is append-only for audit/evaluation. 

- Teacher reviews do not delete system predictions. 

- Research exports use pseudonymous IDs and omit direct identifiers. 

#### **11.3 PostgreSQL vs SQLite** 

SQLite is acceptable for a single-machine POC because it minimizes setup. The integrated product should use PostgreSQL to support concurrent classrooms, indexing, robust transactions, JSON metadata where useful, migrations, backups, and operational monitoring. There is still one shared application database; do not create a separate database per student. 

## **12. Dataset Strategy and Data Engineering** 

The dataset plan should not assume the team can manually collect or label thousands of examples. Different public and local sources answer different research questions. The key is to normalize them into a common TraceLearn schema and keep provenance explicit. 



<!-- Start of picture text -->
MeMining<br>labelled misconception code<br>ProgFeed / CSEDM / HELP-DKT Detector dataset<br>teal attempt sequences twaindvalidate XGBoost<br>—$r<br>‘Common TraceLearn schema Helc-out final evaluation<br>student» problem + attempt<br>* code+ labels student- and problem-aware splits<br>TraceLeam local pilot Temporal evaluation set<br>real code + hints + reviews ordered student trajectories<br>Controlled synthetic trajectories<br>POC and edge cases<br><!-- End of picture text -->

_Figure 9. Multi-source dataset strategy for current diagnosis, temporal evaluation, and final holdout testing._ 

#### **12.1 What data is needed for each subsystem** 

|**Subsystem / question**|**Required data**|**Best sources**|
|---|---|---|
|Misconception classifier|Code + problem context + misconception/no-<br>misconception label; ideally tests.|McMining benchmark + local human<br>labels + controlled synthetic edge cases.|
|Temporal learner model|Ordered attempts by stable student ID,<br>problem relations, correctness/evidence,|ProgFeed, CSEDM 2019, HELP-DKT,<br>FalconCode where accessible, plus|
||ideally human state labels.|TraceLearn pilot.|



TraceLearn  |  18 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**Subsystem / question**|**Required data**|**Best sources**|
|---|---|---|
|Hint effectiveness|Hint event + pre/post attempts + time/order +<br>success/transfer.|ProgFeed for behavior patterns;<br>TraceLearn pilot for system-specific hint<br>policy.|
|Final validity|Real TraceLearn student trajectories with<br>human-reviewed misconception/state labels.|Local pilot/research deployment.|



#### **12.2 McMining as a labelled misconception source** 

The 2026 McMining benchmark is especially valuable because it includes a misconception bank and code samples explicitly designed to exhibit those misconceptions. The repository reports 67 misconceptions and 1,063 code samples exhibiting them, along with correct/no-misconception examples and multi-code bags. TraceLearn should select only the subset that maps cleanly to its own 8–12 belief taxonomy, then run its own feature extractors on the code. 

#### **12.3 Public Python longitudinal sources** 

|**Dataset**|**Useful properties for TraceLearn**|**Primary role**|
|---|---|---|
|ProgFeed|De-identified introductory-programming submissions, per-<br>submission code/autograder data, feedback condition/text, problem<br>descriptions.|Attempt/hint-response<br>analysis and external temporal<br>behavior data.|
|CSEDM 2019 / ITAP|ProgSnap-style ordered events, stable student IDs, code states,<br>correctness, hint requests; explicit knowledge-tracing framing.|Temporal modelling,<br>chronology/leakage<br>methodology, student-held-<br>out evaluation patterns.|
|HELP-DKT|9,119 Python source codes with buggy/correct flag, challenge ID,<br>stable student ID, and submission number.|Repeated-attempt sequence<br>experiments and<br>representation testing.|
|FalconCode|Over 1.5M Python programs from >2,000 students and >800<br>assignments; prompts/tests/skills metadata; access depends on<br>distribution route.|Large-scale external<br>code/evidence experiments<br>and transfer/generalization<br>studies.|



#### **12.4 Local TraceLearn data targets** 

The project’s own collection remains important because public datasets will not contain TraceLearn’s exact misconception labels, temporal states, intervention policy, and teacher review workflow. A realistic target remains a pilot rather than a thousand manually labelled examples. 

|**Stage**|**Target**|**Purpose**|
|---|---|---|
|Initial controlled data|Synthetic/controlled examples for every<br>supported misconception; positive and<br>negative examples.|Technical testing and rule/feature development<br>only.|
|FYP-I student testing|Approximately 5–10 students solving 10–<br>15 selected problems.|Refine taxonomy, diagnostics, UI, annotation<br>handbook, and failure cases.|
|FYP-II pilot|Approximately 15–40 participants where<br>feasible; 15–25 evaluated problems; 300<br>–800 total submissions if recruitment<br>permits.|Real longitudinal evaluation and system usability.|



TraceLearn  |  19 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**Stage**|**Target**|**Purpose**|
|---|---|---|
|Human-labelled<br>subset|Approximately 150–300<br>submissions/trajectory segments where<br>achievable; substantial double<br>annotation.|Final precision/recall/F1, state validity,<br>disagreement analysis.|



#### **12.5 Common normalized schema** 

|**Field**|**Description**|
|---|---|
|dataset_source|MCMINING / PROGFEED / CSEDM / HELP_DKT / FALCONCODE / TRACELEARN_SYNTHETIC /<br>TRACELEARN_REAL|
|student_id|Stable pseudonymous learner ID within source.|
|problem_id|Normalized problem ID with source-specific mapping.|
|attempt_order|Chronological order within learner/problem and global learner history where available.|
|source_code|Raw/normalized source with provenance.|
|correct/test_results|Outcome evidence where available.|
|concept_tags|Normalized concepts/prerequisites if available or mapped.|
|misconception_label|Nullable; only populated when supported by source or human annotation.|
|state_label|Nullable; populated only for real/controlled trajectory annotations.|
|hint_event|Nullable; level/type/text identifier when available.|
|source_split|development / validation / holdout; never infer from row order after analysis.|



#### **12.6 Splitting and leakage prevention** 

- Never random-split individual attempts from the same student across train and final test if the model can exploit student history. 

- Primary generalization split: hold out students (GroupKFold/leave-one-student-out where scale allows). 

- Problem-held-out experiment: train on some problems and test on unseen related problems to measure whether the model learned the misconception rather than the exercise template. 

- Temporal split within a student must respect time: no future event may generate a feature for an earlier event. 

- Keep synthetic/demo trajectories separate from holdout evaluation trajectories. 

- Freeze taxonomy mappings, evidence extraction, and final feature definitions before the true holdout is evaluated. 

#### **12.7 C/C++ contingency datasets** 

Python remains the primary product language. C/C++ datasets are a contingency if Python data access becomes insufficient for a particular methodological experiment. The most useful backups discussed are CodeStream (iterative C/C++/Java attempt histories), PROGpedia (student submissions plus code property graphs), and Project CodeNet (very large C++ corpus with submission metadata). If used, their role must be stated as external methodological validation rather than silently changing the product scope. 

TraceLearn  |  20 

TraceLearn | FYP Master Design and Implementation Blueprint 

## **13. Adaptive Hints, Remediation, and Transfer** 

#### **13.1 Minimum useful intervention** 

TraceLearn should not reward every failure with a full explanation. Intervention depends on diagnosis confidence, learner state, previous hint exposure, and evidence of improvement. The objective is to give the least revealing support that can move the learner toward conceptual progress. 

|**Level**|**Intervention**|**When appropriate**|
|---|---|---|
|1|Guiding question|Low/medium confidence or early attempt; prompts<br>reflection without naming the exact fix.|
|2|Concept reminder|Likely misconception; reminds relevant semantics (e.g.,<br>range behavior) without rewriting code.|
|3|Code-region focus|Points to the relevant construct/region and asks the learner<br>to inspect a specific relationship.|
|4|Partial logical correction|High confidence and repeated unsuccessful attempts;<br>explains the conceptual correction without providing full<br>final code.|
|5|Full explanation / worked teaching<br>response|Escalation after repeated failure or teacher-approved<br>remediation; should be logged and evaluated for answer<br>leakage/dependency.|



#### **13.2 Remedial and transfer problem graph** 

- Each problem should carry concept and prerequisite tags. 

- Each supported misconception should map to at least one simpler remedial task and one related transfer task. 

- Remedial tasks test the exact concept with reduced problem complexity. 

- Transfer tasks alter surface structure so success is evidence of conceptual learning rather than memorized patching. 

- The learner model should use transfer success as stronger conflicting evidence against persistence than sameproblem correction alone. 

#### **13.3 LLM boundary** 

An LLM may be used to realize teacher-approved hint templates or explain already-structured diagnoses, but it should not be the hidden source of the diagnosis itself. Inputs should include the selected misconception, evidence summary, permitted hint level, and “do not reveal solution” constraints. The produced text should not alter the learner state unless new student evidence is generated afterward. 

## **14. Teacher Decision Support and Human Correction** 

#### **14.1 Evidence-first dashboard** 

The teacher dashboard should lead with instructional decisions and evidence, not decorative charts. Every class trend should be drillable to supporting submissions and every student-level alert should explain confidence, evidence, and a recommended next action. 

|**View**|**Key content**|
|---|---|
|Class overview|Misconception prevalence, newly persistent/recurred cases, improvement/resolution<br>trends, students needing review.|



TraceLearn  |  21 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**View**|**Key content**|
|---|---|
|Student evidence profile|Current state/confidence per misconception, timeline, related submissions, hints,<br>successes, teacher actions.|
|Diagnosis inspector|Current code, test outcomes, AST/static evidence, classifier probabilities, alternative<br>hypothesis, supporting/conflicting signals.|
|Intervention queue|Prioritized students based on persistence, recurrence, confidence, repeated unsuccessful<br>attempts, and review flags.|
|Correction/audit|CONFIRM, REJECT, CORRECT, MARK_UNCERTAIN; reason/notes; correction feeds future<br>evaluation and model-development datasets.|



#### **14.2 Human correction semantics** 

- Teacher labels are stored separately from automated predictions. 

- Corrections can update the active learner state but must preserve the original model result and prior state history. 

- For training/evaluation, only agreed/quality-controlled teacher labels should become ground truth. 

- Teacher disagreement should be reportable rather than forced into a single false label. 

## **15. Evaluation and Experimental Methodology** 

#### **15.1 Research questions** 

|**RQ**|**Question**|
|---|---|
|RQ1|Can structured execution/test/static evidence identify supported beginner-programming misconceptions<br>better than simple single-source/rule/statistical baselines?|
|RQ2|Does XGBoost improve current-submission misconception classification over transparent baselines on held-<br>out students/problems?|
|RQ3|Does longitudinal history improve identification of persistent misconception states compared with treating<br>each submission independently?|
|RQ4|Can the temporal model correctly represent improvement, resolution, and recurrence without permanently<br>labelling learners after isolated mistakes?|
|RQ5|Do confidence/state-aware hints and remedial/transfer tasks improve attempts-to-success and transfer<br>compared with fixed/static feedback?|
|RQ6|Does the teacher evidence/correction workflow provide useful, trustworthy intervention support?|



#### **15.2 Experiments and baselines** 

|**Experiment**|**Comparisons**|**Main metrics**|
|---|---|---|
|Current diagnosis|Runtime-only vs test-only vs static-only vs rule-fusion vs<br>logistic/statistical vs XGBoost.|Macro precision/recall/F1, per-class F1,<br>confusion matrix, false-positive rate on no-<br>misconception cases.|
|History value|Current-only diagnosis/state vs history-aware temporal<br>model on same chronological events.|State accuracy/agreement, false-persistent<br>rate, missed-persistent rate, correct<br>history-induced changes.|
|Ablation|Full evidence vs remove one source at a time.|Δ macro-F1, calibration, state agreement.|



TraceLearn  |  22 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**Experiment**|**Comparisons**|**Main metrics**|
|---|---|---|
|Transfer|Seen problem families vs held-out related problems.|Performance drop, transfer success after<br>remediation.|
|Hinting|Fixed hint baseline vs confidence/state-aware policy.|Attempts to success, time to success,<br>repeated misconception frequency,<br>transfer performance.|
|Teacher workflow|System prediction vs teacher review and usefulness<br>survey/task timing.|Agreement, correction frequency, time<br>saved, perceived usefulness/trust.|



#### **15.3 Temporal evaluation labels** 

A temporal-state label should be assigned to an ordered trajectory segment, not to an isolated code file without context. Annotators should see only information that would be available at that point in time. Recommended labels are Isolated/No persistent misconception, New, Persistent, Improving, Resolved, Recurred, and Uncertain/Teacher Review. For final evaluation, two annotators should label a substantial subset and disagreement should be measured and adjudicated. 

#### **15.4 Metrics beyond accuracy** 

- Macro-F1 and per-class precision/recall/F1 for imbalanced misconception classes. 

- False-positive rate on correct/no-misconception submissions. 

- False-persistent rate: isolated behavior incorrectly escalated to Persistent. 

- Missed-persistent rate: repeated/cross-problem patterns not recognized. 

- Calibration metrics/reliability plot if confidence probabilities drive interventions. 

- Inter-annotator agreement for misconception/state labels. 

- Transfer performance on unseen related problems. 

- Teacher correction frequency and actionability/usefulness measures. 

## **16. Security, Privacy, Reliability, and Deployment** 

#### **16.1 Security boundary** 

Executing student code is the highest operational security risk. The current subprocess POC is explicitly restricted to trusted demo data. Before public/student deployment, the execution service must enforce isolation, hard timeouts, memory/CPU/process limits, restricted filesystem access, blocked or tightly controlled network access, and cleanup of temporary resources. Abuse tests should be part of acceptance. 

#### **16.2 Privacy** 

- Use pseudonymous research identifiers for exports and model-development data. 

- Separate operational identity information from research datasets. 

- Do not send student code to third-party LLM APIs without explicit governance/approval; prefer structured local processing for diagnosis. 

- Log teacher corrections and model versions but avoid collecting unrelated personal data. 

- Define data retention/deletion policy before the pilot. 

#### **16.3 Reliability and observability** 

- Execution timeouts and worker failure must produce explicit status, not hang the submission flow. 

- Model inference failure should fall back to test/runtime feedback and mark diagnosis unavailable/uncertain. 

- Database migrations and backups are required before pilot deployment. 

- All model/config versions used for a diagnosis should be logged. 

- Provide an offline/local backup demo for final defense reliability. 

TraceLearn  |  23 

TraceLearn | FYP Master Design and Implementation Blueprint 

#### **16.4 Deployment architecture** 



<!-- Start of picture text -->
Execution Worker<br>Current POC: subprocess (trusted only)<br>‘Target product: isolated runner<br>Browser Application Server Inference Services<br>(comes J Sete PostgreSQL<br>shared data + per-student state<br><!-- End of picture text -->

_Figure 10. Deployment architecture and replaceable execution boundary._ 

## **17. Scaling to Real Classrooms** 

#### **17.1 Scaling the temporal model to 100+ students** 

TraceLearn uses shared inference logic with per-student state data. A class of 100 students does not require 100 XGBoost models or 100 temporal algorithms. The same XGBoost model classifies each current submission, and the same temporal update function reads that learner’s prior state/history before updating only that learner’s records. 

|**Example scale**|**Approximate records / implication**|
|---|---|
|100 students × 10 misconceptions|≈1,000 current learner_state rows.|
|100 students × 20 problems × 4 attempts|≈8,000 submission rows plus per-test/evidence rows; ordinary relational-<br>database scale.|
|Model artifacts|One active XGBoost artifact per model version, not per student.|
|Temporal logic|One shared update implementation; state is keyed by (student_id,<br>misconception_id).|



#### **17.2 Concurrency strategy** 

- API requests should be stateless beyond database/model-store access. 

- Execution is the expensive workload and should be separable into workers if concurrent demand increases. 

- Inference is lightweight compared with execution and can typically run in the application service initially. 

- Use indexes on student_id, problem_id, submission time/order, misconception_id, and active learner state. 

- Cache read-only problem/test metadata where appropriate, but do not cache mutable learner state without consistency rules. 

## **18. Proposal-Stage POC as a Project Milestone** 

**POC positioning:** The POC is a small vertical slice used to validate feasibility and expose design failures early. It is not the final architecture, not the entire FYP focus, and not sufficient evidence for claims about real-world educational effectiveness. 

#### **18.1 POC objective** 

The proposal POC should demonstrate the complete information path from actual Python source code through execution/tests, evidence extraction, current-only diagnosis, history-aware state update, hint selection, teacher 

TraceLearn  |  24 

TraceLearn | FYP Master Design and Implementation Blueprint 

review, and calculated evaluation outputs. The POC exists to make the core idea concrete before full FYP development. 

#### **18.2 POC scope** 

|**Area**|**POC implementation**|
|---|---|
|Misconceptions|3 belief-style classes: range/loop boundary, index-vs-value, print-vs-return; plus<br>NONE/UNCERTAIN.|
|Problems|Approximately 6 related Python problems with visible/hidden/diagnostic tests.|
|Learners|5–15 controlled synthetic/demo trajectories; separate demo and holdout sequences.|
|Execution|Backend subprocess, trusted code only, hard timeout; clearly marked non-secure.|
|Diagnosis|Rule-based weighted evidence baseline. XGBoost training is not required for the tiny synthetic<br>POC.|
|Temporal model|Explicit state machine with strict no-future-leakage rules.|
|Database|SQLite acceptable for POC if SQLAlchemy schema remains PostgreSQL-compatible.|
|Frontend|Monaco-based student submission plus evidence inspector, current-vs-history comparison,<br>learner timeline, teacher/evaluation view.|
|Metrics|Generated from database/exports; no hard-coded accuracy.|



#### **18.3 Why not train XGBoost on only the POC data** 

A few dozen synthetic submissions are sufficient to demonstrate plumbing but not to validate a supervised classifier. Training XGBoost on the same tiny trajectories used to design the rules would produce misleadingly optimistic results. XGBoost enters the main FYP once the selected McMining/public/local labelled data has been mapped, feature-extracted, split, and quality-checked. 

#### **18.4 POC comparison** 

|**Mode**|**Inputs**|**Question answered**|
|---|---|---|
|Current-only|Current execution/tests/static evidence.|What misconception does this<br>submission suggest without<br>history?|
|History-aware|Current diagnosis + prior related evidence/state/successes.|Does history justify changing<br>confidence or learner state?|



#### **18.5 POC success criteria** 

- An isolated failure is not automatically marked Persistent. 

- Cross-problem recurrence can strengthen persistence. 

- Related success can lower confidence and move a learner toward Improving/Resolved. 

- A resolved misconception can recur when strong later evidence appears. 

- Current-only and history-aware outputs can differ for a defensible reason. 

- Every output is traceable to actual execution/test/static/history evidence. 

- No future event or ground-truth label is accessible to diagnosis code. 

- Demo and holdout sequences are separated and evidence weights are frozen before holdout evaluation. 



TraceLearn  |  25 

TraceLearn | FYP Master Design and Implementation Blueprint 

_Figure 11. The POC is the first validation stage within the full FYP roadmap._ 

## **19. Full Development Roadmap** 



_Figure 12. Full FYP development sequence from proposal validation to final deployment/evaluation._ 

**19.1 Phase plan** 



<!-- Start of picture text -->
Period Primary outcome Key work<br>July–August: proposal  Defensible problem, architecture,  Literature/competitor mapping; taxonomy v1; public<br>validation data plan, and POC. dataset verification; POC vertical slice; evaluation<br>design; scope freeze.<br>September–October: FYP-I  Integrated platform foundation. Auth/classrooms; Monaco; server execution;<br>Iteration 1 problem/test authoring; submission logging;<br>runtime/test/static evidence; initial teacher view; 4–6<br>misconceptions.<br>November–December: FYP-I  Complete December prototype. 30–40 problems; 8–12 classes; dataset ingestion;<br>Iteration 2 XGBoost baseline/training if data ready; temporal learner<br>model; evidence decay; five hint levels; teacher<br>correction; initial metrics.<br>January–February: FYP-II pilot  Evaluation-ready system and  40–60 problem bank; stable deployment; annotation<br>preparation recruitment. handbook; pilot instruments; model freeze candidate;<br>reliability/security hardening.<br>March–April: pilot and  Real-student and teacher  Collect pilot trajectories; double-label subset; run<br>evaluation evidence. detector/temporal/hint/teacher experiments; ablations;<br>transfer tests; error analysis.<br>Late April–May: finalization Complete FYP submission. Fixes; reproducibility package; final report; user/admin<br>guides; demo video; final presentation; viva material;<br>backup demo.<br>==<br>19.2 Gating rules<br> Do not delay the end-to-end December prototype for optional deep-learning or multi-language features.<br><!-- End of picture text -->

- Do not train final models before taxonomy/data mappings are frozen enough to support reproducible labels. 

- Do not call a subprocess runner “secure” during the POC. 

- Do not use the local pilot only for training; reserve a true final evaluation subset. 

- If XGBoost does not beat transparent baselines reliably, report that result and keep the more defensible method rather than forcing an ML claim. 

## **20. Risks, Fallbacks, and Scope Control** 



<!-- Start of picture text -->
Risk Why it matters Mitigation / fallback<br>Insufficient real data Temporal/ML claims may rely too heavily on  Use McMining + public sequence datasets for development;<br>synthetic examples. recruit early; preserve a smaller high-quality local pilot;<br>state limitations.<br>Ambiguous  Ground truth becomes unreliable. Belief-style taxonomy; annotation handbook; two<br>misconception labels annotators; allow multi-label/uncertain; report agreement.<br>Class imbalance Accuracy hides minority failure. Macro-F1, per-class metrics, class weights, targeted<br>problem/data selection.<br>—<br><!-- End of picture text -->

TraceLearn  |  26 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**Risk**|**Why it matters**|**Mitigation / fallback**|
|---|---|---|
|History does not help|Core temporal value may be weaker than<br>assumed.|Run current-only vs history-aware comparison early; narrow<br>temporal claims if improvement is only class-specific.|
|XGBoost overfits<br>problem templates|Apparent accuracy does not transfer.|Student-held-out + problem-held-out tests; avoid raw IDs;<br>inspect feature dependence.|
|Execution security|Arbitrary code can harm host.|Trusted-only POC; isolated execution service before public<br>deployment; limits and abuse tests.|
|LLM overreach|Hints leak answers or create unsupported<br>diagnoses.|Structured diagnosis first; constrained hint realization only;<br>output validation; teacher review.|
|Scope creep|Editor/dashboard features consume research<br>time.|Freeze core/supporting/optional hierarchy; POC is not<br>product scope; multi-language remains contingency only.|
|Teacher dashboard<br>decorative|Low educational/engineering contribution.|Tie every view to evidence, uncertainty, and an actionable<br>intervention/review workflow.|



## **21. Three-Person Work Distribution** 

|**Workstream**|**Primary responsibility**|**Shared integration obligations**|
|---|---|---|
|Platform + execution|Frontend, Monaco, backend APIs, classrooms,<br>problem/test management, execution service,<br>database operational layer, deployment.|Problem-bank integration, logging contracts,<br>security tests, end-to-end demo.|
|Diagnosis + learner<br>model|Taxonomy, AST/runtime/test/sequence feature<br>extraction, XGBoost pipeline,<br>confidence/calibration, temporal model, model<br>evaluation.|Annotation review, API/data contracts,<br>evidence visualization, failure analysis.|
|Adaptive support +<br>evaluation|Hint/remediation/transfer policy, teacher<br>decision support, study instruments,<br>annotation protocol, reporting.|Problem bank, pilot recruitment, evaluation<br>scripts, dashboard requirements, final<br>analysis.|



The work should not be split into three disconnected mini-projects. All team members must contribute to problembank design, dataset review, integration testing, documentation, and the final end-to-end demonstration. 

## **22. Deliverables and Acceptance Criteria** 

#### **22.1 Required by December** 

- Working student and teacher platform with browser code editor. 

- Server-side Python execution and visible/hidden/diagnostic test workflow. 

- 30–40 integrated problems and approximately 8–12 supported misconception beliefs. 

- Multi-source evidence extraction with provenance. 

- Rule/statistical baseline and XGBoost integration/training pipeline; trained XGBoost included if mapped labelled data is ready and validated. 

- Persistent temporal learner model with state history and no-future-leakage tests. 

- Five-level adaptive hint/remediation policy. 

- Teacher evidence and correction workflow. 

- Normalized external/public data ingestion and initial local data collection. 

- Initial labelled evaluation and reproducible metrics. 

- Complete classroom → submission → execution → evidence → diagnosis → state → hint → teacher demonstration. 

TraceLearn  |  27 

TraceLearn | FYP Master Design and Implementation Blueprint 

#### **22.2 Required by mid-April / final** 

- 40–60 problem bank and stable deployed system. 

- Completed core diagnostic and learner-model modules with model/config versioning. 

- Pilot data collection and human-labelled evaluation subset. 

- Current diagnosis results and evidence-source ablations. 

- Temporal-state validity and recurrence/improvement/resolution analysis. 

- Hint effectiveness and transfer evaluation. 

- Teacher usefulness/agreement/correction evaluation. 

- Security/reliability testing appropriate to deployment mode. 

- Complete source, dataset documentation, technical report, user/admin guides, demo video, presentation, viva question bank, and offline backup demo. 

## **23. Defense-Ready Positioning** 

|**Question**|**Defensible answer**|
|---|---|
|What is the project?|An end-to-end classroom programming system that converts code attempts into structured<br>misconception evidence, current diagnosis, persistent learner state, adaptive support, and<br>teacher intervention.|
|What is technically new?|The project contribution is the designed and evaluated evidence-fusion + longitudinal learner-<br>state workflow and its intervention/audit integration—not XGBoost, databases, Monaco, or an<br>LLM by themselves.|
|Why not just store history in a<br>database?|The database stores events; the temporal learner model interprets how current and previous<br>evidence should change confidence/state.|
|Why XGBoost?|Evidence is structured/tabular, dataset scale is moderate, nonlinear feature interactions matter,<br>and XGBoost provides a strong practical learned baseline that can be compared against simple<br>rules/statistics.|
|Why not an LLM like McMining?|McMining is a valuable baseline/prior work for misconception mining. TraceLearn’s production<br>reasoning uses execution/test/static evidence, a learned/tabular classifier, longitudinal state,<br>uncertainty, intervention, and human correction.|
|Are there 100 temporal models<br>for 100 students?|No. One shared algorithm/model is applied to each learner; only per-student/per-<br>misconception state and history are individualized in the database.|
|What if you cannot collect<br>1,000 examples?|The plan does not require that. Use labelled McMining data for detector development, public<br>longitudinal datasets for sequence methods, and a smaller high-quality local pilot with an<br>annotated subset for final validity.|
|What does the POC prove?|That the full information path is technically feasible and that history can legitimately change a<br>diagnosis/state in controlled cases; it does not prove real-world effectiveness.|



## **Appendix A. Proposed Database Tables** 

|**Table**|**Primary key / relationship**|**Notes**|
|---|---|---|
|users|user_id|Operational identity; research export uses<br>pseudonymous ID.|
|classrooms|classroom_id; teacher_id FK|Class membership table may be separate.|
|problems|problem_id|Concept/prerequisite tags; version problems if tests<br>change.|
|test_cases|test_id; problem_id FK|type<br>visible/hidden/diagnostic/transfer where<br>∈<br>applicable.|



TraceLearn  |  28 

TraceLearn | FYP Master Design and Implementation Blueprint 

|**Table**|**Primary key / relationship**|**Notes**|
|---|---|---|
|submissions|submission_id; student_id + problem_id|attempt_no and chronological timestamp/order.|
|test_results|result_id; submission_id + test_id|Store category and error/output evidence.|
|evidence_items|evidence_id; submission_id|source, misconception, support/conflict, strength,<br>extractor version.|
|diagnoses|diagnosis_id; submission_id|mode/model_version, probability vector,<br>primary/alternative, confidence.|
|learner_states|(student_id, misconception_id)|Latest state only.|
|learner_state_history|history_id|Append-only transitions and triggers.|
|hint_events|hint_event_id|Level, rationale, misconception/state snapshot.|
|teacher_reviews|review_id; diagnosis_id|Human action and corrected label/state where<br>appropriate.|



## **Appendix B. Initial XGBoost Feature Dictionary** 

|**Feature**|**Type**|**Source**|**Notes**|
|---|---|---|---|
|syntax_error_family|categorical/one-hot|execution|None when syntax succeeds.|
|runtime_error_family|categorical/one-hot|execution|IndexError, TypeError, RecursionError, etc.|
|timeout|binary|execution|Important for non-progress/infinite<br>behavior.|
|visible_pass_rate|numeric|tests|Current submission only.|
|hidden_pass_rate|numeric|tests|Do not show details to student.|
|diag_boundary_fail|binary|diagnostic test|Maps to misconception-sensitive boundary<br>category.|
|diag_return_fail|binary|diagnostic test|Return-vs-print and missing return evidence.|
|has_return|binary|AST|Function-level.|
|print_without_return|binary|AST|Only when function expected to return.|
|range_stop_pattern|categorical|AST|e.g. n, n+1, len(x), len(x)+1.|
|loop_value_as_index|binary|AST|Context-aware detector.|
|suspicious_or_comparison|binary|AST|Pattern such as x == a or b.|
|recursive_arg_changes|binary/numeric|AST|Whether recursion progresses.|
|attempt_number|numeric|current metadata|Can be used carefully; not sufficient for<br>state.|
|problem_concept_tags|multi-hot|problem metadata|Use normalized concept set.|
|code_size_ast_nodes|numeric|AST|Control for extreme structure only; avoid<br>relying on style.|
|NONE label|target class|annotation|Essential to control false positives.|



TraceLearn  |  29 

TraceLearn | FYP Master Design and Implementation Blueprint 

## **Appendix C. Temporal Transition Rules (Initial, to Validate)** 

|**From**|**Condition (illustrative)**|**To**|
|---|---|---|
|No active state|Credible first current evidence above new threshold.|NEW|
|NEW|Repeated support plus cross-problem recurrence / strong independent<br>evidence.|PERSISTENT|
|NEW|Later evidence contradicts/isolated and confidence falls below active<br>threshold.|No active / weak<br>record|
|PERSISTENT|Recent related successes + declining confidence.|IMPROVING|
|IMPROVING|Sustained related/transfer success and no strong supporting evidence.|RESOLVED|
|RESOLVED|Strong later support returns on related context.|RECURRED|
|RECURRED|Corrective success weakens support.|IMPROVING|
|Any active|Low confidence, top hypotheses close, teacher disagreement, or conflicting<br>evidence.|TEACHER REVIEW /<br>UNCERTAIN|



## **Appendix D. External Dataset Register** 

|**Dataset**|**Language**|**Use in TraceLearn**|**Important limitation**|
|---|---|---|---|
|McMining / McMiner|Python|Misconception taxonomy and labelled detector<br>development.|Synthetic benchmark bags; not<br>genuine learning-state<br>trajectories.|
|ProgFeed|Python|Real attempt/autograder/feedback behavior and<br>hint-response analyses.|Misconception ground truth is<br>not TraceLearn-native.|
|CSEDM 2019 / ITAP|Python|Chronological programming knowledge/attempt<br>modelling.|Requires DataShop access;<br>labels are<br>correctness/knowledge-<br>tracing oriented.|
|HELP-DKT|Python|9,119 code submissions with stable<br>student/problem/submission order.|Buggy/correct, not<br>misconception labels.|
|FalconCode|Python|Large external code/assignment/test/skill data.|Access/distribution and exact<br>fields must be verified before<br>use.|
|CodeStream|C/C++/Java|Backup longitudinal attempt histories with verdict<br>traces.|Not Python; external<br>methodological contingency.|
|PROGpedia|Multiple incl. C++|Backup source code + code-property-graph data.|Older/multi-year exercise<br>context; label semantics differ.|
|Project CodeNet|Many; C++<br>dominant|Very large backup code/status corpus.|Online-judge population, not<br>necessarily novice classroom<br>learners; no misconception<br>labels.|



TraceLearn  |  30 

TraceLearn | FYP Master Design and Implementation Blueprint 

## **Appendix E. API / Service Outline** 

|**Endpoint / service**|**Purpose**|
|---|---|
|POST /api/submissions/run|Execute current code without finalizing attempt if product distinguishes<br>Run from Submit.|
|POST /api/submissions|Persist submission, execute tests, extract evidence, generate current<br>diagnosis, update temporal state, select intervention.|
|GET /api/problems/{id}|Problem metadata and student-visible tests/examples.|
|GET /api/students/{id}/learner-state|Authorized learner-state summary.|
|GET /api/students/{id}/timeline|State/evidence history for teacher/research view.|
|POST /api/teacher-reviews|Confirm/reject/correct/mark uncertain.|
|GET /api/classrooms/{id}/analytics|Class misconception trends and intervention queue.|
|POST /api/evaluation/run|Offline/admin evaluation run against frozen dataset/model version.|
|ExecutionService.run(source, tests, limits)|Stable internal boundary independent of subprocess/container/worker<br>implementation.|
|DiagnosisService.predict(evidence)|Current-only rules/XGBoost interface.|
|TemporalService.update(student, misconception,<br>current, history)|State update with causal history only.|



## **Appendix F. Terminology** 

|**Term**|**Meaning in this project**|
|---|---|
|Error|Observed incorrect behavior/syntax/runtime outcome; may or may not reflect a misconception.|
|Misconception|A hypothesized false belief about a programming-language construct or semantic rule.|
|Evidence|A structured observation that supports or conflicts with a misconception hypothesis.|
|Current diagnosis|Prediction about the present submission, primarily produced by rule/XGBoost classifier.|
|Learner state|Persistent longitudinal interpretation for a student–misconception pair.|
|Temporal model|Shared logic that updates learner state from current evidence plus prior causal history.|
|Confidence|Degree of support assigned to a diagnosis/state; not equivalent to certainty or truth.|
|Remediation|Targeted practice/support intended to address the diagnosed concept.|
|Transfer|Performance on a related but non-identical problem used to test generalization of learning.|
|POC|Proposal-stage technical vertical slice; not the full FYP scope.|



## **References and Source Basis** 

Project documents used as the primary scope basis: “Ideas we like” / TraceLearn concept documents, the FAST FYP alignment guide, the updated TraceLearn FYP scope and timeline, the TraceLearn presentation, and the latest POC 

TraceLearn  |  31 

TraceLearn | FYP Master Design and Implementation Blueprint 

implementation plan. Public references below support the dataset/research positioning; exact license/access conditions should be re-checked before final dataset ingestion. 

[1] Al-Hossami, E. & Bunescu, R. (2026). McMining: Automated Discovery of Misconceptions in Student Code. EACL 2026 Short Papers. https://aclanthology.org/2026.eacl-short.10/ 

[2] McMiner repository and benchmark data (MIT). https://github.com/taisazero/mcminer 

[3] ProgFeed public dataset repository (CC BY 4.0). https://github.com/umass-ml4ed/progFeed-dataset-public 

[4] CSEDM 2019 Data Challenge / ITAP dataset documentation. https://github.com/thomaswp/CSEDM2019-Data- <u>Challenge</u> 

[5] HELP-DKT repository and dataset. https://github.com/liangyubuaa/HELP-DKT 

[6] FalconCode: A Multiyear Dataset of Python Code Samples from an Introductory Computer Science Course. <u>https://doi.org/10.1145/3545945.3569822</u> 

- [7] Project CodeNet repository. https://github.com/IBM/Project_CodeNet 

[8] CodeStream dataset article / Mendeley Data. https://doi.org/10.1016/j.dib.2026.112843 

[9] PROGpedia dataset. https://zenodo.org/records/7449056 

[10] Monaco Editor. https://github.com/microsoft/monaco-editor 

- [11] XGBoost documentation. https://xgboost.readthedocs.io/ 

TraceLearn  |  32 

