/**
 * Thin typed client for the TraceLearn API.
 *
 * Auth model: the backend sets an httpOnly session cookie (not readable by
 * JavaScript, so an XSS bug cannot steal it) plus a readable CSRF cookie.
 * Every state-changing request echoes the CSRF cookie in X-CSRF-Token.
 * No token is ever stored in localStorage.
 */
import type {
  Assignment,
  AssignmentDetail,
  Classroom,
  ClassroomOverview,
  Diagnosis,
  EvidenceItem,
  Hint,
  LearnerProfile,
  Me,
  Member,
  NewTestCase,
  ProblemDetail,
  ProblemSummary,
  RunResult,
  StudentRow,
  Submission,
  SubmissionSummary,
  TeacherReview,
  TestResult,
  TimelineEntry,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Fired when the session is missing/expired so the app can show the login screen. */
export const UNAUTHORIZED_EVENT = 'tracelearn:unauthorized'

function readCookie(name: string): string | null {
  for (const part of document.cookie.split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k === name) return decodeURIComponent(v.join('='))
  }
  return null
}

function detailMessage(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const d = (body as { detail: unknown }).detail
    if (typeof d === 'string') return d
    if (Array.isArray(d) && d.length) {
      return d
        .map((e) => (e && typeof e === 'object' && 'msg' in e ? String((e as { msg: unknown }).msg) : ''))
        .filter(Boolean)
        .join('; ')
        .replace(/^Value error, /, '')
    }
  }
  return fallback
}

async function request<T>(method: string, path: string, body?: unknown, form?: URLSearchParams): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (method !== 'GET') {
    const csrf = readCookie('tl_csrf')
    if (csrf) headers['X-CSRF-Token'] = csrf
  }
  let payload: BodyInit | undefined
  if (form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    payload = form.toString()
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let res: Response
  try {
    res = await fetch(BASE + path, { method, headers, body: payload, credentials: 'include' })
  } catch {
    throw new ApiError(0, 'Cannot reach the TraceLearn server. Is the backend running?')
  }

  if (res.status === 204) return undefined as T
  let data: unknown = null
  const text = await res.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/api/auth/login')) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    }
    const fallback =
      res.status === 429
        ? 'Too many requests — please wait a moment and try again.'
        : res.status === 413
          ? 'That request is too large.'
          : `Request failed (${res.status})`
    throw new ApiError(res.status, detailMessage(data, fallback))
  }
  return data as T
}

const e = encodeURIComponent

export const api = {
  // auth
  me: () => request<Me>('GET', '/api/auth/me'),
  login: (email: string, password: string) =>
    request<Me>('POST', '/api/auth/login', undefined, new URLSearchParams({ username: email, password })),
  register: (body: { email: string; password: string; display_name: string; role: 'student' | 'teacher'; teacher_code?: string }) =>
    request<Me>('POST', '/api/auth/register', body),
  logout: () => request<void>('POST', '/api/auth/logout'),

  // problems
  problems: () => request<ProblemSummary[]>('GET', '/api/problems'),
  problem: (id: string) => request<ProblemDetail>('GET', `/api/problems/${e(id)}`),
  createProblem: (body: {
    title: string
    description: string
    topic: string
    difficulty: string
    starter_code: string
    test_cases: NewTestCase[]
  }) => request<ProblemDetail>('POST', '/api/problems', body),

  // submissions
  submit: (problemId: string, sourceCode: string) =>
    request<Submission>('POST', '/api/submissions', { problem_id: problemId, source_code: sourceCode }),
  runAndAnalyze: (id: number) => request<RunResult>('POST', `/api/submissions/${id}/run-and-analyze`),
  submission: (id: number) => request<Submission>('GET', `/api/submissions/${id}`),
  testResults: (id: number) => request<TestResult[]>('GET', `/api/submissions/${id}/test-results`),
  diagnoses: (id: number) => request<Diagnosis[]>('GET', `/api/submissions/${id}/diagnoses`),
  evidence: (id: number) => request<EvidenceItem[]>('GET', `/api/submissions/${id}/evidence`),
  hints: (id: number) => request<Hint[]>('GET', `/api/submissions/${id}/hints`),
  nextHint: (id: number) => request<Hint>('POST', `/api/submissions/${id}/next-hint`),
  reviews: (id: number) => request<TeacherReview[]>('GET', `/api/submissions/${id}/reviews`),
  review: (diagnosisId: number, body: { action: string; corrected_misconception?: string | null; comment?: string }) =>
    request<TeacherReview>('POST', `/api/diagnoses/${diagnosisId}/teacher-review`, body),

  // students
  students: () => request<StudentRow[]>('GET', '/api/students'),
  studentSubmissions: (id: number) => request<SubmissionSummary[]>('GET', `/api/students/${id}/submissions`),
  timeline: (id: number) => request<TimelineEntry[]>('GET', `/api/students/${id}/timeline`),
  profile: (id: number) => request<LearnerProfile>('GET', `/api/students/${id}/learner-profile`),

  // classrooms
  classrooms: () => request<Classroom[]>('GET', '/api/classrooms'),
  createClassroom: (code: string, name: string) => request<Classroom>('POST', '/api/classrooms', { code, name }),
  joinClassroom: (joinCode: string) => request<Classroom>('POST', '/api/classrooms/join', { join_code: joinCode }),
  rotateJoinCode: (id: number) => request<Classroom>('POST', `/api/classrooms/${id}/rotate-code`),
  members: (id: number) => request<Member[]>('GET', `/api/classrooms/${id}/members`),
  removeMember: (id: number, studentId: number) => request<void>('DELETE', `/api/classrooms/${id}/members/${studentId}`),
  overview: (id: number) => request<ClassroomOverview>('GET', `/api/classrooms/${id}/overview`),
  classAssignments: (id: number) => request<Assignment[]>('GET', `/api/classrooms/${id}/assignments`),
  createAssignment: (id: number, body: { problem_id: string; student_ids: number[]; due_date: string; notes: string }) =>
    request<Assignment>('POST', `/api/classrooms/${id}/assignments`, body),
  myAssignments: () => request<Assignment[]>('GET', '/api/assignments/mine'),
  assignment: (id: number) => request<AssignmentDetail>('GET', `/api/assignments/${id}`),
  setAssignmentState: (id: number, state: 'active' | 'closed') =>
    request<Assignment>('PATCH', `/api/assignments/${id}`, { state }),

  // research
  experiment: () => request<Record<string, unknown>>('GET', '/api/evaluation/comparison'),
  demoStatus: () =>
    request<{ enabled: boolean; sequences: string[]; sandbox: { mode: string; isolated: boolean; required: boolean } }>(
      'GET',
      '/api/demo/status',
    ),
  demoReset: () => request<{ status: string }>('POST', '/api/demo/reset'),
  demoRun: (name: string) => request<{ attempts_processed: number }>('POST', `/api/demo/run-sequence/${e(name)}`),
}
