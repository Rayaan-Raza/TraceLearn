import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Classroom } from '../../api/types'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { bySeverity, confidencePct, misconceptionLabel, stateToStatus, statusLabel, worstStatus } from '../../lib/labels'
import { useApi } from '../../lib/useApi'
import { RequireClass } from './shared'

function View({ room }: { room: Classroom }) {
  const { misconceptionId } = useParams()
  const { data, error, loading, reload } = useApi(() => api.overview(room.id), [room.id])
  if (loading) return <Loading />
  if (error || !data) return <ErrorState message={error ?? 'Could not load'} onRetry={reload} />

  const selected = misconceptionId ? data.misconceptions.find((m) => m.misconception_id === misconceptionId) : undefined

  if (misconceptionId) {
    const students = selected ? bySeverity(selected.students) : []
    return (
      <div className="stack">
        <header className="page-header">
          <p className="muted" style={{ marginBottom: '0.35rem' }}>
            <Link to="/teacher/misconceptions" className="btn btn-ghost" style={{ padding: 0 }}>
              ← Misconceptions
            </Link>
          </p>
          <h1>{misconceptionLabel(misconceptionId)}</h1>
          <p>
            {selected?.attention_count ?? 0} student{selected?.attention_count === 1 ? '' : 's'} currently need attention · {students.length} with this concept tracked
          </p>
        </header>
        {students.length === 0 ? (
          <section className="card">
            <h2>No students tracked</h2>
            <p>Nobody in {room.code} has evidence for this misconception.</p>
          </section>
        ) : (
          students.map((s) => (
            <section className="card" key={s.student_id}>
              <div className="split-header">
                <div>
                  <div className="card-label">Student</div>
                  <h2 style={{ margin: 0 }}>{s.display_name}</h2>
                </div>
                <StatusBadge status={stateToStatus(s.state)} />
              </div>
              <div className="grid-3" style={{ marginTop: '1.1rem' }}>
                <div>
                  <div className="faint" style={{ fontSize: '0.8rem' }}>Learner state</div>
                  <div style={{ marginTop: '0.45rem', fontWeight: 650 }}>{s.state.replace(/_/g, ' ').toLowerCase()}</div>
                </div>
                <div>
                  <div className="faint" style={{ fontSize: '0.8rem' }}>Confidence</div>
                  <div className="stat-value" style={{ fontSize: '1.5rem' }}>{confidencePct(s.confidence)}</div>
                </div>
                <div>
                  <div className="faint" style={{ fontSize: '0.8rem' }}>Suggested</div>
                  <div style={{ marginTop: '0.45rem' }}>
                    {stateToStatus(s.state) === 'persistent' ? 'Assign focused practice' : stateToStatus(s.state) === 'review' ? 'Review the diagnosis' : 'Keep watching'}
                  </div>
                </div>
              </div>
              <div className="btn-row">
                <Link className="btn btn-primary" to={`/teacher/students/${s.student_id}`}>
                  Open {s.display_name}
                </Link>
                <Link className="btn btn-secondary" to={`/teacher/classroom/assign?student=${s.student_id}`}>
                  Assign practice
                </Link>
              </div>
            </section>
          ))
        )}
      </div>
    )
  }

  return (
    <div className="stack">
      <header className="page-header">
        <h1>Misconceptions</h1>
        <p>Areas currently tracked across {room.code}.</p>
      </header>
      <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {data.misconceptions.length === 0 ? (
          <p className="muted" style={{ padding: '1.25rem' }}>Nothing tracked yet — misconceptions appear as students submit attempts.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Area</th>
                <th>Students tracked</th>
                <th>Need attention</th>
                <th>Worst status</th>
              </tr>
            </thead>
            <tbody>
              {data.misconceptions.map((m) => (
                <tr key={m.misconception_id} className="clickable">
                  <td>
                    <Link to={`/teacher/misconceptions/${encodeURIComponent(m.misconception_id)}`} style={{ fontWeight: 650, display: 'block' }}>
                      {misconceptionLabel(m.misconception_id)}
                    </Link>
                  </td>
                  <td>{m.students.length}</td>
                  <td>{m.attention_count}</td>
                  <td>
                    <StatusBadge status={worstStatus(m.students)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <p className="muted" style={{ fontSize: '0.88rem' }}>
        Status legend: {statusLabel('persistent')} (recurs across related problems), {statusLabel('isolated')} (seen, not yet recurring),{' '}
        {statusLabel('improving')}, {statusLabel('review')} (mixed evidence — your call).
      </p>
    </div>
  )
}

export function MisconceptionsPage() {
  return <RequireClass>{(room) => <View room={room} />}</RequireClass>
}
