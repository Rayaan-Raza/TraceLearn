import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Diagnosis, EvidenceItem } from '../../api/types'
import { CodeBlock } from '../../components/CodeBlock'
import { ErrorState, Loading, NotFound } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { confidencePct, display, formatDate, KNOWN_MISCONCEPTIONS, misconceptionLabel } from '../../lib/labels'
import { useApi } from '../../lib/useApi'

const SOURCES = ['execution', 'test', 'static', 'sequence', 'history', 'context']

function DiagnosisCol({ title, d, changed }: { title: string; d: Diagnosis | null; changed?: boolean }) {
  return (
    <div className={`card compare-col${changed ? ' changed' : ''}`}>
      <div className="card-label">{title}</div>
      {d ? (
        <>
          <h3 style={{ margin: 0 }}>{misconceptionLabel(d.primary_misconception)}</h3>
          <p style={{ margin: '0.35rem 0 0' }}>
            Confidence {confidencePct(d.primary_confidence)} · uncertainty {d.uncertainty_level}
          </p>
          {d.alternative_misconception ? (
            <p className="muted" style={{ margin: '0.25rem 0 0' }}>
              Alternative: {misconceptionLabel(d.alternative_misconception)} ({confidencePct(d.alternative_confidence)})
            </p>
          ) : null}
          {d.requires_teacher_review ? <span className="badge review" style={{ marginTop: 8 }}>Requires review</span> : null}
        </>
      ) : (
        <p className="muted">Not diagnosed.</p>
      )}
    </div>
  )
}

