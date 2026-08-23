import { useState } from 'react'
import { SessionProvider } from './context/SessionContext'
import { StudentSubmissionScreen } from './screens/StudentSubmission'
import { EvidenceInspectorScreen } from './screens/EvidenceInspector'
import { ComparisonScreen } from './screens/ComparisonView'
import { LearnerTimelineScreen } from './screens/LearnerTimeline'
import { TeacherExperimentScreen } from './screens/TeacherExperimentView'
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
  return (
    <SessionProvider>
      <div className="app">
        <h1>TraceLearn POC</h1>
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
