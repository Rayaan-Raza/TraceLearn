import { useState, type FormEvent, type ReactNode } from 'react'
import { api } from '../../api/client'
import type { Classroom } from '../../api/types'
import { ErrorState, Loading } from '../../components/PageState'
import { useClasses } from '../../context/ClassContext'

export function CreateClassForm({ onCreated }: { onCreated?: (c: Classroom) => void }) {
  const { refresh, setCurrentId } = useClasses()
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr('')
    try {
      const c = await api.createClassroom(code.trim(), name.trim())
      await refresh()
      setCurrentId(c.id)
      setCode('')
      setName('')
      onCreated?.(c)
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not create class')
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="stack" style={{ gap: '0.85rem' }} onSubmit={(e) => void submit(e)}>
      <div className="form-row">
        <label className="field">
          <span>Course code</span>
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS101" maxLength={32} required />
        </label>
        <label className="field">
          <span>Course name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Introduction to Programming" maxLength={128} required />
        </label>
      </div>
      {err ? <p className="form-error">{err}</p> : null}
      <div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          Create classroom
        </button>
      </div>
    </form>
  )
}

/** Renders children with the current classroom, or a create-class prompt. */
export function RequireClass({ children }: { children: (c: Classroom) => ReactNode }) {
  const { current, loading, error, refresh } = useClasses()
  if (loading) return <Loading />
  if (error) return <ErrorState message={error} onRetry={() => void refresh()} />
  if (!current)
    return (
      <div className="stack">
        <header className="page-header">
          <h1>Create your first classroom</h1>
        </header>
        <section className="card">
          <CreateClassForm />
        </section>
      </div>
    )
  return <>{children(current)}</>
}

export function JoinCodeCard({ classroom }: { classroom: Classroom }) {
  const { refresh } = useClasses()
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  async function rotate() {
    if (!window.confirm('Generate a new join code? The old code will stop working for new students.')) return
    setBusy(true)
    try {
      await api.rotateJoinCode(classroom.id)
      await refresh()
    } finally {
      setBusy(false)
    }
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(classroom.join_code ?? '')
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked */
    }
  }
  return (
    <section className="card">
      <div className="card-label">Join code</div>
      <div className="split-header">
        <div className="join-code">{classroom.join_code}</div>
        <div className="btn-row" style={{ marginTop: 0 }}>
          <button type="button" className="btn btn-secondary" onClick={() => void copy()}>
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => void rotate()} disabled={busy}>
            New code
          </button>
        </div>
      </div>
      <p className="muted" style={{ marginTop: '0.5rem', fontSize: '0.88rem' }}>
        Share this with students. They enter it on their Classroom page.
      </p>
    </section>
  )
}
