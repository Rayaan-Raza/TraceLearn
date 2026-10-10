import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Classroom, NewTestCase } from '../../api/types'
import { ErrorState, Loading } from '../../components/PageState'
import { useClasses } from '../../context/ClassContext'
import { useApi } from '../../lib/useApi'
import { RequireClass } from './shared'

type Mode = 'dataset' | 'create'

const STARTER = '#include <iostream>\nusing namespace std;\n\nint main() {\n    int n, k;\n    cin >> n >> k;\n\n    return 0;\n}\n'

function AssignForm({ room }: { room: Classroom }) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { refresh } = useClasses()
  const { data, error, loading, reload } = useApi(() => Promise.all([api.practiceProblems(), api.members(room.id)]), [room.id])

  const [mode, setMode] = useState<Mode>('dataset')
  const [selectedId, setSelectedId] = useState('')
  const [selectedStudents, setSelectedStudents] = useState<number[]>([])
  const [dueDate, setDueDate] = useState('')
  const [notes, setNotes] = useState('')
  const [toast, setToast] = useState('')
  const [busy, setBusy] = useState(false)

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [topic, setTopic] = useState('Loops')
  const [difficulty, setDifficulty] = useState('Easy')
  const [starterCode, setStarterCode] = useState(STARTER)
  const [testCases, setTestCases] = useState<NewTestCase[]>([
    { input: '10 2', expected: '2 4 6 8 10', visible: true },
    { input: '15 5', expected: '5 10 15', visible: false },
  ])

  useEffect(() => {
    if (!data) return
    const [problems, members] = data
    if (!selectedId && problems[0]) setSelectedId(problems[0].id)
    const pre = Number(params.get('student'))
    setSelectedStudents(pre && members.some((m) => m.student_id === pre) ? [pre] : members.map((m) => m.student_id))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  const problems = useMemo(() => data?.[0] ?? [], [data])
  const members = data?.[1] ?? []
  const selected = problems.find((p) => p.id === selectedId)

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} onRetry={reload} />

  const toggle = (id: number) => setSelectedStudents((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]))
  const updateTc = (i: number, patch: Partial<NewTestCase>) => setTestCases((prev) => prev.map((tc, j) => (j === i ? { ...tc, ...patch } : tc)))

  async function handleAssign() {
    setToast('')
    if (members.length === 0) return setToast('No students have joined this classroom yet. Share the join code first.')
    if (selectedStudents.length === 0) return setToast('Select at least one student.')
    setBusy(true)
    try {
      let problemId = selectedId
      let problemTitle = selected?.title ?? ''
      if (mode === 'create') {
        if (!title.trim()) throw new Error('Give the problem a title.')
        const cases = testCases.filter((tc) => tc.expected.trim())
        if (cases.length === 0) throw new Error('Add at least one test case with an expected output.')
        const created = await api.createProblem({ title, description, topic, difficulty, starter_code: starterCode, test_cases: cases })
        problemId = created.id
        problemTitle = created.title
      }
      await api.createAssignment(room.id, { problem_id: problemId, student_ids: selectedStudents, due_date: dueDate, notes })
      await refresh()
      setToast(`Assigned “${problemTitle}” to ${selectedStudents.length} student${selectedStudents.length === 1 ? '' : 's'}.`)
      window.setTimeout(() => navigate('/teacher/assigned'), 700)
    } catch (e) {
      setToast(e instanceof Error ? e.message : 'Could not assign')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <header className="page-header">
        <p className="muted" style={{ marginBottom: '0.35rem' }}>
          <Link to="/teacher/classroom" className="btn btn-ghost" style={{ padding: 0 }}>
            ← Classroom
          </Link>
        </p>
        <h1>Assign Problem</h1>
        <p>Choose from the TraceLearn dataset or create a new C++ problem with test cases, then assign it to {room.code}.</p>
      </header>

      <div className="mode-switch">
        <button type="button" className={mode === 'dataset' ? 'active' : ''} onClick={() => setMode('dataset')}>
          Choose existing problem
        </button>
        <button type="button" className={mode === 'create' ? 'active' : ''} onClick={() => setMode('create')}>
          Create new problem
        </button>
      </div>

      {mode === 'dataset' ? (
        <section className="card">
          <div className="card-label">Problem bank</div>
          <h2 style={{ margin: '0 0 0.85rem' }}>Pick an existing problem</h2>
          <label className="field">
            <span>Problem</span>
            <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
              {problems.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} — {p.topic} · {p.difficulty}
                  {p.source === 'custom' ? ' (yours)' : ''}
                </option>
              ))}
            </select>
          </label>
          {selected ? (
            <div className="dataset-preview">
              <p>
                <strong>Topic:</strong> {selected.topic || '—'} · <strong>Difficulty:</strong> {selected.difficulty}
              </p>
              <p>
                <strong>Concepts:</strong> {selected.concept_tags.join(', ') || '—'}
              </p>
            </div>
          ) : null}
        </section>
      ) : (
        <section className="card stack">
          <div>
            <div className="card-label">New problem</div>
            <h2 style={{ margin: 0 }}>Create problem + test cases</h2>
            <p className="muted" style={{ marginTop: '0.35rem' }}>
              Students read input from stdin and print the answer. Output is compared token by token, so spaces vs. newlines do not matter.
            </p>
          </div>
          <label className="field">
            <span>Title</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="Count multiples in a range" />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={4000} placeholder="Print all multiples of K from 1 to N." />
          </label>
          <div className="form-row">
            <label className="field">
              <span>Topic</span>
              <input value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={48} />
            </label>
            <label className="field">
              <span>Difficulty</span>
              <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                <option>Easy</option>
                <option>Medium</option>
                <option>Hard</option>
              </select>
            </label>
          </div>
          <label className="field">
            <span>Starter code (C++)</span>
            <textarea className="code-input" rows={9} value={starterCode} onChange={(e) => setStarterCode(e.target.value)} maxLength={16000} spellCheck={false} />
          </label>
          <div>
            <div className="split-header">
              <h3 style={{ margin: 0 }}>Test cases</h3>
              <button type="button" className="btn btn-secondary" onClick={() => setTestCases((p) => [...p, { input: '', expected: '', visible: false }])} disabled={testCases.length >= 20}>
                Add test case
              </button>
            </div>
            <div className="stack" style={{ gap: '0.65rem', marginTop: '0.75rem' }}>
              {testCases.map((tc, i) => (
                <div className="test-case-row" key={i}>
                  <label className="field">
                    <span>Input (stdin)</span>
                    <input value={tc.input} onChange={(e) => updateTc(i, { input: e.target.value })} maxLength={4000} />
                  </label>
                  <label className="field">
                    <span>Expected output</span>
                    <input value={tc.expected} onChange={(e) => updateTc(i, { expected: e.target.value })} maxLength={4000} />
                  </label>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                    <label className="check-pill" title="Hidden tests are graded but never shown to students">
                      <input type="checkbox" checked={tc.visible} onChange={(e) => updateTc(i, { visible: e.target.checked })} />
                      Visible
                    </label>
                    <button type="button" className="btn btn-ghost" onClick={() => setTestCases((p) => p.filter((_, j) => j !== i))} disabled={testCases.length <= 1}>
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="card stack">
        <div>
          <div className="card-label">Assignment</div>
          <h2 style={{ margin: 0 }}>Who should receive this?</h2>
        </div>
        {members.length === 0 ? (
          <p className="muted">No students in {room.code} yet.</p>
        ) : (
          <div className="student-checkboxes">
            <button type="button" className="btn btn-ghost" style={{ padding: '0.3rem 0.5rem' }} onClick={() => setSelectedStudents(selectedStudents.length === members.length ? [] : members.map((m) => m.student_id))}>
              {selectedStudents.length === members.length ? 'Select none' : 'Select all'}
            </button>
            {members.map((m) => (
              <label key={m.student_id} className="check-pill">
                <input type="checkbox" checked={selectedStudents.includes(m.student_id)} onChange={() => toggle(m.student_id)} />
                {m.display_name}
              </label>
            ))}
          </div>
        )}
        <div className="form-row">
          <label className="field">
            <span>Due date</span>
            <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </label>
          <label className="field">
            <span>Notes for students</span>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} placeholder="Focus on inclusive loop boundaries." />
          </label>
        </div>
        <div className="btn-row">
          <button type="button" className="btn btn-primary" onClick={() => void handleAssign()} disabled={busy}>
            {busy ? 'Assigning…' : 'Assign to class'}
          </button>
          <Link className="btn btn-secondary" to="/teacher/classroom">
            Cancel
          </Link>
        </div>
        {toast ? <p className="toast-msg">{toast}</p> : null}
      </section>
    </div>
  )
}

export function AssignProblemPage() {
  return <RequireClass>{(room) => <AssignForm room={room} />}</RequireClass>
}
