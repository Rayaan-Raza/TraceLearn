/** Human-facing names, descriptions, and status mapping for backend misconception data. */

export type UiStatus = 'persistent' | 'improving' | 'isolated' | 'none' | 'review'
export type ProblemStatus = 'needs-practice' | 'recommended' | 'improving' | 'completed' | 'not-started'

export interface ChartPoint {
  label: string
  count: number
  tone?: string
  color?: string
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
  CPP_RANGE_CHECK: 'Range Checks',
  CPP_STALE_EXIT: 'Stale Loop Exit',
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

/** Short plain-language description shown below a diagnosis label. */
const MISCONCEPTION_DESCRIPTIONS: Record<string, string> = {
  CPP_LOOP_BOUNDARY: 'The loop runs one iteration too many or too few because the boundary condition is off by one.',
  CPP_OFF_BY_ONE: 'An index is one too large or too small, causing a wrong value to be read or written.',
  CPP_ARRAY_BOUNDS: 'The code accesses an array or vector at an index that is out of its valid range.',
  CPP_UNINITIALIZED_VAR: 'A variable is used before it has been given a value, so its content is unpredictable.',
  CPP_INT_OVERFLOW: 'A numeric computation exceeds the range of int, wrapping around to a wrong value.',
  CPP_MISSING_BASE_CASE: 'A recursive function does not have a condition that stops it, causing infinite recursion.',
  CPP_ASSIGN_VS_COMPARE: 'An assignment operator (=) was written where a comparison (==) was intended inside a condition.',
  CPP_WRONG_LOOP_DIR: 'The loop variable moves in the wrong direction, so the loop runs backwards or not at all.',
  CPP_RANGE_CHECK: 'The range check is written as a chained comparison (a < x < b) which does not work as expected in C++.',
  CPP_STALE_EXIT: "The loop's exit variable is never updated inside the body, so the loop runs forever.",
  CPP_OTHER_ERROR: 'The code contains an error that does not fit the specific misconception categories.',
  M01_LOOP_BOUNDARY: 'The loop boundary is off, causing it to run too many or too few times.',
  M02_INDEX_VALUE: 'The code returns or uses an index where the actual value is expected, or vice versa.',
  M03_MISSING_RETURN: 'The function prints its result instead of returning it to the caller.',
}

/** Short description for a misconception. Falls back to a generic message. */
export function misconceptionDescription(id: string | null | undefined): string {
  if (!id) return ''
  return MISCONCEPTION_DESCRIPTIONS[id] ?? 'Review the problem statement and trace through your code carefully.'
}

/** CSS color token for a misconception category (matches the chart palette). */
const MISCONCEPTION_COLORS: Record<string, string> = {
  CPP_LOOP_BOUNDARY: '#4f7dd4',
  CPP_OFF_BY_ONE: '#7c5cbf',
  CPP_ARRAY_BOUNDS: '#d45f4f',
  CPP_UNINITIALIZED_VAR: '#d49a4f',
  CPP_INT_OVERFLOW: '#4fb0d4',
  CPP_MISSING_BASE_CASE: '#4fd48a',
  CPP_ASSIGN_VS_COMPARE: '#d4c14f',
  CPP_WRONG_LOOP_DIR: '#d47a4f',
  CPP_RANGE_CHECK: '#5fd4b0',
  CPP_STALE_EXIT: '#a04fd4',
  CPP_OTHER_ERROR: '#8d9ea8',
  M01_LOOP_BOUNDARY: '#4f7dd4',
  M02_INDEX_VALUE: '#7c5cbf',
  M03_MISSING_RETURN: '#d49a4f',
}

/** Hex color for a misconception. Falls back to a neutral grey. */
export function misconceptionColor(id: string | null | undefined): string {
  if (!id) return '#8d9ea8'
  return MISCONCEPTION_COLORS[id] ?? '#8d9ea8'
}

/** Confidence band: low / medium / high — do not show raw probabilities to students. */
export function confidenceBand(p: number | null | undefined): 'low' | 'medium' | 'high' {
  if (p == null) return 'low'
  if (p >= 0.75) return 'high'
  if (p >= 0.5) return 'medium'
  return 'low'
}

export function confidenceBandLabel(p: number | null | undefined): string {
  const band = confidenceBand(p)
  return band === 'high' ? 'High confidence' : band === 'medium' ? 'Some confidence' : 'Low confidence'
}
