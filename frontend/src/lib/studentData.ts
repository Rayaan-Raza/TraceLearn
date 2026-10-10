import { useMemo } from 'react'
import { api } from '../api/client'
import type { Assignment, LearnerProfile, ProblemSummary, SubmissionSummary, TimelineEntry } from '../api/types'
import type { ProgressEvent } from '../components/Timeline'
import {
  bySeverity,
  isRealMisconception,
  misconceptionLabel,
  shortDate,
  formatDate,
  stateToStatus,
  statusExplanation,
  type ChartPoint,
  type ProblemStatus,
  type UiStatus,
} from './labels'
import { useApi } from './useApi'

export interface StudentBundle {
  profile: LearnerProfile
  submissions: SubmissionSummary[] // newest first
  timeline: TimelineEntry[] // oldest first
}

export function useStudentBundle(studentId: number | null) {
  return useApi<StudentBundle | null>(async () => {
    if (studentId == null) return null
    const [profile, submissions, timeline] = await Promise.all([
      api.profile(studentId),
      api.studentSubmissions(studentId),
      api.timeline(studentId),
    ])
    return { profile, submissions, timeline }
  }, [studentId])
}

export interface Derived {
  focus: { misconceptionId: string; label: string; status: UiStatus; explanation: string } | null
  counts: { improving: number; needingPractice: number; solved: number }
  stateCounts: ChartPoint[]
  mistakeTimeline: ChartPoint[]
  solvedProblemIds: Set<string>
  attemptedProblemIds: Set<string>
}

export function derive(bundle: StudentBundle | null): Derived {
  const states = bundle ? bySeverity(bundle.profile.learner_states) : []
  const subs = bundle?.submissions ?? []
  const solved = new Set(subs.filter((s) => s.passed).map((s) => s.problem_id))
  const attempted = new Set(subs.map((s) => s.problem_id))
  const statuses = states.map((s) => stateToStatus(s.state))

  const top = states[0]
  const focus =
    top && stateToStatus(top.state) !== 'none'
      ? {
          misconceptionId: top.misconception_id,
          label: misconceptionLabel(top.misconception_id),
          status: stateToStatus(top.state),
          explanation: statusExplanation(stateToStatus(top.state)),
        }
      : null

  const count = (s: UiStatus) => statuses.filter((x) => x === s).length
  const stateCounts: ChartPoint[] = [
    { label: 'Persistent', count: count('persistent'), tone: 'persistent' },
    { label: 'Improving', count: count('improving'), tone: 'improving' },
    { label: 'Isolated', count: count('isolated'), tone: 'isolated' },
    { label: 'Needs review', count: count('review'), tone: 'review' },
    { label: 'Solved', count: solved.size, tone: 'none' },
  ]

  // Cumulative failed attempts per day (oldest -> newest), last 8 days with activity.
  const byDay = new Map<string, number>()
  for (const s of [...subs].reverse()) {
    const day = shortDate(s.submitted_at)
    byDay.set(day, (byDay.get(day) ?? 0) + (s.passed ? 0 : 1))
  }
  let running = 0
  const mistakeTimeline = [...byDay.entries()].map(([label, n]) => ({ label, count: (running += n) })).slice(-8)

  return {
    focus,
    counts: { improving: count('improving'), needingPractice: count('persistent') + count('review'), solved: solved.size },
    stateCounts,
    mistakeTimeline: mistakeTimeline.length ? mistakeTimeline : [{ label: '—', count: 0 }],
    solvedProblemIds: solved,
    attemptedProblemIds: attempted,
  }
}

export function problemStatus(problemId: string, d: Derived, assignedIds: Set<string>, recommendedIds: Set<string>): ProblemStatus {
  if (d.solvedProblemIds.has(problemId)) return 'completed'
  if (d.attemptedProblemIds.has(problemId)) return 'needs-practice'
  if (assignedIds.has(problemId) || recommendedIds.has(problemId)) return 'recommended'
  return 'not-started'
}

/** Unsolved problems to try next: active assignments first, then problems sharing a topic with recent mistakes. */
export function recommend(problems: ProblemSummary[], bundle: StudentBundle | null, d: Derived, assignments: Assignment[]): ProblemSummary[] {
  const failedTopics = new Set(
    (bundle?.submissions ?? [])
      .filter((s) => !s.passed)
      .map((s) => problems.find((p) => p.id === s.problem_id)?.topic)
      .filter(Boolean) as string[],
  )
  const active = new Set(assignments.filter((a) => a.state === 'active').map((a) => a.problem_id))
  const score = (p: ProblemSummary) => (active.has(p.id) ? 2 : 0) + (failedTopics.has(p.topic) ? 1 : 0)
  return problems
    .filter((p) => !d.solvedProblemIds.has(p.id))
    .sort((a, b) => score(b) - score(a))
    .slice(0, 3)
}

/** Per-misconception learning story built from real learner-state transitions. */
export function conceptStories(bundle: StudentBundle | null, problemTitle: (id: string) => string) {
  if (!bundle) return []
  return bySeverity(bundle.profile.learner_states).map((st) => {
    const events: ProgressEvent[] = []
    for (const entry of bundle.timeline) {
      const t = entry.state_transitions.find((x) => x.misconception_id === st.misconception_id)
      const diagnosed = entry.primary_diagnosis === st.misconception_id
      if (!t && !diagnosed) continue
      const status = stateToStatus(t?.new_state ?? 'NEW')
      const good = status === 'improving' || status === 'none'
      events.push({
        label: `${problemTitle(entry.problem_id)} · attempt ${entry.attempt_number}`,
        detail: t
          ? t.old_state === t.new_state
            ? `Still ${t.new_state.toLowerCase().replace(/_/g, ' ')} (confidence ${Math.round(t.new_confidence * 100)}%)`
            : `${t.old_state.toLowerCase().replace(/_/g, ' ')} → ${t.new_state.toLowerCase().replace(/_/g, ' ')}`
          : 'Mistake seen',
        tone: good ? 'positive' : 'negative',
        date: formatDate(entry.submitted_at),
      })
    }
    const status = stateToStatus(st.state)
    events.push({ label: 'Current', detail: statusExplanation(status), tone: 'current', date: formatDate(st.updated_at) })
    return { misconceptionId: st.misconception_id, concept: misconceptionLabel(st.misconception_id), status, events }
  })
}

export function useProblemTitles(problems: ProblemSummary[] | null) {
  return useMemo(() => {
    const map = new Map((problems ?? []).map((p) => [p.id, p.title]))
    return (id: string) => map.get(id) ?? id
  }, [problems])
}

export function submissionArea(s: SubmissionSummary): string | null {
  return isRealMisconception(s.primary_misconception) ? misconceptionLabel(s.primary_misconception) : null
}
