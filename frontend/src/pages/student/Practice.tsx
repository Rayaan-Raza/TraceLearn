import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { useMe } from '../../context/AuthContext'
import { formatDate } from '../../lib/labels'
import { derive, problemStatus, recommend, useStudentBundle } from '../../lib/studentData'
import { useApi } from '../../lib/useApi'

export function PracticePage() {
  const me = useMe()
  const navigate = useNavigate()
  const bundle = useStudentBundle(me.student_id)
  const extra = useApi(() => Promise.all([api.problems(), api.myAssignments()]), [])

  if (bundle.loading || extra.loading) return <Loading />
  if (bundle.error || extra.error) return <ErrorState message={(bundle.error || extra.error)!} onRetry={() => { bundle.reload(); extra.reload() }} />

  const [problems, assignments] = extra.data!
  const d = derive(bundle.data)
  const active = assignments.filter((a) => a.state === 'active')
  const assignedIds = new Set(active.map((a) => a.problem_id))
  const recIds = new Set(recommend(problems, bundle.data, d, assignments).map((p) => p.id))
  const open = (id: string) => navigate(`/student/problem/${encodeURIComponent(id)}`)

  return (
    <div className="stack">
      <header className="page-header">
        <h1>Practice</h1>
        <p>Pick a problem to continue learning — including class assignments.</p>
      </header>

      {active.length > 0 && (
        <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '1.1rem 1.25rem 0.4rem' }}>
            <div className="card-label">Assigned by teacher</div>
            <h2 style={{ margin: 0 }}>Classroom problems</h2>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Problem</th>
                <th>Assigned</th>
                <th>Due</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {active.map((a) => (
                <tr key={a.id} className="clickable" onClick={() => open(a.problem_id)}>
                  <td style={{ fontWeight: 650 }}>{a.problem_title}</td>
                  <td>{formatDate(a.assigned_at)}</td>
                  <td>{a.due_date || '—'}</td>
                  <td>
                    <StatusBadge status={d.solvedProblemIds.has(a.problem_id) ? 'completed' : 'recommended'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1.1rem 1.25rem 0.4rem' }}>
          <div className="card-label">Problem set</div>
          <h2 style={{ margin: 0 }}>All practice problems</h2>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Problem</th>
              <th>Topic</th>
              <th>Difficulty</th>
              <th>Language</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {problems.map((p) => (
              <tr key={p.id} className="clickable" onClick={() => open(p.id)}>
                <td style={{ fontWeight: 650 }}>
                  {p.title}
                  {assignedIds.has(p.id) ? (
                    <span className="badge recommended" style={{ marginLeft: 8 }}>
                      Assigned
                    </span>
                  ) : null}
                </td>
                <td>{p.topic || '—'}</td>
                <td>{p.difficulty}</td>
                <td>{p.language === 'cpp' ? 'C++' : 'Python'}</td>
                <td>
                  <StatusBadge status={problemStatus(p.id, d, assignedIds, recIds)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
