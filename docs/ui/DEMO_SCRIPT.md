# TraceLearn POC — Demo Script

Use this script during a live walkthrough. Follow the steps in order.
Estimated time: **6–8 minutes**.

**Start URL:** http://localhost:5173/

**Before you begin**
1. Run `npm run dev` if the app is not already open.
2. Start on the **Student** side (default).
3. Make sure the student picker shows **Ali** selected.

---

## Opening line (15 seconds)

> “TraceLearn helps programming students learn from repeated mistakes — not just one wrong answer. It notices the type of mistake, tracks it over time, gives progressive hints, and shows the teacher where the class needs attention.”

---

## Part 1 — Student: Focus and practice (≈2 min)

### 1. Student Dashboard (Ali)

**Click:** Student → Dashboard (or refresh if already there)

**Show**
- Welcome message for Ali
- Focus Area card: **Loop Boundaries** / Needs more practice
- Recommended problems
- Simple progress counts

**Say**
> “Ali’s dashboard already tells him what to focus on. TraceLearn isn’t dumping a full gradebook on him — it’s pointing to one clear next step: loop boundaries.”

**Click:** Start Practice *(or open Practice from the sidebar)*

---

### 2. Practice list

**Show**
- Problems with topic, difficulty, and status
- Ali’s loop problems marked Needs Practice / Recommended

**Say**
> “This is the practice queue. Ali’s recommended work is concentrated on loops because that’s where the repeated issue is.”

**Click:** **Count from 1 to N**

---

### 3. Problem page

**Show**
- Problem statement
- Hardcoded C++ code editor with the buggy loop (`i < n`)

**Say**
> “This is the problem screen. In the real system this would compile and run. In the POC, Submit uses a prepared incorrect attempt so we can focus on the learning flow.”

**Click:** **Run / Submit**

---

### 4. Result page — first hint

**Show**
- “Not quite yet”
- Expected vs your output (`1 2 3 4 5` vs `1 2 3 4`)
- “What TraceLearn noticed”
- Hint Level 1 — Guiding Question
- “Why this matters” (patterns across attempts)

**Say**
> “TraceLearn doesn’t dump the full answer. It starts with a guiding question. And it already notes that this isn’t a one-off — similar mistakes showed up before.”

---

### 5. Progressive hints (all 5 levels)

**Click:** **Next Hint** repeatedly through levels 2 → 5

| Level | What to point at | What to say |
|------:|------------------|-------------|
| 1 | Guiding Question | “Ask the student to think.” |
| 2 | Concept Reminder | “Remind the relevant idea.” |
| 3 | Code-Region Focus | “Highlight the loop condition.” |
| 4 | Partial Logical Correction | “More direct, still no full fix.” |
| 5 | Full Teaching Explanation | “Only now explain `i < n` vs including N.” |

**Say**
> “Support gets more direct only when the student asks for more help. That’s intentional — TraceLearn is structured tutoring, not a chatbot that immediately reveals the answer.”

**Optional click:** Try Again *(returns to the problem)* then come back via Progress

---

### 6. Student Progress (Ali)

**Click:** Progress *(sidebar)*

**Show**
- Loop Boundaries timeline: Attempt 1 → 2 → 3 → Current / **Persistent**
- Variables: Correct / no continuing issue

**Say**
> “This is the key idea: TraceLearn tracks patterns over time. One mistake isn’t automatically a misconception. Ali’s loop issue kept repeating, so it’s treated as persistent. Variables did not.”

---

## Part 2 — Contrast students (≈1.5 min)

Stay on the Student side. Use the **Ali / Sara / Hamza** pills at the top.

### 7. Switch to Sara

**Click:** **Sara**

**Show on Dashboard / Progress**
- Focus: **Recursion Base Case**
- Status: **Improving**
- Timeline: mistakes earlier, recent attempts correct

**Say**
> “Sara also made mistakes — but recent attempts are correct. TraceLearn updates her status to Improving. Students aren’t permanently labeled from one bad attempt.”

### 8. Switch to Hamza

**Click:** **Hamza**

**Show on Dashboard / Progress**
- Focus: **Array Indexing**
- Status: **Isolated** / no persistent misconception
- One incorrect attempt, then correct

**Say**
> “Hamza made a mistake once and corrected it. TraceLearn treats that as isolated — not a continuing misunderstanding. That distinction matters for both feedback and teacher attention.”

**Click:** **Ali** again *(reset for teacher story continuity)*

---

## Part 3 — Teacher: Class → area → student → evidence (≈3 min)

### 9. Switch to Teacher

**Click:** sidebar **Teacher**

**Land on:** Class Overview

