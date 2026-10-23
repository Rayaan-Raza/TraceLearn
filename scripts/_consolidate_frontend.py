from pathlib import Path

ROOT = Path("frontend/src")

# --- api/client.ts ---
(ROOT / "api/client.ts").write_text(r'''import type {
  DiagnosisResult,
  EvidenceItem,
  LearnerProfile,
  ProblemDetail,
  ProblemSummary,
  RunAnalyzeResponse,
  StudentOption,
  TimelineEntry,
} from '../types'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text || 'request failed'}`)
  }
  return res.json() as Promise<T>
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
''', encoding='utf-8')

# --- types.ts patch ---
types = (ROOT / "types.ts").read_text(encoding='utf-8')
if 'TimelineEntry' not in types:
    types += '''

export type TimelineEntry = {
  submission_id: number
  problem_id: string
  attempt_number: number
  submitted_at: string
  execution_status?: string | null
  primary_diagnosis?: string | null
  state_transitions?: { misconception_id: string; old_state: string; new_state: string; timestamp: string }[]
}

export type LearnerProfile = {
  student_id: number
  display_name: string
  learner_states: LearnerStateRow[]
}
'''
    types = types.replace(
        'export type RunAnalyzeResponse = {',
        '''export type DiagnosisBrief = DiagnosisResult & { id?: number }

export type RunAnalyzeResponse = {'''
    )
    if 'current_only' not in types:
        types = types.replace(
            '  diagnoses?: DiagnosisResult[]',
            '  current_only?: DiagnosisBrief | null\n  history_aware?: DiagnosisBrief | null\n  diagnoses?: DiagnosisResult[]'
        )
    (ROOT / "types.ts").write_text(types, encoding='utf-8')

# --- App.tsx ---
(ROOT / "App.tsx").write_text(r'''import { useState } from 'react'
import { SessionProvider } from './context/SessionContext'
import { StudentSubmissionScreen } from './screens/StudentSubmission'
import { EvidenceInspectorScreen } from './screens/EvidenceInspector'
import { ComparisonScreen } from './screens/ComparisonView'
import { LearnerTimelineScreen } from './screens/LearnerTimeline'
import { TeacherExperimentScreen } from './screens/TeacherExperimentView'
import './index.css'

const TABS = [
  ['submission', 'Submission'],
  ['evidence', 'Evidence'],
  ['compare', 'Compare'],
  ['timeline', 'Timeline'],
  ['teacher', 'Teacher/Experiment'],
] as const

export default function App() {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('submission')
  return (
    <SessionProvider>
      <div className="app">
        <h1>TraceLearn POC</h1>
        <nav className="tabs">
          {TABS.map(([id, label]) => (
            <button key={id} type="button" className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>
        {tab === 'submission' && <StudentSubmissionScreen />}
        {tab === 'evidence' && <EvidenceInspectorScreen />}
        {tab === 'compare' && <ComparisonScreen />}
        {tab === 'timeline' && <LearnerTimelineScreen />}
        {tab === 'teacher' && <TeacherExperimentScreen />}
      </div>
    </SessionProvider>
  )
}
''', encoding='utf-8')

# --- StudentSubmission.tsx fixes ---
ss = (ROOT / "screens/StudentSubmission.tsx").read_text(encoding='utf-8')
ss = ss.replace(
    'const result = await runAndAnalyze(selectedStudent.display_name, problemId, editorCode)',
    'const result = await runAndAnalyze(selectedStudent.id, problemId, editorCode)'
)
ss = ss.replace(
    "const currentOnly = lastResult?.diagnoses?.find((d) => d.mode === 'current_only')\n  const historyAware = lastResult?.diagnoses?.find((d) => d.mode === 'history_aware')",
    'const currentOnly = lastResult?.current_only ?? lastResult?.diagnoses?.find((d) => d.mode === \'current_only\')\n  const historyAware = lastResult?.history_aware ?? lastResult?.diagnoses?.find((d) => d.mode === \'history_aware\')'
)
(ROOT / "screens/StudentSubmission.tsx").write_text(ss, encoding='utf-8')

# --- ComparisonView fixes ---
cv = (ROOT / "screens/ComparisonView.tsx").read_text(encoding='utf-8')
cv = cv.replace(
    'const [diagnoses, setDiagnoses] = useState<DiagnosisResult[]>(lastResult?.diagnoses ?? [])',
    'const [diagnoses, setDiagnoses] = useState<DiagnosisResult[]>([])'
)
insert = '''
    if (lastResult?.current_only || lastResult?.history_aware) {
      const built: DiagnosisResult[] = []
      if (lastResult.current_only) built.push({ ...lastResult.current_only, mode: 'current_only' })
      if (lastResult.history_aware) built.push({ ...lastResult.history_aware, mode: 'history_aware' })
      setDiagnoses(built)
      return
    }
'''
cv = cv.replace('    if (lastResult.diagnoses?.length) {', insert + '    if (lastResult.diagnoses?.length) {')
(ROOT / "screens/ComparisonView.tsx").write_text(cv, encoding='utf-8')

