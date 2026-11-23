# Confirmatory set (Gate 5)

The one set the project may call independent. It is scored **once**, by the frozen system, at
Gate 6 (`docs/EVAL_PROTOCOL.md` section 1). Owner: Umaima (task U5). Reviewer: Eman.

**Status, 22 November 2026:** candidate problems listed. Nothing is selected, sampled, labelled
or frozen yet.

## What a label here means

A label names the error in the program, judged from the task, the failing test and the code. It
is not evidence of what the student believed.

## Step 1: candidate problems (done)

`candidates_v1.csv` is written by `scripts/g5_candidates.py` (seed 20261122). It lists all 70
Project CodeNet problems whose submissions are in the local raw copy. Every CodeStream and
PROGPedia problem the project normalized (62) is already used, so CodeNet is the only source of
fresh problems.

A problem is **eligible** when all of these hold. The rule was fixed before any program was opened.

1. Not used anywhere. Excluded by id: the label and lane files, every split file, the reference
   solutions in `scripts/build_codenet_pool.py`, and any cache or oracle-test file name. That
   removes the 11 CodeNet problems the project trained or tested on.
2. An English statement (at least 90% of its letters ASCII).
3. At least one sample in the statement.
4. At least 100 C++ submissions in the raw folder.

Result: **31 eligible, 39 not.** 11 are used, 20 have a Japanese statement, 2 have no statement
and 6 have fewer than 100 C++ submissions. The `reason` column gives each one.

## Step 2: choose the problems (Umaima, with the team)

Work down `candidates_v1.csv` in `rank` order. Do not jump ahead. Take a problem unless one of
two things is true, and write which in `selection_log.csv` (rank, problem id, taken or skipped,
reason, who, date):

- **Not course-level.** An introductory C++ student could not attempt it, judged from the
  statement alone. The `atcoder_score` column helps; AOJ problems have none.
- **No reference.** You cannot write a reference solution and an input generator that reproduce
  every sample output, as `scripts/build_codenet_pool.py` does for its problems.

Stop when the taken problems reach the agreed size. The plan suggests about 150 failing programs
over at least 8 problems, but the supervisor fixes the number.

**Expect a shortfall.** Many eligible problems are contest problems well above an introductory
course: AtCoder scores of 500 to 900, and ICPC problems from AOJ. If fewer than 8 survive step 2,
that is a finding to take to the supervisor, not a reason to relax the rule. The way out is more
raw data. All 3,999 CodeNet statements are local, but submissions are only for these 70, so the
CodeNet archive's other problems would have to be copied in and listed by this same script.

## Steps 3 to 6: sample, label, freeze (later)

These follow task U5 in the work plan.

- **Sample.** Draw failing submissions at random with a fixed seed, an equal number per problem.
  "Failing" means failing a derived test.
- **Label.** All three raters label every item alone, with no model output anywhere. Then
  adjudicate and report Fleiss kappa.
- **Freeze.** Commit `splits/confirmatory_v1.csv` and the labels, record both hashes in the
  protocol, and tag the commit.

Until that freeze commit exists:

- no feature extraction, run record, prediction or rule is computed for a sampled program;
- nobody opens a sampled program except as a rater.

## Raw code

The submissions stay outside the repository. They are at
`G:/TraceLearn/Datasets_RAW/Project_CodeNet/Project_CodeNet/data/<problem>/C++/`. Record the
archive hash when the sample is drawn.

## Access log

`access_log.csv` lists every time anyone reads anything from these problems. Add a line before
you open something.
