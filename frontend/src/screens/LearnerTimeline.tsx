import { useEffect, useState } from 'react'
import { fetchLearnerTimeline } from '../api/client'
import { useSession } from '../context/SessionContext'
import type { TimelineEntry } from '../types'

export function LearnerTimelineScreen() {
  const { selectedStudentId, students } = useSession()
  const [entries, setEntries] = useState<TimelineEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const student = students.find((s) => s.id === selectedStudentId)

  useEffect(() => {
    if (selectedStudentId == null) return
    setLoading(true)
    void (async () => {
      try {
        setEntries(await fetchLearnerTimeline(selectedStudentId))
        setError(null)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Timeline unavailable')
        setEntries([])
      } finally {
        setLoading(false)
      }
    })()
  }, [selectedStudentId])

  return (
    <div className="screen">
      <header className="screen-header">
        <h2>Learner Timeline</h2>
        <p className="muted">Events for {student?.display_name ?? 'selected student'}.</p>
      </header>
      {loading && <p className="muted">Loading timeline…</p>}
      {error && <div className="banner error">{error}</div>}
      {entries.length === 0 && !loading && !error && <p className="muted">No timeline entries yet.</p>}
      <ol className="timeline">
        {entries.map((ev) => (
          <li key={ev.submission_id} className="timeline-item">
            <time>{new Date(ev.submitted_at).toLocaleString()}</time>
            <strong>{ev.problem_id} attempt {ev.attempt_number}</strong>
            <p>{ev.primary_diagnosis ?? '—'}</p>
            {ev.state_transitions?.map((tr, i) => (
              <div key={i} className="muted">{tr.old_state} → {tr.new_state} ({tr.misconception_id})</div>
            ))}
          </li>
        ))}
      </ol>
    </div>
  )
}
