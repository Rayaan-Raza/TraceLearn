import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { useMe } from '../../context/AuthContext'
import { formatDate } from '../../lib/labels'
import { submissionArea } from '../../lib/studentData'
import { useApi } from '../../lib/useApi'

export function StudentSubmissionsPage() {
  const me = useMe()
  const navigate = useNavigate()
  const { data: subs, error, loading, reload } = useApi(() => api.studentSubmissions(me.student_id!), [me.student_id])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} onRetry={reload} />
  const attempts = subs!
  const passed = attempts.filter((a) => a.passed).length

  return (
    <div className="stack">
      <header className="page-header">
        <h1>Submissions</h1>
        <p>Everything you have attempted — pass/fail, timestamps, and solutions.</p>
      </header>

      <div className="grid-3">
        <section className="card">
          <div className="card-label">Total attempts</div>
          <div className="stat-value">{attempts.length}</div>
        </section>
        <section className="card">
          <div className="card-label">Passed</div>
          <div className="stat-value">{passed}</div>
        </section>
        <section className="card">
          <div className="card-label">Failed</div>
          <div className="stat-value">{attempts.length - passed}</div>
        </section>
      </div>

      <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1.1rem 1.25rem 0.4rem' }}>
          <div className="card-label">Attempt history</div>
          <h2 style={{ margin: 0 }}>All submissions</h2>
        </div>
        {attempts.length === 0 ? (
          <p className="muted" style={{ padding: '0.5rem 1.25rem 1.25rem' }}>
            No submissions yet. <Link to="/student/practice">Pick a problem →</Link>
          </p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Problem</th>
                <th>Result</th>
                <th>Submitted</th>
                <th>Area</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {attempts.map((s) => (
                <tr key={s.id} className="clickable" onClick={() => navigate(`/student/submissions/${s.id}`)}>
                  <td style={{ fontWeight: 650 }}>
                    {s.problem_title} <span className="muted">#{s.attempt_number}</span>
                  </td>
                  <td>
                    <StatusBadge status={s.passed ? 'correct' : 'incorrect'} />
                  </td>
                  <td>{formatDate(s.submitted_at)}</td>
                  <td>{submissionArea(s) ?? '—'}</td>
                  <td>
                    <span className="btn btn-ghost" style={{ padding: 0 }}>
                      View solution →
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
