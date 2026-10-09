# TraceLearn POC UI Master Prompt for Cursor

## Purpose

Build a **simple frontend-only POC** for TraceLearn that shows how the
system will work for both students and teachers.

This is **not the full TraceLearn system**. Do not build a backend,
database, real code execution, real machine learning, authentication, or
complex infrastructure.

Everything should be **hardcoded** so the focus stays on the user flow
and the idea.

The main story to show is:

**A student makes mistakes → TraceLearn notices the type of mistake →
the mistake is tracked over time → the student receives an appropriate
hint → the teacher can see the student's progress and the common
mistakes in the class.**

Keep the POC simple. It should feel believable and polished, but do not
try to build every feature from the full project.

------------------------------------------------------------------------

# 1. Overall Style

Use a **hybrid visual style**:

-   Teacher side: premium, clean SaaS dashboard
-   Student side: slightly friendlier and more approachable
-   Modern and spacious
-   Professional enough for a university project presentation
-   Simple navigation
-   Clear cards, tables, charts, progress indicators, and status labels
-   Avoid excessive animations
-   Avoid unnecessary decorative elements

Do not make it look like a generic admin dashboard.

Use a consistent TraceLearn identity throughout the application.

------------------------------------------------------------------------

# 2. Technology

Build the frontend in **C++-aligned project context**, but keep the
actual POC implementation practical for the chosen Cursor frontend
setup.

Do not add unnecessary technical complexity.

All information can be stored in simple hardcoded objects/data
structures.

There is no need for:

-   Database
-   API
-   Authentication
-   Real compiler
-   Real machine learning
-   Real student accounts
-   Real-time communication

The application should behave as though these things exist by using
hardcoded data and simple interactions.

------------------------------------------------------------------------

# 3. Application Structure

Create **one application** with a simple role switch.

At the top or in the sidebar, provide:

**TraceLearn**

`Student | Teacher`

This should let the presenter instantly switch between the two sides.

Do not create two completely separate applications.

------------------------------------------------------------------------

# 4. Small Hardcoded Class

Keep the class small because this is only a POC.

Use:

**Course:** CS101 --- Introduction to Programming\
**Teacher:** Dr. Sarah Ahmed\
**Students:** 3\
**Problems:** 8

Use three fictional students:

### Ali

Main issue: - Repeatedly struggles with Python `range()` boundaries.

Current state: - Persistent

### Sara

Main issue: - Had difficulty understanding recursion base cases. - Is
now improving after practice.

Current state: - Improving

### Hamza

Main issue: - Has made a few indexing mistakes. - These mistakes were
isolated and are not treated as a continuing misconception.

Current state: - No persistent misconception

Keep these three students consistent everywhere in the application.

------------------------------------------------------------------------

# 5. Student Side

The student experience should contain only the screens needed to explain
the main idea.

Navigation:

-   Dashboard
-   Practice
-   Problem
-   Result
-   Progress

------------------------------------------------------------------------

## Student Dashboard

Create a friendly dashboard showing:

### Welcome

**Good afternoon, Ali**

Short message:

"Here is what you should focus on next."

### Focus Area

A prominent card:

**Loop Boundaries**

Status:

**Needs more practice**

Small explanation:

"You have made this mistake more than once. A few focused problems can
help you get more comfortable with it."

### Recommended Practice

Show 2--3 recommended problems.

Example:

**Counting from 1 to N** - Beginner - Loops - Recommended

**Sum of Numbers in a Range** - Beginner - Loops - Recommended

**Print Even Numbers** - Beginner - Loops - Recommended

Add a simple **Start Practice** button.

### Progress

Show a simple visual:

-   Concepts improving
-   Concepts needing practice
-   Problems solved

Do not overload the dashboard with statistics.

------------------------------------------------------------------------

# 6. Student Practice Page

Show a small problem list.

Each problem should have:

-   Problem title
-   Difficulty
-   Topic
-   Status

Example:

  Problem             Topic       Difficulty   Status
  ------------------- ----------- ------------ ----------------
  Count from 1 to N   Loops       Easy         Needs Practice
  Sum a Range         Loops       Easy         Recommended
  Factorial           Recursion   Medium       Improving
  Find Maximum        Arrays      Easy         Completed

Clicking a problem should open the Problem page.

------------------------------------------------------------------------

# 7. Student Problem Page

This is one of the most important screens.

Show:

### Problem

**Count from 1 to N**

"Write a program that prints all numbers from 1 to N."

### Code Area

Show a simple C++ code editor-style area.

Use hardcoded code.

Example:

``` cpp
int n;
cin >> n;

for (int i = 1; i < n; i++) {
    cout << i << endl;
}
```

Below it:

**Run / Submit**

The button does not actually run code.

Instead, clicking it should move to the Result page using the hardcoded
result.

------------------------------------------------------------------------

# 8. Student Result Page

This is the central part of the student flow.

Show:

### Result

**Not quite yet**

Expected: `1 2 3 4 5`

Your output: `1 2 3 4`

Then show:

