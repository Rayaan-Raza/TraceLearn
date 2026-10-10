import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { Assignment, SubmissionSummary } from '../../api/types'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { useMe } from '../../context/AuthContext'
import { useClasses } from '../../context/ClassContext'
import { formatDate } from '../../lib/labels'
import { useApi } from '../../lib/useApi'

function JoinForm({ onJoined }: { onJoined: () => void }) {
  const [code, setCode] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  async function join(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMsg('')
    try {
      const room = await api.joinClassroom(code)
      setMsg(`Joined ${room.code} — ${room.name}.`)
      setCode('')
      onJoined()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Could not join')
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="join-form" onSubmit={(e) => void join(e)}>
      <label className="field" style={{ flex: 1 }}>
        <span>Class join code</span>
        <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="e.g. K7Q2M9XD" maxLength={16} autoComplete="off" required />
      </label>
      <button type="submit" className="btn btn-primary" disabled={busy || code.trim().length < 4}>
        Join class
      </button>
      {msg ? <p className="toast-msg" style={{ width: '100%' }}>{msg}</p> : null}
    </form>
  )
}

export function StudentClassroomPage() {
  const me = useMe()
  const navigate = useNavigate()
  const { classrooms, refresh } = useClasses()
  const { data, error, loading, reload } = useApi(
    () => Promise.all([api.myAssignments(), api.studentSubmissions(me.student_id!)]),
    [me.student_id, classrooms.length],
  )
  const [expandedId, setExpandedId] = useState<number | null>(null)

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} onRetry={reload} />
  const [assignments, subs] = data!
  const active = assignments.filter((a) => a.state === 'active')
  const previous = assignments.filter((a) => a.state === 'closed')
  const attemptsFor = (a: Assignment): SubmissionSummary[] => subs.filter((s) => s.problem_id === a.problem_id)

  function card(a: Assignment, isPast: boolean) {
    const attempts = attemptsFor(a)
    const latest = attempts[0]
    const isOpen = expandedId === a.id
    return (
      <section className="card" key={a.id}>
        <div className="split-header">
          <div>
            <div className="card-label">{isPast ? 'Previous assignment' : 'Current assignment'} · {a.classroom_name}</div>
            <h2 style={{ margin: 0 }}>{a.problem_title}</h2>
            <p style={{ marginTop: '0.35rem' }}>
              Assigned {formatDate(a.assigned_at)}
              {a.due_date ? ` · Due ${a.due_date}` : ''}
            </p>
            {a.notes ? <p className="muted" style={{ marginTop: '0.25rem' }}>{a.notes}</p> : null}
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            {latest ? <StatusBadge status={latest.passed ? 'correct' : 'incorrect'} /> : <span className="badge not-started">Not submitted</span>}
            <span className={`badge ${isPast ? 'isolated' : 'recommended'}`}>{isPast ? 'Closed' : 'Active'}</span>
          </div>
        </div>
        <div className="btn-row">
          {!isPast && (
            <button type="button" className="btn btn-primary" onClick={() => navigate(`/student/problem/${encodeURIComponent(a.problem_id)}`)}>
              Open question
            </button>
          )}
          <button type="button" className="btn btn-secondary" onClick={() => setExpandedId(isOpen ? null : a.id)} disabled={attempts.length === 0}>
            {attempts.length === 0 ? 'No attempts yet' : isOpen ? 'Hide attempts' : `View my attempts (${attempts.length})`}
          </button>
          {latest && (
            <Link className="btn btn-ghost" to={`/student/submissions/${latest.id}`}>
              Latest submission
            </Link>
          )}
        </div>
        {isOpen && (
          <div className="stack" style={{ marginTop: '1rem', gap: '0.5rem' }}>
            {attempts.map((s) => (
              <Link key={s.id} to={`/student/submissions/${s.id}`} className="recommended-item split-header" style={{ textDecoration: 'none' }}>
                <span>
                  <strong>Attempt {s.attempt_number}</strong>
                  <span className="muted" style={{ marginLeft: 8 }}>
                    {formatDate(s.submitted_at)} · {s.tests_passed}/{s.tests_total} tests
                  </span>
                </span>
                <StatusBadge status={s.passed ? 'correct' : 'incorrect'} />
              </Link>
            ))}
          </div>
        )}
      </section>
    )
  }

  return (
    <div className="stack">
      <header className="page-header">
        <h1>Classroom</h1>
        <p>
          {classrooms.length
            ? `Your classes: ${classrooms.map((c) => `${c.code} (${c.teacher_name})`).join(', ')}`
            : 'You have not joined a class yet. Ask your teacher for the join code.'}
        </p>
      </header>

      <section className="card">
        <div className="card-label">Join a class</div>
        <JoinForm onJoined={() => void refresh()} />
      </section>

      <div className="grid-3">
        <section className="card">
          <div className="card-label">Active</div>
          <div className="stat-value">{active.length}</div>
        </section>
        <section className="card">
          <div className="card-label">Previous</div>
          <div className="stat-value">{previous.length}</div>
        </section>
        <section className="card">
          <div className="card-label">Your submissions here</div>
          <div className="stat-value">{assignments.reduce((n, a) => n + attemptsFor(a).length, 0)}</div>
        </section>
      </div>

      <div>
        <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.15rem' }}>Current class assignments</h2>
        {active.length === 0 ? (
          <section className="card">
            <p className="muted" style={{ margin: 0 }}>No active assignments.</p>
          </section>
        ) : (
          <div className="stack">{active.map((a) => card(a, false))}</div>
        )}
      </div>

      <div>
        <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.15rem' }}>Previous class assignments</h2>
        {previous.length === 0 ? (
          <section className="card">
            <p className="muted" style={{ margin: 0 }}>No previous class assignments yet.</p>
          </section>
        ) : (
          <div className="stack">{previous.map((a) => card(a, true))}</div>
        )}
      </div>
    </div>
  )
}