# --- LearnerTimeline fixes ---
lt = (ROOT / "screens/LearnerTimeline.tsx").read_text(encoding='utf-8')
lt = lt.replace('TimelineEvent', 'TimelineEntry').replace('events', 'entries').replace('setEvents', 'setEntries').replace('TimelineEntry[]', 'TimelineEntry[]')
lt = lt.replace(
    '''      <ol className="timeline">
        {events.map((ev) => (
          <li key={ev.id} className="timeline-item">
            <time>{new Date(ev.timestamp).toLocaleString()}</time>
            <strong>{ev.event_type}</strong>
            <p>{ev.summary}</p>
            {ev.problem_id && <span className="tag">{ev.problem_id}</span>}
          </li>
        ))}
      </ol>''',
    '''      <ol className="timeline">
        {entries.map((ev) => (
          <li key={ev.submission_id} className="timeline-item">
            <time>{new Date(ev.submitted_at).toLocaleString()}</time>
            <strong>{ev.problem_id} attempt {ev.attempt_number}</strong>
            <p>{ev.primary_diagnosis ?? '—'}</p>
            {ev.state_transitions?.map((tr, i) => (
              <div key={i} className="muted">{tr.old_state} → {tr.new_state} ({tr.misconception_id})</div>
            ))}
          </li>
        ))}
      </ol>'''
)
lt = lt.replace('const [entries, setEntries]', 'const [entries, setEntries]')
(ROOT / "screens/LearnerTimeline.tsx").write_text(lt, encoding='utf-8')

# --- TeacherExperimentView ---
(ROOT / "screens/TeacherExperimentView.tsx").write_text(r'''import { useEffect, useState } from 'react'
import { fetchExperimentComparison, fetchLearnerProfile, submitTeacherReview } from '../api/client'
import { useSession } from '../context/SessionContext'
import type { LearnerStateRow } from '../types'

export function TeacherExperimentScreen() {
  const { selectedStudentId, lastResult } = useSession()
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null)
  const [states, setStates] = useState<LearnerStateRow[]>([])
  const [msg, setMsg] = useState('')

  useEffect(() => {
    void fetchExperimentComparison().then(setComparison).catch(() => setComparison(null))
  }, [lastResult])

  useEffect(() => {
    if (selectedStudentId == null) return
    void fetchLearnerProfile(selectedStudentId)
      .then((p) => setStates(p.learner_states))
      .catch(() => setStates([]))
  }, [selectedStudentId, lastResult])

  const diagnosisId = lastResult?.history_aware?.id

  return (
    <div className="screen">
      <header className="screen-header">
        <h2>Teacher / Experiment View</h2>
      </header>
      <section className="card">
        <h3>Experiment comparison (calculated)</h3>
        <pre>{comparison ? JSON.stringify(comparison, null, 2) : 'Run experiment script or demo sequence to populate.'}</pre>
      </section>
      <section className="card">
        <h3>Learner states</h3>
        {states.length === 0 ? <p className="muted">No states yet.</p> : (
          <table className="data-table"><tbody>
            {states.map((s) => <tr key={s.id}><td>{s.misconception_id}</td><td>{s.state}</td><td>{s.confidence.toFixed(2)}</td></tr>)}
          </tbody></table>
        )}
      </section>
      {diagnosisId && (
        <section className="card">
          <h3>Teacher review</h3>
          <button type="button" onClick={() => void submitTeacherReview(diagnosisId, 'CONFIRM').then(() => setMsg('CONFIRM saved'))}>Confirm</button>{' '}
          <button type="button" onClick={() => void submitTeacherReview(diagnosisId, 'REJECT').then(() => setMsg('REJECT saved'))}>Reject</button>{' '}
          <button type="button" onClick={() => void submitTeacherReview(diagnosisId, 'MARK_UNCERTAIN').then(() => setMsg('MARK_UNCERTAIN saved'))}>Mark uncertain</button>
          {msg && <p>{msg}</p>}
        </section>
      )}
    </div>
  )
}
''', encoding='utf-8')

# remove duplicate api.ts
api_ts = ROOT / "api.ts"
if api_ts.exists():
    api_ts.unlink()

print("frontend consolidated")
