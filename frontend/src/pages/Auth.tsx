import { useState, type FormEvent } from 'react'
import { useAuth } from '../context/AuthContext'

type Mode = 'login' | 'register'

export function AuthPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [isTeacher, setIsTeacher] = useState(false)
  const [teacherCode, setTeacherCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(email.trim(), password)
      } else {
        await register({
          email: email.trim(),
          password,
          display_name: name.trim(),
          role: isTeacher ? 'teacher' : 'student',
          teacher_code: isTeacher ? teacherCode : undefined,
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-card">
        <div className="brand" style={{ padding: 0, marginBottom: '1.5rem' }}>
          <div className="brand-mark" style={{ color: 'var(--ink)' }}>
            TraceLearn
          </div>
          <div className="brand-sub" style={{ color: 'var(--ink-muted)' }}>
            Learning patterns, made visible
          </div>
        </div>

        <div className="mode-switch" style={{ marginBottom: '1.25rem' }}>
          <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>
            Sign in
          </button>
          <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>
            Create account
          </button>
        </div>

        <form className="stack" style={{ gap: '0.9rem' }} onSubmit={(e) => void submit(e)}>
          {mode === 'register' && (
            <label className="field">
              <span>Your name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} maxLength={64} autoComplete="name" required />
            </label>
          )}
          <label className="field">
            <span>Email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={254} autoComplete="email" required />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={mode === 'register' ? 8 : undefined}
              maxLength={72}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
            />
          </label>
          {mode === 'register' && (
            <>
              <label className="check-pill" style={{ alignSelf: 'flex-start' }}>
                <input type="checkbox" checked={isTeacher} onChange={(e) => setIsTeacher(e.target.checked)} />
                I am a teacher
              </label>
              {isTeacher && (
                <label className="field">
                  <span>Teacher invite code</span>
                  <input value={teacherCode} onChange={(e) => setTeacherCode(e.target.value)} maxLength={128} autoComplete="off" required />
                </label>
              )}
            </>
          )}
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </section>
    </div>
  )
}