**Show**
- Course: CS101 — Introduction to Programming
- Teacher: Dr. Sarah Ahmed
- Summary cards: 3 students, 18 problems completed, 2 areas needing attention
- Misconception bar chart

**Say**
> “On the teacher side, the first question is class-level: where should I look? Loop Boundaries and Recursion Base Cases stand out. Array Indexing does not show as persistent.”

**Click:** the **Loop Boundaries** bar *(or Open details → Loop Boundaries)*

---

### 10. Misconceptions → Loop Boundaries

**Show**
- 1 student currently needs attention
- **Ali** — 3 related attempts, Persistent, last attempt incorrect
- Suggested: assign focused practice

**Say**
> “From the class chart we drill into one area. TraceLearn surfaces who is affected and what action is suggested — without burying the teacher in model details.”

**Click:** **Open Ali**

---

### 11. Teacher Student Details (Ali)

**Show**
- Current Areas: Loop Boundaries — Persistent — High priority
- Recent Activity table (incorrect loop problems + correct Variables)
- Timeline: First → Second → Third attempt → Current needs practice
- Suggested Action at the bottom

**Say**
> “This is the teacher’s evidence view. Same story as Ali’s student Progress page — repeated loop-boundary mistakes across problems.”

**Click:** **Count from 1 to N** *(in Recent Activity)*

---

### 12. Submission detail

**Show**
- Student code with the highlighted `for (int i = 1; i < n; i++)` line
- Expected vs received output
- TraceLearn’s finding: possible loop-boundary misunderstanding
- Evidence bullets
- Status: Persistent

**Say**
> “The teacher can go Class → Area → Student → Submission and immediately see why this was flagged: same mistake type before, related struggle, current attempt still wrong.”

**Click:** **Back to Ali**

---

### 13. Suggested teacher action

**On Ali’s detail page**

**Click:** **View Recommended Problems**  
**Then click:** **Mark as Reviewed**

**Show**
- Recommended loop problems appear
- Banner updates to “Marked as reviewed”

**Say**
> “In the full product this would drive assignments. In the POC, the action is intentionally simple — enough to show the teacher workflow without building a full LMS.”

---

## Part 4 — Classroom assign flow (≈1.5 min)

### 14. Teacher Classroom

**Click:** Classroom

**Show**
- Roster with submission counts
- Recent class submissions **with dates/times**
- Assign Problem button

**Say**
> “Classroom is where the teacher manages the class workload — not just diagnostics.”

**Click:** **Assign Problem**

### 15. Assign from dataset or create

**Show**
- Toggle: Choose from dataset / Create new problem
- Create mode: title, description, starter code, test cases
- Student checkboxes + due date

**Click:** Assign to class

**Say**
> “After assign, that problem appears on the student Practice list for the selected students.”

### 16. Confirm on Student side

**Click:** Student → Practice

**Show**
- “Assigned by teacher” section with the new problem and due date

**Say**
> “Same assignment, visible immediately on the student side — still frontend-only session state for the POC.”

---

## Closing line (20 seconds)

> “So to summarize: a student makes mistakes, TraceLearn notices the type, tracks whether it repeats or improves, gives progressive help, and lets the teacher drill from the whole class down to the exact submission evidence. That’s the TraceLearn story.”

---

## Quick backup paths (if someone asks mid-demo)

| Question | Go here |
|----------|---------|
| “What if the student improves?” | Student → **Sara** → Progress |
| “What if it was just one mistake?” | Student → **Hamza** → Progress |
| “How do hints escalate?” | Student → Problem → Submit → click **Next Hint** ×5 |
| “What does the teacher see first?” | Teacher → Class Overview chart |
| “Why is Ali flagged?” | Teacher → Ali → submission **Count from 1 to N** |
| “Where is all the data?” | Mention `src/data/hardcoded.ts` — frontend-only POC |

---

## Demo checklist (features covered)

- [ ] Student / Teacher role switch
- [ ] Student dashboard focus area
- [ ] Recommended practice
- [ ] Practice problem list
- [ ] Problem editor + Submit
- [ ] Result comparison
- [ ] Five hint levels
- [ ] Student progress timeline
- [ ] Ali / Sara / Hamza contrast
- [ ] Teacher class overview + chart
- [ ] Misconception drill-down
- [ ] Student details + timeline
- [ ] Submission evidence + highlight
- [ ] View recommended problems
- [ ] Mark as reviewed

---

## Optional shorter version (3 minutes)

1. Ali Dashboard → Practice → Count from 1 to N → Submit  
2. Next Hint through level 3  
3. Progress (Persistent)  
4. Switch Sara (Improving) → Hamza (Isolated)  
5. Teacher Overview chart → Loop Boundaries → Ali → one submission → Mark as Reviewed  
6. Close with the summary line