### What TraceLearn noticed

**You may be stopping the loop one step too early.**

Do not immediately give the full answer.

Show the first level of help:

### Hint

**Guiding Question**

> If the loop should include N, what condition should be true when i
> reaches N?

Button:

**Try Again**

Also show:

**Why this matters**

"Similar mistakes have appeared in more than one problem."

This is how the POC should show that TraceLearn is not only looking at
the current answer. It is also considering previous attempts.

------------------------------------------------------------------------

# 9. Five Hint Levels

The UI should make it possible to show the five levels of help.

Do not make this complicated.

A simple **Next Hint** interaction is enough.

The levels are:

### Level 1 --- Guiding Question

Ask a question that helps the student think.

Example:

"If the loop should include N, what should happen when i reaches N?"

### Level 2 --- Concept Reminder

Remind the student of the relevant idea.

Example:

"Remember that the condition in a loop determines when the loop stops."

### Level 3 --- Code-Region Focus

Point toward the relevant part of the student's code.

Example:

"Look closely at the condition in your `for` loop."

Highlight the relevant line.

### Level 4 --- Partial Logical Correction

Give more direct guidance without writing the complete answer.

Example:

"Your loop stops before i becomes equal to N. The condition needs to
allow that final value."

### Level 5 --- Full Teaching Explanation

Explain the issue clearly.

Example:

"Your loop uses `i < n`, so when i becomes equal to n, the loop stops.
If the problem requires N to be printed, the condition needs to include
that value."

The UI should visibly show that help becomes more direct as the student
asks for more help.

Do not make the hints sound like an AI chatbot.

They should feel like structured learning support.

------------------------------------------------------------------------

# 10. Student Progress Page

Show a simple timeline of the student's progress.

Example for Ali:

### Your Progress

**Loop Boundaries**

-   Attempt 1 --- Mistake made
-   Attempt 2 --- Same mistake
-   Attempt 3 --- Same mistake
-   Current --- Needs focused practice

Status:

**Persistent**

Add a small explanation:

"This issue has appeared across multiple attempts, so TraceLearn is
treating it as something that needs more practice."

Also show another concept:

**Variables** - Correct - No continuing issue

This page should visually communicate that TraceLearn tracks patterns
over time.

------------------------------------------------------------------------

# 11. Sara's Student View

Make Sara's data show a different story.

Sara has a recursion issue.

Show:

**Recursion Base Case**

Previous: - Mistake made - Mistake made

Recent: - Correct - Correct

Status:

**Improving**

Message:

"You are getting better at this. Keep practicing with similar problems."

This demonstrates that TraceLearn does not permanently label a student
based on one mistake.

------------------------------------------------------------------------

# 12. Hamza's Student View

Hamza should show an isolated mistake.

Example:

**Array Indexing**

-   One incorrect attempt
-   Next attempt correct

Status:

**No persistent misconception**

Message:

"This looks like an isolated mistake rather than a continuing problem."

This is important because it shows the difference between:

**one mistake**

and

**a repeated misunderstanding.**

------------------------------------------------------------------------

# 13. Teacher Side

Teacher navigation:

-   Class Overview
-   Misconceptions
-   Students
-   Student Details

Keep it small.

Do not create a large teacher management system.

------------------------------------------------------------------------

# 14. Teacher Class Overview

This should be the main teacher screen.

Header:

**CS101 --- Introduction to Programming**

Subtext:

**Dr. Sarah Ahmed**

Show three simple summary cards:

### Students

3

### Problems Completed

18

### Areas Needing Attention

2

Then show:

## Class Misconceptions

Use a simple bar chart.

Show the total number of students currently showing each type of issue.

Example:

-   Loop Boundaries --- 1
-   Recursion Base Cases --- 1
-   Array Indexing --- 0 persistent
-   Conditional Logic --- 0

The chart should make it immediately obvious which areas deserve
attention.

Do not make the chart overly complicated.

------------------------------------------------------------------------

# 15. Teacher Misconceptions Page

Show a simple list/table:

  Area                     Students Status
  ---------------------- ---------- ------------
  Loop Boundaries                 1 Persistent
  Recursion Base Cases            1 Improving
  Array Indexing                  0 Isolated

Clicking **Loop Boundaries** should show:

### Loop Boundaries

**1 student currently needs attention**

Student:

**Ali**

Show:

-   Number of related attempts
-   Current status
-   Recent result
-   Recommended action

Example:

**Ali** - 3 related attempts - Persistent - Last attempt: incorrect -
Suggested: assign focused practice

Do not show complicated model details.

------------------------------------------------------------------------

# 16. Teacher Students Page

Show the three students as simple rows/cards.

### Ali

**Needs attention** - Loop Boundaries - Persistent

### Sara

**Improving** - Recursion Base Cases

### Hamza

**Doing well** - No continuing misconception

Clicking a student opens Student Details.

------------------------------------------------------------------------

# 17. Teacher Student Details

This page should be one of the strongest teacher screens.

Header:

**Ali**

Then show:

### Current Areas

