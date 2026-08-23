import { useEffect, useState } from 'react'
import { fetchLearnerProfile, submitTeacherReview } from '../api/client'
import { useSession } from '../context/SessionContext'
import type { LearnerStateRow } from '../types'

export function TeacherExperimentScreen() {
  const { selectedStudentId, lastResult } = useSession()
  const [states, setStates] = useState<LearnerStateRow[]>([])
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (selectedStudentId == null) return
    void fetchLearnerProfile(selectedStudentId)
      .then((p) => setStates(p.learner_states))
      .catch(() => setStates([]))
  }, [selectedStudentId, lastResult])

  const diagnosisId = lastResult?.history_aware?.id

  return (
    <div className="screen">
      <header className="screen-header">
        <h2>Teacher View</h2>
      </header>
      <section className="card">
        <h3>Learner states</h3>
        {states.length === 0 ? <p className="muted">No states yet.</p> : (
          <table className="data-table"><tbody>
            {states.map((s) => <tr key={s.id}><td>{s.misconception_id}</td><td>{s.state}</td><td>{(s.confidence ?? 0).toFixed(2)}</td></tr>)}
          </tbody></table>
        )}
      </section>
      {diagnosisId && (
        <section className="card">
          <h3>Teacher review</h3>
          <button type="button" onClick={() => void submitTeacherReview(diagnosisId, 'CONFIRM').then(() => setMsg('CONFIRM saved'))}>Confirm</button>{' '}
          <button type="button" onClick={() => void submitTeacherReview(diagnosisId, 'REJECT').then(() => setMsg('REJECT saved'))}>Reject</button>{' '}
          <button type="button" onClick={() => void submitTeacherReview(diagnosisId, 'MARK_UNCERTAIN').then(() => setMsg('MARK_UNCERTAIN saved'))}>Mark uncertain</button>
          {msg && <p>{msg}</p>}
        </section>
      )}
    </div>
  )
}

