import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { BarChart, TimelineChart } from '../../components/MisconceptionCharts'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { useMe } from '../../context/AuthContext'
import { derive, problemStatus, recommend, useStudentBundle } from '../../lib/studentData'
import { formatDate } from '../../lib/labels'
import { useApi } from '../../lib/useApi'

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export function StudentDashboard() {
  const me = useMe()
  const bundle = useStudentBundle(me.student_id)
  const extra = useApi(() => Promise.all([api.practiceProblems(), api.myAssignments()]), [])

  if (bundle.loading || extra.loading) return <Loading />
  if (bundle.error || extra.error) return <ErrorState message={(bundle.error || extra.error)!} onRetry={() => { bundle.reload(); extra.reload() }} />

  const [problems, assignments] = extra.data!
  const d = derive(bundle.data)
  const recommended = recommend(problems, bundle.data, d, assignments)
  const recIds = new Set(recommended.map((p) => p.id))
  const assignedIds = new Set(assignments.filter((a) => a.state === 'active').map((a) => a.problem_id))
  const activeAssignments = assignments.filter((a) => a.state === 'active')
  const firstName = (me.display_name || 'there').split(' ')[0]
  const focusClass = d.focus?.status === 'improving' ? 'improving' : d.focus?.status === 'isolated' ? 'isolated' : ''

  return (
    <div className="stack">
      <header className="page-header">
        <h1 className="welcome">
          {greeting()}, {firstName}
        </h1>
      </header>

      <div className="grid-2">
        <section className={`card focus-card ${focusClass}`}>
          <div className="card-label">Focus Area</div>
          {d.focus ? (
            <>
              <h2>{d.focus.label}</h2>
              <div style={{ margin: '0.55rem 0 0.75rem' }}>
                <StatusBadge status={d.focus.status} />
                {d.focus.status === 'persistent' && (
                  <span className="badge needs-practice" style={{ marginLeft: 8 }}>
                    Needs more practice
                  </span>
                )}
              </div>
              <p>{d.focus.explanation}</p>
            </>
          ) : null}
          <div className="btn-row">
            <Link className="btn btn-primary" to="/student/practice">
              Start Practice
            </Link>
            <Link className="btn btn-secondary" to="/student/progress">
              View Progress
            </Link>
          </div>
        </section>

        <section className="card">
          <div className="card-label">Your Progress</div>
          <div className="stack" style={{ gap: '0.85rem', marginTop: '0.5rem' }}>
            <div>
              <div className="faint" style={{ fontSize: '0.8rem' }}>Concepts improving</div>
              <div className="stat-value">{d.counts.improving}</div>
            </div>
            <div>
              <div className="faint" style={{ fontSize: '0.8rem' }}>Concepts needing practice</div>
              <div className="stat-value">{d.counts.needingPractice}</div>
            </div>
            <div>
              <div className="faint" style={{ fontSize: '0.8rem' }}>Problems solved</div>
              <div className="stat-value">{d.counts.solved}</div>
            </div>
          </div>
        </section>
      </div>

      <div className="grid-2">
        <BarChart title="Concepts by state" points={d.stateCounts} axisNote="X: state · Y: count" />
        <TimelineChart title="Mistake timeline" points={d.mistakeTimeline} />
      </div>

      {activeAssignments.length > 0 && (
        <section className="card">
          <div className="card-label">Assigned by your teacher</div>
          <h2 style={{ margin: 0 }}>Class assignments</h2>
          <div className="problem-list" style={{ marginTop: '1rem' }}>
            {activeAssignments.map((a) => (
              <Link key={a.id} to={`/student/problem/${encodeURIComponent(a.problem_id)}`} className="problem-row" style={{ gridTemplateColumns: '1.6fr 1fr 1fr' }}>
                <div>
                  <div className="title">{a.problem_title}</div>
                  <div className="meta">{a.due_date ? `Due ${a.due_date}` : a.classroom_name}</div>
                </div>
                <div className="meta">Assigned {formatDate(a.assigned_at)}</div>
                <div>
                  <span className="badge recommended">Assigned</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="card">
        <div className="split-header">
          <div>
            <div className="card-label">Recommended Practice</div>
            <h2 style={{ margin: 0 }}>Next problems for you</h2>
          </div>
          <Link className="btn btn-secondary" to="/student/practice">
            See all
          </Link>
        </div>
        {recommended.length === 0 ? (
          <p className="muted" style={{ marginTop: '0.75rem' }}>All problems solved.</p>
        ) : (
          <div className="problem-list" style={{ marginTop: '1rem' }}>
            {recommended.map((p) => (
              <Link key={p.id} to={`/student/problem/${encodeURIComponent(p.id)}`} className="problem-row" style={{ gridTemplateColumns: '1.6fr 0.8fr 1fr' }}>
                <div>
                  <div className="title">{p.title}</div>
                  <div className="meta">{p.topic}</div>
                </div>
                <div className="meta">{p.difficulty}</div>
                <div>
                  <StatusBadge status={problemStatus(p.id, d, assignedIds, recIds)} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
