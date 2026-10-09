import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { Classroom } from '../../api/types'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { misconceptionLabel, worstStatus } from '../../lib/labels'
import { useApi } from '../../lib/useApi'
import { CreateClassForm, JoinCodeCard, RequireClass } from './shared'

function Overview({ room }: { room: Classroom }) {
  const { data, error, loading, reload } = useApi(() => api.overview(room.id), [room.id])
  if (loading) return <Loading />
  if (error || !data) return <ErrorState message={error ?? 'Could not load'} onRetry={reload} />
  const items = data.misconceptions
  const maxCount = Math.max(...items.map((m) => m.students.length), 1)

  return (
    <div className="stack">
      <header className="page-header">
        <h1>
          {room.code} — {room.name}
        </h1>
        <p>{room.teacher_name}</p>
      </header>

      <div className="grid-3">
        <section className="card">
          <div className="card-label">Students</div>
          <div className="stat-value">{data.totals.students}</div>
        </section>
        <section className="card">
          <div className="card-label">Problems Completed</div>
          <div className="stat-value">{data.totals.problems_completed}</div>
        </section>
        <section className="card">
          <div className="card-label">Areas Needing Attention</div>
          <div className="stat-value">{data.totals.areas_needing_attention}</div>
        </section>
      </div>

      {data.totals.students === 0 ? <JoinCodeCard classroom={data.classroom} /> : null}

      <section className="card">
        <div className="split-header">
          <div>
            <div className="card-label">Class Misconceptions</div>
            <h2 style={{ margin: 0 }}>Where the class needs attention</h2>
          </div>
          <Link className="btn btn-secondary" to="/teacher/misconceptions">
            Open details
          </Link>
        </div>
        {items.length === 0 ? (
          <p className="muted" style={{ marginTop: '0.85rem' }}>
            No misconceptions tracked yet. They appear once students submit attempts.
          </p>
        ) : (
          <>
            <div className="chart">
              {items.map((m) => {
                const n = m.students.length
                const width = n === 0 ? 0 : Math.max((n / maxCount) * 100, 18)
                return (
                  <Link key={m.misconception_id} to={`/teacher/misconceptions/${encodeURIComponent(m.misconception_id)}`} className="chart-row" style={{ textDecoration: 'none' }}>
                    <div className="chart-label">{misconceptionLabel(m.misconception_id)}</div>
                    <div className="chart-bar-track">
                      <div className={`chart-bar${m.attention_count ? '' : ' zero'}`} style={{ width: `${width}%` }} />
                    </div>
                    <div className="chart-count">{n}</div>
                  </Link>
                )
              })}
            </div>
            <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {items.map((m) => (
                <span key={m.misconception_id} style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                  <span className="muted" style={{ fontSize: '0.82rem' }}>{misconceptionLabel(m.misconception_id)}:</span>
                  <StatusBadge status={worstStatus(m.students)} />
                </span>
              ))}
            </div>
            <div className="chart-axis-note">Bar length: students with this concept tracked · highlighted: at least one needs attention</div>
          </>
        )}
      </section>
    </div>
  )
}

export function ClassOverview() {
  return (
    <RequireClass>
      {(room) => (
        <>
          <Overview room={room} />
          <details className="card" style={{ marginTop: '1.25rem' }}>
            <summary className="card-label" style={{ cursor: 'pointer' }}>
              Add another classroom
            </summary>
            <div style={{ marginTop: '0.85rem' }}>
              <CreateClassForm />
            </div>
          </details>
        </>
      )}
    </RequireClass>
  )
}
