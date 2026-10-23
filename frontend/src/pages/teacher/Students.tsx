import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { Classroom } from '../../api/types'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { bySeverity, misconceptionLabel, teacherLabel, worstStatus } from '../../lib/labels'
import { useApi } from '../../lib/useApi'
import { RequireClass } from './shared'

function List({ room }: { room: Classroom }) {
  const { data, error, loading, reload } = useApi(() => api.overview(room.id), [room.id])
  if (loading) return <Loading />
  if (error || !data) return <ErrorState message={error ?? 'Could not load'} onRetry={reload} />

  return (
    <div className="stack">
      <header className="page-header">
        <h1>Students</h1>
        <p>
          {data.students.length} student{data.students.length === 1 ? '' : 's'} in {room.code}.
        </p>
      </header>
      {data.students.length === 0 ? (
        <section className="card">
          <p className="muted" style={{ margin: 0 }}>
            No students yet. Share the join code from the <Link to="/teacher/classroom">Classroom</Link> page.
          </p>
        </section>
      ) : (
        <div className="stack">
          {data.students.map((s) => {
            const status = worstStatus(s.states)
            const top = bySeverity(s.states)[0]
            return (
              <Link key={s.id} to={`/teacher/students/${s.id}`} className="card interactive" style={{ textDecoration: 'none' }}>
                <div className="split-header">
                  <div>
                    <h2 style={{ margin: 0 }}>{s.display_name}</h2>
                    <p style={{ marginTop: '0.35rem' }}>
                      {top ? `${misconceptionLabel(top.misconception_id)} — ${top.state.replace(/_/g, ' ').toLowerCase()}` : 'No continuing misconception'} · {s.solved_problems} solved
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                    <span className={`badge ${status}`}>{teacherLabel(status)}</span>
                    <StatusBadge status={status} />
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function StudentsPage() {
  return <RequireClass>{(room) => <List room={room} />}</RequireClass>
}
