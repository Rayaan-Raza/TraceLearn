import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Diagnosis, Hint, RunResult, Submission, TestResult } from '../../api/types'
import { CodeBlock } from '../../components/CodeBlock'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { display, formatDate, isRealMisconception, misconceptionLabel } from '../../lib/labels'
import { useApi } from '../../lib/useApi'

interface Loaded {
  submission: Submission
  problemTitle: string
  tests: TestResult[]
  history: Diagnosis | null
  hints: Hint[]
  stderr: string
  status: string
}

export function ResultPage() {
  const { submissionId = '' } = useParams()
  const id = Number(submissionId)
  const location = useLocation()
  const fresh = (location.state as { result?: RunResult } | null)?.result

  const { data, error, loading, reload, setData } = useApi<Loaded>(async () => {
    const submission = await api.submission(id)
    const [problem, tests, diags, hints] = await Promise.all([
      api.problem(submission.problem_id).catch(() => null),
      fresh ? Promise.resolve(fresh.test_results) : api.testResults(id),
      fresh ? Promise.resolve([fresh.history_aware].filter(Boolean) as Diagnosis[]) : api.diagnoses(id),
      api.hints(id),
    ])
    return {
      submission,
      problemTitle: problem?.title ?? submission.problem_id,
      tests,
      history: [...diags].reverse().find((d) => d.mode === 'history_aware') ?? null,
      hints,
      stderr: fresh?.stderr ?? '',
      status: fresh?.execution_status ?? submission.execution_status ?? 'unknown',
    }
  }, [id])
  const [hintBusy, setHintBusy] = useState(false)
  const [hintError, setHintError] = useState('')

  if (!Number.isInteger(id) || id < 1) return <ErrorState message="Invalid submission." back={{ to: '/student/submissions', label: 'Submissions' }} />
  if (loading) return <Loading />
  if (error || !data) return <ErrorState message={error ?? 'Not found'} onRetry={reload} back={{ to: '/student/submissions', label: 'Submissions' }} />

  const { submission, tests, history, hints } = data
  const total = tests.length
  const passedCount = tests.filter((t) => t.passed).length
  const allPassed = total > 0 && passedCount === total
  const firstVisibleFail = tests.find((t) => !t.passed && t.test_type === 'visible')
  const hiddenFails = tests.filter((t) => !t.passed && t.test_type !== 'visible').length
  const current = hints[hints.length - 1]
  const maxLevel = current?.max_level ?? 1
  const area = history && isRealMisconception(history.primary_misconception) ? misconceptionLabel(history.primary_misconception) : null

  async function nextHint() {
    setHintBusy(true)
    setHintError('')
    try {
      const h = await api.nextHint(id)
      setData((prev) => (prev ? { ...prev, hints: [...prev.hints.filter((x) => x.level !== h.level), h] } : prev))
    } catch (e) {
      setHintError(e instanceof Error ? e.message : 'Could not load hint')
    } finally {
      setHintBusy(false)
    }
  }

  const headline =
    data.status === 'syntax_error'
      ? 'Your code did not compile'
      : data.status === 'timeout'
        ? 'Your code took too long'
        : data.status === 'system_error'
          ? 'We could not run your code'
          : allPassed
            ? 'All tests passed'
            : 'Not quite yet'

  return (
    <div className="stack">
      <header className="page-header">
        <div className="split-header">
          <div>
            <h1>{headline}</h1>
            <p>
              TraceLearn compared your output with the expected results for <strong>{data.problemTitle}</strong>
              {total ? ` — ${passedCount} of ${total} tests passed.` : '.'}
            </p>
          </div>
          <div className="muted" style={{ fontSize: '0.88rem' }}>
            Attempt {submission.attempt_number} · {formatDate(submission.submitted_at)}
          </div>
        </div>
      </header>

      {data.stderr && !allPassed ? (
        <section className="card">
          <div className="card-label">{data.status === 'syntax_error' ? 'Compiler output' : 'Error output'}</div>
          <pre className="stderr-box">{data.stderr}</pre>
        </section>
      ) : null}

      {firstVisibleFail ? (
        <div className="output-compare">
          <div className="output-box">
            <div className="label">Expected</div>
            <code>{display(firstVisibleFail.expected_output_json)}</code>
          </div>
          <div className="output-box">
            <div className="label">Your output</div>
            <code>{firstVisibleFail.error_type && firstVisibleFail.actual_output_json == null ? firstVisibleFail.error_type : display(firstVisibleFail.actual_output_json)}</code>
          </div>
        </div>
      ) : !allPassed && hiddenFails > 0 ? (
        <section className="card">
          <p style={{ margin: 0 }}>
            Your code passed the visible examples but failed {hiddenFails} hidden test{hiddenFails === 1 ? '' : 's'}. Think about edge cases.
          </p>
        </section>
      ) : null}

      {total > 0 && (
        <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Test</th>
                <th>Type</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((t, i) => (
                <tr key={t.test_case_id}>
                  <td>{t.name ?? `Test ${i + 1}`}</td>
                  <td style={{ textTransform: 'capitalize' }}>{t.test_type ?? '—'}</td>
                  <td>
                    <StatusBadge status={t.passed ? 'correct' : 'incorrect'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {!allPassed && (
        <section className="card">
          <div className="card-label">What TraceLearn noticed</div>
          <h2>{area ? `Possible ${area.toLowerCase()} misunderstanding` : 'No clear pattern yet'}</h2>
          <p style={{ marginTop: '0.55rem' }}>
            {history?.requires_teacher_review
              ? 'The evidence is mixed, so your teacher may take a look at this attempt.'
              : area
                ? 'TraceLearn looked at this attempt together with your earlier attempts on related problems.'
                : 'Keep going — patterns become clearer over several attempts.'}
          </p>
          <div style={{ marginTop: '1rem' }}>
            <CodeBlock code={submission.source_code} />
          </div>
        </section>
      )}

      {!allPassed && (
        <section className="hint-panel">
          <div className="split-header">
            <div>
              <div className="card-label">{current ? `Hint · Level ${current.level} of ${maxLevel}` : 'Hints'}</div>
              <h2 style={{ margin: 0 }}>{current ? (current.level === 1 ? 'Guiding question' : current.level === 2 ? 'Concept reminder' : 'Where to look') : 'Need a nudge?'}</h2>
            </div>
          </div>
          {current ? (
            <>
              <div className="hint-levels" aria-hidden>
                {Array.from({ length: maxLevel }, (_, i) => i + 1).map((lvl) => (
                  <div key={lvl} className={`hint-dot${lvl < current.level ? ' done' : lvl === current.level ? ' active' : ''}`} />
                ))}
              </div>
              <blockquote className="quote">{current.text}</blockquote>
            </>
          ) : (
            <p style={{ marginTop: '0.5rem' }}>Hints get more specific each time you ask.</p>
          )}
          {hintError ? <p className="form-error">{hintError}</p> : null}
          <div className="btn-row">
            {!current || current.level < maxLevel ? (
              <button type="button" className="btn btn-primary" onClick={() => void nextHint()} disabled={hintBusy}>
                {current ? 'Next Hint' : 'Show a hint'}
              </button>
            ) : (
              <span className="badge completed">All hint levels shown</span>
            )}
            <Link className="btn btn-secondary" to={`/student/problem/${encodeURIComponent(submission.problem_id)}`}>
              Try Again
            </Link>
            <Link className="btn btn-ghost" to="/student/progress">
              View Progress
            </Link>
          </div>
        </section>
      )}

      {allPassed && (
        <div className="btn-row">
          <Link className="btn btn-primary" to="/student/practice">
            Next problem
          </Link>
          <Link className="btn btn-secondary" to="/student/progress">
            View Progress
          </Link>
        </div>
      )}

      <section className="card">
        <div className="card-label">Why this matters</div>
        <h3 style={{ margin: 0 }}>Patterns over single attempts</h3>
        <p style={{ marginTop: '0.5rem' }}>
          TraceLearn is not only looking at this answer. It also considers your previous attempts on related problems, so one mistake is
          treated as evidence — not a label.
        </p>
      </section>
    </div>
  )
}
