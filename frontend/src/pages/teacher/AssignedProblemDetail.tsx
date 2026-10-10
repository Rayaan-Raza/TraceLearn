import { Fragment, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { BarChart } from '../../components/MisconceptionCharts'
import { ErrorState, Loading, NotFound } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { formatDate } from '../../lib/labels'
import { submissionArea } from '../../lib/studentData'
import { useApi } from '../../lib/useApi'
import { misconceptionPoints } from './assignmentChart'

export function AssignedProblemDetail() {
  const { assignmentId = '' } = useParams()
  const id = Number(assignmentId)
  const navigate = useNavigate()
  const { data: a, error, loading, reload, setData } = useApi(() => api.assignment(id), [id])
  const problem = useApi(() => (a ? api.problem(a.problem_id) : Promise.resolve(null)), [a?.problem_id])
  const [expanded, setExpanded] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)

  if (loading) return <Loading />
  if (error?.toLowerCase().includes('not found') || !Number.isInteger(id))
    return <NotFound title="Assignment not found" body="This assigned problem is not available." back={{ to: '/teacher/assigned', label: 'Back to Assigned Problems' }} />
  if (error || !a) return <ErrorState message={error ?? 'Not found'} onRetry={reload} />

  const all = a.results.flatMap((r) => r.submissions)

  async function toggleState() {
    setBusy(true)
    try {
      const updated = await api.setAssignmentState(a!.id, a!.state === 'active' ? 'closed' : 'active')
      setData((prev) => (prev ? { ...prev, state: updated.state } : prev))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <header className="page-header">
        <p className="muted" style={{ marginBottom: '0.35rem' }}>
          <Link to="/teacher/assigned" className="btn btn-ghost" style={{ padding: 0 }}>
            ← Assigned Problems
          </Link>
        </p>
        <div className="split-header">
          <div>
            <h1>{a.problem_title}</h1>
            <p>
              Assigned {formatDate(a.assigned_at)}
              {a.due_date ? ` · Due ${a.due_date}` : ''}
              {a.notes ? ` · ${a.notes}` : ''}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className={`badge ${a.state === 'active' ? 'recommended' : 'isolated'}`}>{a.state === 'active' ? 'Active' : 'Closed'}</span>
            <button type="button" className="btn btn-secondary" onClick={() => void toggleState()} disabled={busy}>
              {a.state === 'active' ? 'Close assignment' : 'Reopen'}
            </button>
          </div>
        </div>
      </header>

      {problem.data ? (
        <section className="card">
          <div className="card-label">Problem</div>
          <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{problem.data.description}</p>
          <p className="meta" style={{ marginTop: '0.45rem' }}>
            {problem.data.topic} · {problem.data.difficulty} · {problem.data.test_cases.length} tests
          </p>
        </section>
      ) : null}

      <BarChart title="Misconceptions encountered in this problem" points={misconceptionPoints(all)} axisNote="X: misconception · Y: attempt count" />

      <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1.1rem 1.25rem 0.4rem' }}>
          <div className="card-label">Student results</div>
          <h2 style={{ margin: 0 }}>Who attempted it and what TraceLearn saw</h2>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Student</th>
              <th>Latest result</th>
              <th>Misconception</th>
              <th>Submitted</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {a.results.map((r) => {
              const latest = r.submissions[0]
              const isOpen = expanded === r.student_id
              return (
                <Fragment key={r.student_id}>
                  <tr>
                    <td style={{ fontWeight: 650 }}>
                      <Link to={`/teacher/students/${r.student_id}`}>{r.display_name}</Link>
                    </td>
                    <td>{latest ? <StatusBadge status={latest.passed ? 'correct' : 'incorrect'} /> : <span className="badge not-started">No attempt</span>}</td>
                    <td>{latest ? submissionArea(latest) ?? '—' : '—'}</td>
                    <td>{latest ? formatDate(latest.submitted_at) : '—'}</td>
                    <td>
                      <button type="button" className="btn btn-ghost" style={{ padding: 0 }} onClick={() => setExpanded(isOpen ? null : r.student_id)} disabled={r.submissions.length === 0}>
                        {r.submissions.length === 0 ? '—' : isOpen ? 'Hide' : `View attempts (${r.submissions.length})`}
                      </button>
                    </td>
                  </tr>
                  {isOpen &&
                    r.submissions.map((s) => (
                      <tr key={s.id}>
                        <td colSpan={5} style={{ background: 'var(--surface-warm)' }}>
                          <div className="split-header">
                            <span>
                              <strong>{s.passed ? 'Passed' : 'Failed'}</strong>
                              <span className="muted" style={{ marginLeft: 8 }}>
                                Attempt {s.attempt_number} · {formatDate(s.submitted_at)} · {s.tests_passed}/{s.tests_total} tests
                                {submissionArea(s) ? ` · ${submissionArea(s)}` : ''}
                              </span>
                            </span>
                            <button type="button" className="btn btn-secondary" onClick={() => navigate(`/teacher/submission/${s.id}`)}>
                              Full submission
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </section>
    </div>
  )
}
