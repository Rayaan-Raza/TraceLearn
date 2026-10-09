/** Human-facing names and status mapping for backend misconception data. */

export type UiStatus = 'persistent' | 'improving' | 'isolated' | 'none' | 'review'
export type ProblemStatus = 'needs-practice' | 'recommended' | 'improving' | 'completed' | 'not-started'

export interface ChartPoint {
  label: string
  count: number
  tone?: string
}

const MISCONCEPTION_LABELS: Record<string, string> = {
  M01_LOOP_BOUNDARY: 'Loop Boundaries',
  M02_INDEX_VALUE: 'Index vs Value',
  M03_MISSING_RETURN: 'Missing Return',
  CPP_LOOP_BOUNDARY: 'Loop Boundaries',
  CPP_OFF_BY_ONE: 'Off-by-one Indexing',
  CPP_ARRAY_BOUNDS: 'Array Bounds',
  CPP_UNINITIALIZED_VAR: 'Uninitialized Variables',
  CPP_INT_OVERFLOW: 'Integer Overflow',
  CPP_MISSING_BASE_CASE: 'Recursion Base Case',
  CPP_ASSIGN_VS_COMPARE: 'Assignment vs Comparison',
  CPP_WRONG_LOOP_DIR: 'Loop Direction',
  NO_MISCONCEPTION: 'No misconception',
  UNCERTAIN: 'Uncertain',
  GENERIC: 'General',
}

export const KNOWN_MISCONCEPTIONS = Object.keys(MISCONCEPTION_LABELS).filter(
  (k) => !['NO_MISCONCEPTION', 'UNCERTAIN', 'GENERIC'].includes(k),
)

export function misconceptionLabel(id: string | null | undefined): string {
  if (!id) return '—'
  return MISCONCEPTION_LABELS[id] ?? id.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())
}

export function isRealMisconception(id: string | null | undefined): boolean {
  return !!id && id !== 'NO_MISCONCEPTION' && id !== 'UNCERTAIN'
}

/** Learner-state machine value -> UI status bucket. */
export function stateToStatus(state: string | null | undefined): UiStatus {
  switch (state) {
    case 'PERSISTENT':
    case 'RECURRED':
      return 'persistent'
    case 'IMPROVING':
      return 'improving'
    case 'RESOLVED':
      return 'none'
    case 'REQUIRES_TEACHER_REVIEW':
      return 'review'
    case 'NEW':
      return 'isolated'
    default:
      return 'none'
  }
}

const SEVERITY: Record<UiStatus, number> = { persistent: 4, review: 3, isolated: 2, improving: 1, none: 0 }

export function worstStatus(states: { state: string }[]): UiStatus {
  let worst: UiStatus = 'none'
  for (const s of states) {
    const st = stateToStatus(s.state)
    if (SEVERITY[st] > SEVERITY[worst]) worst = st
  }
  return worst
}

export function bySeverity<T extends { state: string }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => SEVERITY[stateToStatus(b.state)] - SEVERITY[stateToStatus(a.state)])
}

export function statusLabel(status: UiStatus): string {
  switch (status) {
    case 'persistent':
      return 'Persistent'
    case 'improving':
      return 'Improving'
    case 'isolated':
      return 'Isolated'
    case 'review':
      return 'Needs review'
    case 'none':
      return 'No continuing issue'
  }
}

export function statusExplanation(status: UiStatus): string {
  switch (status) {
    case 'persistent':
      return 'You have made this mistake on more than one problem. A few focused problems can help you get more comfortable with it.'
    case 'improving':
      return 'You are getting better at this. Keep practicing with similar problems.'
    case 'isolated':
      return 'This looks like an isolated mistake rather than a continuing problem.'
    case 'review':
      return 'The evidence is mixed, so TraceLearn has flagged this for your teacher to look at.'
    case 'none':
      return 'No continuing issue.'
  }
}

export function teacherLabel(status: UiStatus): string {
  switch (status) {
    case 'persistent':
      return 'Needs attention'
    case 'review':
      return 'Review diagnosis'
    case 'isolated':
      return 'Watch'
    case 'improving':
      return 'Improving'
    case 'none':
      return 'Doing well'
  }
}

export function problemStatusLabel(status: ProblemStatus): string {
  switch (status) {
    case 'needs-practice':
      return 'Needs Practice'
    case 'recommended':
      return 'Recommended'
    case 'improving':
      return 'Improving'
    case 'completed':
      return 'Completed'
    case 'not-started':
      return 'Not Started'
  }
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function shortDate(iso: string): string {
  const d = new Date(iso.endsWith('Z') || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function display(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value === '' ? '(empty)' : value
  return JSON.stringify(value)
}

export function testInput(input: { args?: unknown[]; stdin?: string } | null): string {
  if (!input) return 'hidden'
  if (typeof input.stdin === 'string') return input.stdin.trim() || '(no input)'
  if (Array.isArray(input.args)) return input.args.map((a) => JSON.stringify(a)).join(', ')
  return JSON.stringify(input)
}

export function confidencePct(c: number | null | undefined): string {
  return c == null ? '—' : `${Math.round(c * 100)}%`
}
