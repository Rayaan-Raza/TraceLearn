import { useState } from 'react'
import { authLogin, authRegister } from '../api/client'
import type { AuthResponse } from '../types'

type Props = {
  onAuth: (resp: AuthResponse) => void
}

export function AuthScreen({ onAuth }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState<'student' | 'teacher'>('student')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const resp = mode === 'login'
        ? await authLogin(email, password)
        : await authRegister(email, password, role, displayName)
      localStorage.setItem('tl_token', resp.access_token)
      localStorage.setItem('tl_role', resp.role)
      localStorage.setItem('tl_user_id', String(resp.user_id))
      if (resp.student_id != null) localStorage.setItem('tl_student_id', String(resp.student_id))
      onAuth(resp)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="screen auth-screen">
      <div className="auth-card">
        <h2>TraceLearn</h2>

        <div className="auth-toggle">
          <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>
            Login
          </button>
          <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>
            Register
          </button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)}>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </label>

          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>

          {mode === 'register' && (
            <>
              <label>
                Display Name
                <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Optional" />
              </label>
              <label>
                Role
                <select value={role} onChange={(e) => setRole(e.target.value as 'student' | 'teacher')}>
                  <option value="student">Student</option>
                  <option value="teacher">Teacher</option>
                </select>
              </label>
            </>
          )}

          {error && <div className="banner error">{error}</div>}

          <button type="submit" className="primary" disabled={loading}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Login' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}
