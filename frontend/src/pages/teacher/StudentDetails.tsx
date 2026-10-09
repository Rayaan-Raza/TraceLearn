import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { ErrorState, Loading, NotFound } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { Timeline } from '../../components/Timeline'
import { bySeverity, confidencePct, formatDate, misconceptionLabel, stateToStatus, statusExplanation, worstStatus } from '../../lib/labels'
import { conceptStories, submissionArea, useProblemTitles, useStudentBundle } from '../../lib/studentData'
import { useApi } from '../../lib/useApi'

export function StudentDetails() {
  const { studentId = '' } = useParams()
  const id = Number(studentId)
  const bundle = useStudentBundle(Number.isInteger(id) && id > 0 ? id : null)
  const problems = useApi(() => api.problems(), [])
  const title = useProblemTitles(problems.data)

  if (bundle.loading) return <Loading />
  if (bundle.error?.toLowerCase().includes('not found') || (!bundle.loading && !bundle.data))
    return <NotFound title="Student not found" body="This student is not in one of your classrooms." back={{ to: '/teacher/students', label: 'Back to Students' }} />
  if (bundle.error) return <ErrorState message={bundle.error} onRetry={bundle.reload} />

  const { profile, submissions } = bundle.data!
  const states = bySeverity(profile.learner_states)
  const status = worstStatus(states)
  const top = states[0]
  const stories = conceptStories(bundle.data, title)
  const persistent = states.filter((s) => stateToStatus(s.state) === 'persistent')

  return (
    <div className="stack">
      <header className="page-header">
        <p className="muted" style={{ marginBottom: '0.35rem' }}>
          <Link to={profile.is_synthetic ? '/teacher/research' : '/teacher/students'} className="btn btn-ghost" style={{ padding: 0 }}>
            ← {profile.is_synthetic ? 'Research' : 'Students'}
          </Link>
        </p>
        <div className="split-header">
          <div>
            <h1>
              {profile.display_name}
              {profile.is_synthetic ? <span className="badge isolated" style={{ marginLeft: 10, verticalAlign: 'middle' }}>Synthetic</span> : null}
            </h1>
            <p>
              {submissions.length} submissions · {new Set(submissions.filter((s) => s.passed).map((s) => s.problem_id)).size} problems solved
            </p>
          </div>
          <StatusBadge status={status} />
        </div>
      </header>

      <section className="card">
        <div className="card-label">Current Areas</div>
        {states.length === 0 ? (
          <p style={{ margin: 0 }}>No misconception tracked yet.</p>
        ) : (
          <>
            <h2>
              {misconceptionLabel(top.misconception_id)} {status === 'persistent' && <span className="badge persistent">High priority</span>}
            </h2>
            <p style={{ marginTop: '0.45rem' }}>{statusExplanation(status)}</p>
            <table className="table" style={{ marginTop: '0.85rem' }}>
              <thead>
                <tr>
                  <th>Concept</th>
                  <th>State</th>
                  <th>Confidence</th>
                  <th>Cross-problem evidence</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {states.map((s) => (
                  <tr key={s.id}>
                    <td>{misconceptionLabel(s.misconception_id)}</td>
                    <td>
                      <StatusBadge status={stateToStatus(s.state)} />
                    </td>
                    <td>{confidencePct(s.confidence)}</td>
                    <td>{s.cross_problem_support_count}</td>
                    <td>{formatDate(s.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>

      <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1.1rem 1.25rem 0.4rem' }}>
          <div className="card-label">Recent Activity</div>
        </div>
        {submissions.length === 0 ? (
          <p className="muted" style={{ padding: '0 1.25rem 1.25rem' }}>No submissions yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Problem</th>
                <th>Result</th>
                <th>Submitted</th>
                <th>Area</th>
              </tr>
            </thead>
            <tbody>
              {submissions.slice(0, 30).map((s) => (
                <tr key={s.id} className="clickable">
                  <td>
                    <Link to={`/teacher/submission/${s.id}`} style={{ fontWeight: 650, display: 'block' }}>
                      {s.problem_title} <span className="muted">#{s.attempt_number}</span>
                    </Link>
                  </td>
                  <td>
                    <StatusBadge status={s.passed ? 'correct' : 'incorrect'} />
                  </td>
                  <td>{formatDate(s.submitted_at)}</td>
                  <td>
                    {submissionArea(s) ?? '—'}
                    {s.requires_teacher_review ? <span className="badge review" style={{ marginLeft: 6 }}>Review</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {stories.map((c) => (
        <section className="card" key={c.misconceptionId}>
          <div className="card-label">What happened over time</div>
          <h2 style={{ marginBottom: '1rem' }}>{c.concept}</h2>
          <Timeline events={c.events} />
        </section>
      ))}

      {persistent.length > 0 && !profile.is_synthetic && (
        <section className="action-banner">
          <div className="card-label">Suggested Action</div>
          <h2 style={{ margin: '0 0 0.45rem' }}>
            Give {profile.display_name} a few focused problems on {persistent.map((s) => misconceptionLabel(s.misconception_id).toLowerCase()).join(' and ')}.
          </h2>
          <p>This mistake has recurred across related problems, which is TraceLearn's main signal for a persistent misconception.</p>
          <div className="btn-row">
            <Link className="btn btn-primary" to={`/teacher/classroom/assign?student=${profile.student_id}`}>
              Assign practice
            </Link>
          </div>
        </section>
      )}
    </div>
  )
}
