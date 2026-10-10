import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { Classroom } from '../../api/types'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { formatDate, misconceptionLabel, bySeverity, worstStatus } from '../../lib/labels'
import { submissionArea } from '../../lib/studentData'
import { useApi } from '../../lib/useApi'
import { JoinCodeCard, RequireClass } from './shared'

function Room({ room }: { room: Classroom }) {
  const { data, error, loading, reload } = useApi(async () => {
    const [overview, assignments] = await Promise.all([api.overview(room.id), api.classAssignments(room.id)])
    const subs = (await Promise.all(overview.students.map((s) => api.studentSubmissions(s.id)))).flat()
    subs.sort((a, b) => b.submitted_at.localeCompare(a.submitted_at))
    return { overview, assignments, subs }
  }, [room.id])

  if (loading) return <Loading />
  if (error || !data) return <ErrorState message={error ?? 'Could not load'} onRetry={reload} />
  const { overview, assignments, subs } = data
  const names = new Map(overview.students.map((s) => [s.id, s.display_name]))

  async function remove(studentId: number, name: string) {
    if (!window.confirm(`Remove ${name} from ${room.code}? Their submissions are kept.`)) return
    await api.removeMember(room.id, studentId)
    reload()
  }

  return (
    <div className="stack">
      <header className="page-header">
        <div className="split-header">
          <div>
            <h1>Classroom</h1>
            <p>{room.code} — manage assignments, review submissions, and track class results.</p>
          </div>
          <Link className="btn btn-primary" to="/teacher/classroom/assign">
            Assign Problem
          </Link>
        </div>
      </header>

      <div className="grid-3">
        <section className="card">
          <div className="card-label">Students</div>
          <div className="stat-value">{overview.totals.students}</div>
        </section>
        <section className="card">
          <div className="card-label">Active Assignments</div>
          <div className="stat-value">{overview.totals.active_assignments}</div>
        </section>
        <section className="card">
          <div className="card-label">Submissions</div>
          <div className="stat-value">{overview.totals.submissions}</div>
        </section>
      </div>

      <JoinCodeCard classroom={overview.classroom} />

      <section className="card">
        <div className="card-label">Class roster</div>
        <h2 style={{ margin: '0 0 0.85rem' }}>Students in this classroom</h2>
        {overview.students.length === 0 ? (
          <p className="muted">No students yet.</p>
        ) : (
          <div className="stack" style={{ gap: '0.65rem' }}>
            {overview.students.map((s) => {
              const top = bySeverity(s.states)[0]
              const assigned = assignments.filter((a) => a.student_ids.includes(s.id)).length
              return (
                <div key={s.id} className="card interactive" style={{ padding: '0.95rem 1.05rem' }}>
                  <div className="split-header">
                    <Link to={`/teacher/students/${s.id}`} style={{ textDecoration: 'none', color: 'inherit', flex: 1 }}>
                      <h3 style={{ margin: 0 }}>{s.display_name}</h3>
                      <p style={{ marginTop: '0.25rem' }}>{top ? `${misconceptionLabel(top.misconception_id)} — ${top.state.toLowerCase().replace(/_/g, ' ')}` : 'No misconception tracked'}</p>
                      <p className="meta" style={{ marginTop: '0.35rem' }}>
                        {s.submission_count} submissions · {s.solved_problems} solved · {assigned} assigned problems
                      </p>
                    </Link>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <StatusBadge status={worstStatus(s.states)} />
                      <button type="button" className="btn btn-ghost" onClick={() => void remove(s.id, s.display_name)}>
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1.1rem 1.25rem 0.4rem' }}>
          <div className="split-header">
            <div>
              <div className="card-label">Assigned problems</div>
              <h2 style={{ margin: 0 }}>What the class is working on</h2>
            </div>
            <Link className="btn btn-secondary" to="/teacher/classroom/assign">
              New assignment
            </Link>
          </div>
        </div>
        {assignments.length === 0 ? (
          <p style={{ padding: '0.5rem 1.25rem 1.25rem' }} className="muted">
            No assignments yet.
          </p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Problem</th>
                <th>Assigned to</th>
                <th>Assigned</th>
                <th>Due</th>
                <th>Results</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((a) => {
                const related = subs.filter((s) => s.problem_id === a.problem_id && a.student_ids.includes(s.student_id))
                const done = new Set(related.filter((s) => s.passed).map((s) => s.student_id)).size
                return (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 650 }}>
                      <Link to={`/teacher/assigned/${a.id}`}>{a.problem_title}</Link>
                    </td>
                    <td>{a.student_ids.map((id) => names.get(id) ?? `#${id}`).join(', ')}</td>
                    <td>{formatDate(a.assigned_at)}</td>
                    <td>{a.due_date || '—'}</td>
                    <td>{related.length === 0 ? 'Waiting for submissions' : `${done}/${a.student_ids.length} correct · ${related.length} attempts`}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>

      <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1.1rem 1.25rem 0.4rem' }}>
          <div className="card-label">Recent class submissions</div>
          <h2 style={{ margin: 0 }}>History across the classroom</h2>
        </div>
        {subs.length === 0 ? (
          <p className="muted" style={{ padding: '0.5rem 1.25rem 1.25rem' }}>No submissions yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Student</th>
                <th>Problem</th>
                <th>Result</th>
                <th>Submitted</th>
                <th>Area</th>
              </tr>
            </thead>
            <tbody>
              {subs.slice(0, 25).map((s) => (
                <tr key={s.id}>
                  <td>{names.get(s.student_id)}</td>
                  <td>
                    <Link to={`/teacher/submission/${s.id}`} style={{ fontWeight: 650 }}>
                      {s.problem_title}
                    </Link>
                  </td>
                  <td>
                    <StatusBadge status={s.passed ? 'correct' : 'incorrect'} />
                  </td>
                  <td>{formatDate(s.submitted_at)}</td>
                  <td>{submissionArea(s) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

export function ClassroomPage() {
  return <RequireClass>{(room) => <Room room={room} />}</RequireClass>
}