function EvidenceGroups({ items }: { items: EvidenceItem[] }) {
  const groups = SOURCES.map((s) => ({ source: s, rows: items.filter((i) => i.source_type === s) })).filter((g) => g.rows.length)
  if (groups.length === 0) return <p className="muted">No evidence recorded.</p>
  return (
    <div className="stack" style={{ gap: '0.85rem' }}>
      {groups.map((g) => (
        <div key={g.source}>
          <div className="card-label" style={{ textTransform: 'capitalize' }}>{g.source}</div>
          <ul className="evidence-list">
            {g.rows.map((e) => (
              <li key={e.id}>
                <strong className={`dir-${e.direction}`}>{e.direction}</strong> · {e.description}
                {e.misconception_id ? <span className="muted"> → {misconceptionLabel(e.misconception_id)}</span> : null}
                <span className="muted"> · weight {e.weight.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

export function SubmissionDetail() {
  const { submissionId = '' } = useParams()
  const id = Number(submissionId)
  const { data, error, loading, reload, setData } = useApi(async () => {
    const submission = await api.submission(id)
    const [problem, tests, diags, evidence, reviews, profile] = await Promise.all([
      api.problem(submission.problem_id).catch(() => null),
      api.testResults(id),
      api.diagnoses(id),
      api.evidence(id),
      api.reviews(id),
      api.profile(submission.student_id),
    ])
    return { submission, problem, tests, diags, evidence, reviews, profile }
  }, [id])
  const [action, setAction] = useState('CONFIRM')
  const [corrected, setCorrected] = useState(KNOWN_MISCONCEPTIONS[0])
  const [comment, setComment] = useState('')
  const [msg, setMsg] = useState('')

  if (loading) return <Loading />
  if (error?.toLowerCase().includes('not found') || !Number.isInteger(id))
    return <NotFound title="Submission not found" body="This submission is not from one of your students." back={{ to: '/teacher/students', label: 'Students' }} />
  if (error || !data) return <ErrorState message={error ?? 'Not found'} onRetry={reload} />

  const { submission, problem, tests, diags, evidence, reviews, profile } = data
  const current = [...diags].reverse().find((d) => d.mode === 'current_only') ?? null
  const history = [...diags].reverse().find((d) => d.mode === 'history_aware') ?? null
  const changed =
    !!current && !!history &&
    (current.primary_misconception !== history.primary_misconception || Math.abs(current.primary_confidence - history.primary_confidence) > 0.05)
  const passed = tests.length > 0 && tests.every((t) => t.passed)
  const fail = tests.find((t) => !t.passed)

  async function review() {
    if (!history) return
    setMsg('')
    try {
      const r = await api.review(history.id, { action, corrected_misconception: action === 'CORRECT' ? corrected : null, comment: comment.trim() || undefined })
      setData((prev) => (prev ? { ...prev, reviews: [...prev.reviews, r] } : prev))
      setComment('')
      setMsg('Review saved. The original diagnosis is kept unchanged alongside it.')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Could not save review')
    }
  }

  return (
    <div className="stack">
      <header className="page-header">
        <p className="muted" style={{ marginBottom: '0.35rem' }}>
          <Link to={`/teacher/students/${submission.student_id}`} className="btn btn-ghost" style={{ padding: 0 }}>
            ← {profile.display_name}
          </Link>
        </p>
        <div className="split-header">
          <div>
            <h1>{problem?.title ?? submission.problem_id}</h1>
            <p>
              {profile.display_name} · attempt {submission.attempt_number} · {formatDate(submission.submitted_at)} · {tests.filter((t) => t.passed).length}/{tests.length} tests
            </p>
          </div>
          <StatusBadge status={passed ? 'correct' : 'incorrect'} />
        </div>
      </header>

      <section className="card">
        <div className="card-label">Student Code</div>
        <div style={{ marginTop: '0.75rem' }}>
          <CodeBlock code={submission.source_code} />
        </div>
      </section>

      {fail ? (
        <div className="output-compare">
          <div className="output-box">
            <div className="label">Expected ({fail.test_type})</div>
            <code>{display(fail.expected_output_json)}</code>
          </div>
          <div className="output-box">
            <div className="label">Received</div>
            <code>{fail.actual_output_json == null && fail.error_type ? fail.error_type : display(fail.actual_output_json)}</code>
          </div>
        </div>
      ) : null}

      <section className="card">
        <div className="split-header">
          <div>
            <div className="card-label">TraceLearn&apos;s Finding</div>
            <h2 style={{ margin: 0 }}>Current-only vs history-aware</h2>
          </div>
          {changed ? <span className="badge improving">History changed the result</span> : null}
        </div>
        <div className="grid-2" style={{ marginTop: '1rem' }}>
          <DiagnosisCol title="Current submission only" d={current} />
          <DiagnosisCol title="History-aware" d={history} changed={changed} />
        </div>
      </section>

      <section className="card">
        <div className="card-label">Evidence</div>
        <h2 style={{ margin: '0 0 0.85rem' }}>Why this was flagged</h2>
        <EvidenceGroups items={evidence} />
      </section>

      <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1.1rem 1.25rem 0.4rem' }}>
          <div className="card-label">All tests (including hidden)</div>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Test</th>
              <th>Type</th>
              <th>Expected</th>
              <th>Received</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {tests.map((t) => (
              <tr key={t.test_case_id}>
                <td>{t.name ?? t.test_case_id}</td>
                <td style={{ textTransform: 'capitalize' }}>{t.test_type}</td>
                <td><code>{display(t.expected_output_json)}</code></td>
                <td><code>{t.actual_output_json == null && t.error_type ? t.error_type : display(t.actual_output_json)}</code></td>
                <td><StatusBadge status={t.passed ? 'correct' : 'incorrect'} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card stack">
        <div>
          <div className="card-label">Teacher review</div>
          <h2 style={{ margin: 0 }}>Confirm or correct the diagnosis</h2>
        </div>
        {reviews.length > 0 && (
          <ul className="evidence-list">
            {reviews.map((r) => (
              <li key={r.id}>
                <strong>{r.action}</strong>
                {r.corrected_misconception ? ` → ${misconceptionLabel(r.corrected_misconception)}` : ''} · {formatDate(r.reviewed_at)}
                {r.comment ? <span className="muted"> — {r.comment}</span> : null}
              </li>
            ))}
          </ul>
        )}
        {history ? (
          <>
            <div className="form-row">
              <label className="field">
                <span>Action</span>
                <select value={action} onChange={(e) => setAction(e.target.value)}>
                  <option value="CONFIRM">Confirm</option>
                  <option value="REJECT">Reject</option>
                  <option value="CORRECT">Correct to…</option>
                  <option value="MARK_UNCERTAIN">Mark uncertain</option>
                </select>
              </label>
              {action === 'CORRECT' ? (
                <label className="field">
                  <span>Correct misconception</span>
                  <select value={corrected} onChange={(e) => setCorrected(e.target.value)}>
                    {[...KNOWN_MISCONCEPTIONS, 'NO_MISCONCEPTION'].map((m) => (
                      <option key={m} value={m}>
                        {misconceptionLabel(m)} ({m})
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
            </div>
            <label className="field">
              <span>Comment (optional)</span>
              <input value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} />
            </label>
            <div className="btn-row">
              <button type="button" className="btn btn-primary" onClick={() => void review()}>
                Save review
              </button>
            </div>
          </>
        ) : (
          <p className="muted">This submission has no diagnosis to review.</p>
        )}
        {msg ? <p className="toast-msg">{msg}</p> : null}
      </section>
    </div>
  )
}
