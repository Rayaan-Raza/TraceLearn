import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { Classroom } from '../../api/types'
import { BarChart } from '../../components/MisconceptionCharts'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { formatDate } from '../../lib/labels'
import { submissionArea } from '../../lib/studentData'
import { useApi } from '../../lib/useApi'
import { misconceptionPoints } from './assignmentChart'
import { RequireClass } from './shared'

function List({ room }: { room: Classroom }) {
  const navigate = useNavigate()
  const { data, error, loading, reload } = useApi(async () => {
    const list = await api.classAssignments(room.id)
    return Promise.all(list.map((a) => api.assignment(a.id)))
  }, [room.id])

  if (loading) return <Loading />
  if (error || !data) return <ErrorState message={error ?? 'Could not load'} onRetry={reload} />

  return (
    <div className="stack">
      <header className="page-header">
        <div className="split-header">
          <div>
            <h1>Assigned Problems</h1>
            <p>Every problem you assigned in {room.code} — student results, misconceptions, and a per-problem overview chart.</p>
          </div>
          <Link className="btn btn-primary" to="/teacher/classroom/assign">
            Assign Problem
          </Link>
        </div>
      </header>

      <div className="grid-3">
        <section className="card">
          <div className="card-label">Assigned</div>
          <div className="stat-value">{data.length}</div>
        </section>
        <section className="card">
          <div className="card-label">Active</div>
          <div className="stat-value">{data.filter((a) => a.state === 'active').length}</div>
        </section>
        <section className="card">
          <div className="card-label">Closed</div>
          <div className="stat-value">{data.filter((a) => a.state === 'closed').length}</div>
        </section>
      </div>

      {data.length === 0 ? (
        <section className="card">
          <p className="muted" style={{ margin: 0 }}>No assigned problems yet.</p>
        </section>
      ) : (
        data.map((a) => {
          const all = a.results.flatMap((r) => r.submissions)
          const latest = a.results.map((r) => ({ ...r, latest: r.submissions[0] }))
          const passed = latest.filter((r) => r.latest?.passed).length
          const failed = latest.filter((r) => r.latest && !r.latest.passed).length
          const waiting = latest.filter((r) => !r.latest).length
          return (
            <section className="card" key={a.id}>
              <div className="split-header">
                <div>
                  <div className="card-label">{a.state === 'active' ? 'Active assignment' : 'Closed assignment'}</div>
                  <h2 style={{ margin: 0 }}>{a.problem_title}</h2>
                  <p style={{ marginTop: '0.35rem' }}>
                    Assigned {formatDate(a.assigned_at)}
                    {a.due_date ? ` · Due ${a.due_date}` : ''}
                  </p>
                  {a.notes ? <p className="muted" style={{ marginTop: '0.25rem' }}>{a.notes}</p> : null}
                  <p className="meta" style={{ marginTop: '0.45rem' }}>
                    {a.problem_topic || '—'} · {a.problem_difficulty || '—'} · {passed} passed · {failed} failed · {waiting} waiting · {all.length} total attempts
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                  <span className={`badge ${a.state === 'active' ? 'recommended' : 'isolated'}`}>{a.state === 'active' ? 'Active' : 'Closed'}</span>
                  <button type="button" className="btn btn-secondary" onClick={() => navigate(`/teacher/assigned/${a.id}`)}>
                    Open details
                  </button>
                </div>
              </div>
              <div style={{ marginTop: '1rem' }}>
                <BarChart embedded title="Misconceptions in this problem" points={misconceptionPoints(all)} axisNote="X: misconception · Y: attempt count" />
              </div>
              <div style={{ marginTop: '1rem', overflowX: 'auto' }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Student</th>
                      <th>Result</th>
                      <th>Misconception</th>
                      <th>Submitted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {latest.map((r) => (
                      <tr key={r.student_id} className={r.latest ? 'clickable' : undefined} onClick={() => r.latest && navigate(`/teacher/submission/${r.latest.id}`)}>
                        <td style={{ fontWeight: 650 }}>{r.display_name}</td>
                        <td>{r.latest ? <StatusBadge status={r.latest.passed ? 'correct' : 'incorrect'} /> : <span className="badge not-started">No attempt</span>}</td>
                        <td>{r.latest ? submissionArea(r.latest) ?? '—' : '—'}</td>
                        <td>{r.latest ? formatDate(r.latest.submitted_at) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )
        })
      )}
    </div>
  )
}

export function AssignedProblemsPage() {
  return <RequireClass>{(room) => <List room={room} />}</RequireClass>
}