**Loop Boundaries** - Persistent - High priority

### Recent Activity

  Problem              Result      Area
  -------------------- ----------- -----------------
  Count from 1 to N    Incorrect   Loop Boundaries
  Sum a Range          Incorrect   Loop Boundaries
  Print Even Numbers   Incorrect   Loop Boundaries
  Variables            Correct     ---

Then show:

### What happened over time

A simple timeline:

**First attempt** Mistake appeared

↓

**Second attempt** Same issue appeared again

↓

**Third attempt** Same issue appeared again

↓

**Current** Needs focused practice

This should clearly show the idea of tracking a student's learning
pattern over time.

------------------------------------------------------------------------

# 18. Teacher Submission Detail

When the teacher clicks one of Ali's incorrect submissions, show:

### Problem

Count from 1 to N

### Student Code

Show the hardcoded code.

Highlight the relevant line:

``` cpp
for (int i = 1; i < n; i++)
```

### Result

Expected: `1 2 3 4 5`

Received: `1 2 3 4`

### TraceLearn's Finding

**Possible loop-boundary misunderstanding**

### Evidence

Keep this simple:

-   Same type of mistake appeared in previous attempts
-   Student also struggled with a related problem
-   Current attempt is incorrect

Then show:

**Status: Persistent**

The teacher should be able to understand why TraceLearn is showing this
issue.

------------------------------------------------------------------------

# 19. Simple Teacher Action

At the bottom of the student detail page:

**Suggested Action**

"Give Ali a few focused problems on loop boundaries."

Buttons:

**View Recommended Problems**

**Mark as Reviewed**

The buttons can simply change the UI state.

There does not need to be a real assignment system.

------------------------------------------------------------------------

# 20. Main Presentation Flow

The application should make this flow extremely easy to demonstrate:

### Student

1.  Open Student Dashboard
2.  Show that TraceLearn identifies a focus area
3.  Open recommended practice
4.  Open a problem
5.  Submit the hardcoded incorrect solution
6.  Show the result
7.  Show the first hint
8.  Click through the five hint levels
9.  Open Progress
10. Show that the issue has appeared more than once

### Teacher

11. Switch to Teacher
12. Open Class Overview
13. Show the misconception chart
14. Open Loop Boundaries
15. Open Ali
16. Show his attempts over time
17. Open the submission
18. Show the evidence behind the finding
19. Show the suggested action

The whole POC should communicate this story without requiring
explanation of complicated technical details.

------------------------------------------------------------------------

# 21. Important Product Behavior

The UI should communicate these ideas clearly:

### A mistake is not automatically a misconception

One wrong answer can simply be an isolated mistake.

### Repeated mistakes matter

When a similar issue appears across attempts, TraceLearn can treat it as
something that needs attention.

### Improvement matters

If a student starts getting similar problems correct, their status can
change to improving.

### Support changes based on the situation

The student does not immediately receive the full answer.

Help starts small and becomes more direct.

### Teachers can see the reason

The teacher should be able to go from:

**Class → Area → Student → Submission**

and understand what happened.

------------------------------------------------------------------------

# 22. Keep the UI Small

Do **not** build:

-   Full authentication
-   Real database
-   Real backend
-   Real compiler
-   Real code execution
-   Real machine learning
-   Large problem management system
-   Full assignment management
-   Messaging system
-   Complex teacher settings
-   Complex analytics
-   Large student profiles
-   Notification systems
-   Payment/subscription features
-   AI chat interface

This is only a POC showing **how TraceLearn will work**.

------------------------------------------------------------------------

# 23. Hardcoded Data

Keep all data in one simple place so it is easy to change later.

Use a small set of hardcoded records for:

-   Students
-   Problems
-   Attempts
-   Misconceptions
-   Hint levels
-   Student statuses
-   Teacher class statistics

Make sure the same data is used across all screens.

For example, if Ali has a persistent loop-boundary issue on the Student
side, the Teacher side must show the same issue.

------------------------------------------------------------------------

# 24. Interaction Requirements

The following interactions must work:

-   Student/Teacher role switch
-   Dashboard navigation
-   Open problem
-   Submit problem
-   Show result
-   Next Hint
-   View progress
-   Open misconception
-   Open student
-   Open submission
-   Mark as reviewed
-   View recommended problems

Use simple state changes and navigation.

No interaction should require a backend.

------------------------------------------------------------------------

# 25. Visual Priorities

Prioritize these five things:

1.  **Clear student learning flow**
2.  **Visible tracking over time**
3.  **Progressive hints**
4.  **Teacher class-level misconception view**
5.  **Teacher drill-down into a student's evidence**

Everything else is secondary.

------------------------------------------------------------------------

# 26. Final Quality Rule

The POC should feel like a small but believable product.

Do not try to impress through the number of screens.

Instead, make the few important screens work together smoothly.

A person seeing the application should understand within a few minutes:

**"TraceLearn notices repeated mistakes, tracks whether they continue or
improve, gives the student appropriate help, and lets the teacher see
which students need attention and why."**
