import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { CodeBlock } from '../../components/CodeBlock'
import { ErrorState, Loading, NotFound } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { display, formatDate, isRealMisconception, misconceptionLabel } from '../../lib/labels'
import { useApi } from '../../lib/useApi'

export function StudentSubmissionDetail() {
  const { submissionId = '' } = useParams()
  const id = Number(submissionId)
  const { data, error, loading, reload } = useApi(async () => {
    const submission = await api.submission(id)
    const [problem, tests, diags, hints] = await Promise.all([
      api.problem(submission.problem_id).catch(() => null),
      api.testResults(id),
      api.diagnoses(id),
      api.hints(id),
    ])
    return { submission, problem, tests, diag: [...diags].reverse().find((d) => d.mode === 'history_aware') ?? null, hints }
  }, [id])

  if (loading) return <Loading />
  if (error?.toLowerCase().includes('not found') || !Number.isInteger(id))
    return <NotFound title="Submission not found" body="This attempt is not in your history." back={{ to: '/student/submissions', label: 'Back to Submissions' }} />
  if (error || !data) return <ErrorState message={error ?? 'Not found'} onRetry={reload} />

  const { submission, problem, tests, diag, hints } = data
  const passed = tests.length > 0 && tests.every((t) => t.passed)
  const fail = tests.find((t) => !t.passed && t.test_type === 'visible')
  const area = diag && isRealMisconception(diag.primary_misconception) ? misconceptionLabel(diag.primary_misconception) : null

  return (
    <div className="stack">
      <header className="page-header">
        <p className="muted" style={{ marginBottom: '0.35rem' }}>
          <Link to="/student/submissions" className="btn btn-ghost" style={{ padding: 0 }}>
            ← Submissions
          </Link>
        </p>
        <div className="split-header">
          <div>
            <h1>{problem?.title ?? submission.problem_id}</h1>
            <p>
              Attempt {submission.attempt_number} · {formatDate(submission.submitted_at)}
              {area ? ` · ${area}` : ''}
            </p>
          </div>
          <StatusBadge status={passed ? 'correct' : 'incorrect'} />
        </div>
      </header>

      {problem ? (
        <section className="card">
          <div className="card-label">Problem</div>
          <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{problem.description}</p>
        </section>
      ) : null}

      <section className="card">
        <div className="card-label">Your solution</div>
        <div style={{ marginTop: '0.75rem' }}>
          <CodeBlock code={submission.source_code} />
        </div>
      </section>

      {fail ? (
        <div className="output-compare">
          <div className="output-box">
            <div className="label">Expected</div>
            <code>{display(fail.expected_output_json)}</code>
          </div>
          <div className="output-box">
            <div className="label">Your output</div>
            <code>{fail.actual_output_json == null && fail.error_type ? fail.error_type : display(fail.actual_output_json)}</code>
          </div>
        </div>
      ) : null}

      <section className="card">
        <div className="card-label">TraceLearn summary</div>
        <h2 style={{ margin: 0 }}>
          {passed ? 'All tests passed' : area ? `Possible ${area.toLowerCase()} misunderstanding` : `${tests.filter((t) => t.passed).length} of ${tests.length} tests passed`}
        </h2>
        {hints.length > 0 && (
          <div className="stack" style={{ gap: '0.4rem', marginTop: '0.85rem' }}>
            {hints.map((h) => (
              <div key={h.level} className="recommended-item">
                <strong>Hint {h.level}:</strong> {h.text}
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="btn-row">
        <Link className="btn btn-primary" to={`/student/problem/${encodeURIComponent(submission.problem_id)}`}>
          Try again
        </Link>
        {!passed && (
          <Link className="btn btn-secondary" to={`/student/result/${submission.id}`}>
            Open result & hints
          </Link>
        )}
        <Link className="btn btn-ghost" to="/student/submissions">
          All submissions
        </Link>
      </div>
    </div>
  )
}
