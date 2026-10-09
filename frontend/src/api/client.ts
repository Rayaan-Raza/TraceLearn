import type {
  AuthResponse,
  DiagnosisResult,
  EvidenceItem,
  LearnerProfile,
  ProblemDetail,
  ProblemSummary,
  RunAnalyzeResponse,
  StudentOption,
  TimelineEntry,
} from '../types'

function getToken(): string | null {
  try {
    return localStorage.getItem('tl_token')
  } catch {
    return null
  }
}

function authHeader(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text || 'request failed'}`)
  }
  return res.json() as Promise<T>
}

export async function authLogin(email: string, password: string): Promise<AuthResponse> {
  const body = new URLSearchParams({ username: email, password })
  return parseJson(await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  }))
}

export async function authRegister(
  email: string,
  password: string,
  role: string,
  display_name: string,
): Promise<AuthResponse> {
  return parseJson(await fetch('/api/auth/register', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ email, password, role, display_name }),
  }))
}

export async function fetchProblems(): Promise<ProblemSummary[]> {
  return parseJson(await fetch('/api/problems'))
}

export async function fetchProblem(problemId: string): Promise<ProblemDetail> {
  return parseJson(await fetch(`/api/problems/${problemId}`))
}

export async function fetchStudents(): Promise<StudentOption[]> {
  return parseJson(await fetch('/api/students'))
}

export async function runAndAnalyze(
  studentId: number,
  problemId: string,
  sourceCode: string,
): Promise<RunAnalyzeResponse> {
  const created = await fetch('/api/submissions', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ student_id: studentId, problem_id: problemId, source_code: sourceCode }),
  })
  const submission = await parseJson<{ id: number }>(created)
  return parseJson(await fetch(`/api/submissions/${submission.id}/run-and-analyze`, { method: 'POST' }))
}

export async function fetchSubmissionEvidence(submissionId: number): Promise<EvidenceItem[]> {
  return parseJson(await fetch(`/api/submissions/${submissionId}/evidence`))
}

export async function fetchSubmissionDiagnoses(submissionId: number): Promise<DiagnosisResult[]> {
  return parseJson(await fetch(`/api/submissions/${submissionId}/diagnoses`))
}

export async function fetchLearnerTimeline(studentId: number): Promise<TimelineEntry[]> {
  return parseJson(await fetch(`/api/students/${studentId}/timeline`))
}

export async function fetchLearnerProfile(studentId: number): Promise<LearnerProfile> {
  return parseJson(await fetch(`/api/students/${studentId}/learner-profile`))
}

export async function fetchExperimentComparison(): Promise<Record<string, unknown>> {
  return parseJson(await fetch('/api/evaluation/comparison'))
}

export async function submitTeacherReview(diagnosisId: number, action: string, comment = ''): Promise<void> {
  await parseJson(await fetch(`/api/diagnoses/${diagnosisId}/teacher-review`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ action, comment }),
  }))
}
