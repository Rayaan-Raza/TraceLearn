import Editor from '@monaco-editor/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchProblem, fetchProblems, fetchStudents, runAndAnalyze } from '../api/client'
import { useSession } from '../context/SessionContext'
import type { ProblemDetail, ProblemSummary } from '../types'

function hintText(hint: unknown): string {
  if (!hint) return '—'
  if (typeof hint === 'string') return hint
  if (typeof hint === 'object' && hint !== null && 'text' in hint) {
    return String((hint as { text?: string }).text ?? JSON.stringify(hint))
  }
  return JSON.stringify(hint)
}

export function StudentSubmissionScreen() {
  const {
    students,
    setStudents,
    selectedStudentId,
    setSelectedStudentId,
    lastResult,
    setLastResult,
    loadingSession,
    setLoadingSession,
  } = useSession()

  const [problems, setProblems] = useState<ProblemSummary[]>([])
  const [problemId, setProblemId] = useState<string>('')
  const [problemDetail, setProblemDetail] = useState<ProblemDetail | null>(null)
  const [code, setCode] = useState('# Select a problem to load starter code')
  const [error, setError] = useState<string | null>(null)
  const editorRef = useRef<{ getValue: () => string } | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        const [p, s] = await Promise.all([fetchProblems(), fetchStudents()])
        setProblems(p)
        setStudents(s)
        if (s.length && selectedStudentId == null) setSelectedStudentId(s[0].id)
        if (p.length && !problemId) setProblemId(p[0].id)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load catalog')
      }
    })()
  }, [problemId, selectedStudentId, setSelectedStudentId, setStudents])

  useEffect(() => {
    if (!problemId) return
    void (async () => {
      try {
        const detail = await fetchProblem(problemId)
        setProblemDetail(detail)
        setCode(detail.starter_code)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load problem')
      }
    })()
  }, [problemId])

  const selectedStudent = students.find((s) => s.id === selectedStudentId)

  const handleRun = useCallback(async () => {
    setError(null)
    if (!selectedStudent || !problemId) {
      setError('Select a student and problem')
      return
    }
    const editorCode = editorRef.current?.getValue() ?? code
    setLoadingSession(true)
    try {
      const result = await runAndAnalyze(selectedStudent.id, problemId, editorCode)
      setLastResult(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Run failed')
    } finally {
      setLoadingSession(false)
    }
  }, [code, problemId, selectedStudent, setLastResult, setLoadingSession])

  const currentOnly = lastResult?.current_only ?? lastResult?.diagnoses?.find((d) => d.mode === 'current_only')
  const historyAware = lastResult?.history_aware ?? lastResult?.diagnoses?.find((d) => d.mode === 'history_aware')

  return (
    <div className="screen submission-screen">
      <header className="screen-header">
        <h2>Student Submission</h2>
      </header>

      <div className="toolbar">
        <label>
          Student
          <select
            value={selectedStudentId ?? ''}
            onChange={(e) => setSelectedStudentId(Number(e.target.value))}
          >
            {students.map((s) => (
              <option key={s.id} value={s.id}>
                {s.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Problem
          <select value={problemId} onChange={(e) => setProblemId(e.target.value)}>
            {problems.map((p) => (
              <option key={p.id} value={p.id}>
                {p.id} — {p.title}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="primary" onClick={() => void handleRun()} disabled={loadingSession}>
          {loadingSession ? 'Running…' : 'Run & Analyze'}
        </button>
      </div>

      {problemDetail && (
        <section className="problem-description">
          <h3>{problemDetail.title}</h3>
          <pre className="description-body">{problemDetail.description}</pre>
        </section>
      )}

      {error && <div className="banner error">{error}</div>}

      <div className="submission-layout">
        <div className="editor-pane">
          <Editor
            height="450px"
            language="python"
            value={code}
            onChange={(v) => setCode(v ?? '')}
            onMount={(editor) => {
              editorRef.current = editor
            }}
            options={{
              fontSize: 14,
              minimap: { enabled: false },
              lineNumbers: 'on',
              autoIndent: 'full',
              bracketPairColorization: { enabled: true },
              matchBrackets: 'always',
              tabSize: 4,
              insertSpaces: true,
            }}
          />
        </div>

        <aside className="results-pane">
          <h3>Results</h3>
          {lastResult ? (
            <>
              <p>
                <strong>Submission</strong> #{lastResult.submission_id}
                {lastResult.attempt_number != null && ` · attempt ${lastResult.attempt_number}`}
              </p>
              <p>
                <strong>Runtime</strong>{' '}
                {lastResult.runtime_ms != null ? `${lastResult.runtime_ms.toFixed(1)} ms` : '—'}
              </p>
              <div className="io-block">
                <h4>stdout</h4>
                <pre>{lastResult.stdout || '—'}</pre>
                <h4>stderr</h4>
                <pre className="stderr">{lastResult.stderr || '—'}</pre>
              </div>

              <h4>Test results</h4>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Pass</th>
                  </tr>
                </thead>
                <tbody>
                  {lastResult.test_results.map((tr) => (
                    <tr key={tr.test_case_id} className={tr.passed ? 'pass' : 'fail'}>
                      <td>{tr.test_case_name ?? tr.test_case_id}</td>
                      <td>{tr.passed ? '✓' : '✗'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="diagnosis-cards">
                <div className="card">
                  <h4>Current-only diagnosis</h4>
                  {currentOnly ? (
                    <>
                      <p>{currentOnly.primary_misconception}</p>
                      <p className="muted">confidence {(currentOnly.primary_confidence * 100).toFixed(0)}%</p>
                    </>
                  ) : (
                    <p className="muted">—</p>
                  )}
                </div>
                <div className="card">
                  <h4>History-aware diagnosis</h4>
                  {historyAware ? (
                    <>
                      <p>{historyAware.primary_misconception}</p>
                      <p className="muted">confidence {(historyAware.primary_confidence * 100).toFixed(0)}%</p>
                    </>
                  ) : (
                    <p className="muted">—</p>
                  )}
                </div>
              </div>

              <div className="card hint-card">
                <h4>Hint</h4>
                <p>{hintText(lastResult.hint)}</p>
              </div>
            </>
          ) : (
            <p className="muted">Run code to see execution and diagnosis output.</p>
          )}
        </aside>
      </div>
    </div>
  )
}
