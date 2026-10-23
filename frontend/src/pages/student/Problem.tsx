import { lazy, Suspense, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { ErrorState, Loading, NotFound } from '../../components/PageState'
import { useMe } from '../../context/AuthContext'
import { display, testInput } from '../../lib/labels'
import { useApi } from '../../lib/useApi'

const CodeEditor = lazy(() => import('../../components/CodeEditor'))

function draftKey(userId: number, problemId: string) {
  return `tl_draft_${userId}_${problemId}`
}

export function ProblemPage() {
  const { problemId = '' } = useParams()
  const me = useMe()
  const navigate = useNavigate()
  const { data, error, loading, reload } = useApi(
    () => Promise.all([api.problem(problemId), api.myAssignments()]),
    [problemId],
  )
  const [code, setCode] = useState('')
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState('')

  useEffect(() => {
    if (!data) return
    let draft: string | null = null
    try {
      draft = sessionStorage.getItem(draftKey(me.user_id, problemId))
    } catch {
      /* storage unavailable */
    }
    setCode(draft ?? data[0].starter_code)
  }, [data, me.user_id, problemId])

  function updateCode(v: string) {
    setCode(v)
    try {
      sessionStorage.setItem(draftKey(me.user_id, problemId), v)
    } catch {
      /* storage unavailable */
    }
  }

  async function submit() {
    setRunError('')
    setRunning(true)
    try {
      const sub = await api.submit(problemId, code)
      const result = await api.runAndAnalyze(sub.id)
      navigate(`/student/result/${sub.id}`, { state: { result } })
    } catch (e) {
      setRunError(e instanceof Error ? e.message : 'Could not run your code')
    } finally {
      setRunning(false)
    }
  }

  if (loading) return <Loading />
  if (error) {
    if (error && (error.includes('not found') || error.includes('Not found')))
      return <NotFound title="Problem not found" body="This problem may not be assigned to you." back={{ to: '/student/practice', label: 'Back to Practice' }} />
    return <ErrorState message={error} onRetry={reload} />
  }

  const [problem, assignments] = data!
  const assignment = assignments.find((a) => a.problem_id === problemId && a.state === 'active')
  const visible = problem.test_cases.filter((t) => t.test_type === 'visible')
  const hiddenCount = problem.test_cases.length - visible.length
  const lang = problem.language === 'cpp' ? 'C++' : 'Python'

  return (
    <div className="stack">
      <header className="page-header">
        <p className="muted" style={{ marginBottom: '0.35rem' }}>
          <Link to="/student/practice" className="btn btn-ghost" style={{ padding: 0 }}>
            ← Practice
          </Link>
        </p>
        <div className="split-header">
          <div>
            <h1>{problem.title}</h1>
            <p style={{ whiteSpace: 'pre-wrap' }}>{problem.description}</p>
          </div>
          {assignment?.due_date ? <span className="badge recommended">Due {assignment.due_date}</span> : null}
        </div>
      </header>

      {visible.length > 0 && (
        <section className="card">
          <div className="card-label">Test cases</div>
          <div className="stack" style={{ gap: '0.45rem', marginTop: '0.5rem' }}>
            {visible.map((tc, i) => (
              <div className="recommended-item" key={tc.id}>
                <strong>Case {i + 1}:</strong> input <code>{testInput(tc.input_json)}</code> → expected <code>{display(tc.expected_output)}</code>
              </div>
            ))}
            {hiddenCount > 0 ? (
              <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.88rem' }}>
                Plus {hiddenCount} hidden test{hiddenCount === 1 ? '' : 's'}.
              </p>
            ) : null}
          </div>
        </section>
      )}

      <section className="card">
        <div className="split-header">
          <div>
            <div className="card-label">Your Code</div>
            <h2 style={{ margin: 0 }}>{lang} editor</h2>
          </div>
          <div className="muted" style={{ fontSize: '0.85rem' }}>
            {problem.topic} · {problem.difficulty}
            {problem.language !== 'cpp' && problem.function_name ? ` · implement ${problem.function_name}()` : ''}
          </div>
        </div>
        <div style={{ marginTop: '1rem' }}>
          <Suspense fallback={<Loading label="Loading editor…" />}>
            <CodeEditor value={code} onChange={updateCode} language={problem.language} />
          </Suspense>
        </div>
        {runError ? (
          <p className="form-error" role="alert" style={{ marginTop: '0.75rem' }}>
            {runError}
          </p>
        ) : null}
        <div className="btn-row">
          <button type="button" className="btn btn-primary" onClick={() => void submit()} disabled={running || !code.trim()}>
            {running ? 'Running your code…' : 'Run / Submit'}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => updateCode(problem.starter_code)}
            disabled={running}
          >
            Reset to starter code
          </button>
          <Link className="btn btn-secondary" to="/student/practice">
            Back to Practice
          </Link>
        </div>
      </section>
    </div>
  )
}

