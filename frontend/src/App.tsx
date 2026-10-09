import { useState, useEffect } from 'react'
import { SessionProvider } from './context/SessionContext'
import { AuthScreen } from './screens/Auth'
import { StudentSubmissionScreen } from './screens/StudentSubmission'
import { EvidenceInspectorScreen } from './screens/EvidenceInspector'
import { ComparisonScreen } from './screens/ComparisonView'
import { LearnerTimelineScreen } from './screens/LearnerTimeline'
import { TeacherExperimentScreen } from './screens/TeacherExperimentView'
import type { AuthResponse } from './types'
import './index.css'

const TABS = [
  ['submission', 'Submission'],
  ['evidence', 'Evidence'],
  ['compare', 'Compare'],
  ['timeline', 'Timeline'],
  ['teacher', 'Teacher'],
] as const

export default function App() {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('submission')
  const [authed, setAuthed] = useState(false)
  const [userRole, setUserRole] = useState<string>('')

  useEffect(() => {
    try {
      const token = localStorage.getItem('tl_token')
      if (token) {
        setAuthed(true)
        setUserRole(localStorage.getItem('tl_role') ?? '')
      }
    } catch {}
  }, [])

  const handleAuth = (resp: AuthResponse) => {
    setAuthed(true)
    setUserRole(resp.role)
  }

  const handleLogout = () => {
    try {
      localStorage.removeItem('tl_token')
      localStorage.removeItem('tl_role')
      localStorage.removeItem('tl_user_id')
      localStorage.removeItem('tl_student_id')
    } catch {}
    setAuthed(false)
    setUserRole('')
  }

  if (!authed) {
    return <AuthScreen onAuth={handleAuth} />
  }

  return (
    <SessionProvider>
      <div className="app">
        <div className="app-header">
          <h1>TraceLearn</h1>
          <div className="app-header-right">
            <span className="role-badge">{userRole}</span>
            <button type="button" className="logout-btn" onClick={handleLogout}>Logout</button>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map(([id, label]) => (
            <button key={id} type="button" className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>
        {tab === 'submission' && <StudentSubmissionScreen />}
        {tab === 'evidence' && <EvidenceInspectorScreen />}
        {tab === 'compare' && <ComparisonScreen />}
        {tab === 'timeline' && <LearnerTimelineScreen />}
        {tab === 'teacher' && <TeacherExperimentScreen />}
      </div>
    </SessionProvider>
  )
}
