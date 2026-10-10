import { api } from '../../api/client'
import { BarChart, TimelineChart } from '../../components/MisconceptionCharts'
import { ErrorState, Loading } from '../../components/PageState'
import { StatusBadge } from '../../components/StatusBadge'
import { Timeline } from '../../components/Timeline'
import { useMe } from '../../context/AuthContext'
import { conceptStories, derive, useProblemTitles, useStudentBundle } from '../../lib/studentData'
import { useApi } from '../../lib/useApi'

export function ProgressPage() {
  const me = useMe()
  const bundle = useStudentBundle(me.student_id)
  const problems = useApi(() => api.problems(), [])
  const title = useProblemTitles(problems.data)

  if (bundle.loading || problems.loading) return <Loading />
  if (bundle.error) return <ErrorState message={bundle.error} onRetry={bundle.reload} />

  const d = derive(bundle.data)
  const stories = conceptStories(bundle.data, title)

  return (
    <div className="stack">
      <header className="page-header">
        <h1>Your Progress</h1>
      </header>

      <div className="grid-2">
        <BarChart title="Concepts by state" points={d.stateCounts} axisNote="X: state · Y: count" />
        <TimelineChart title="Mistake timeline" points={d.mistakeTimeline} />
      </div>

      {stories.map((c) => (
          <section className="card" key={c.misconceptionId}>
            <div className="split-header">
              <div>
                <div className="card-label">Concept</div>
                <h2 style={{ margin: 0 }}>{c.concept}</h2>
              </div>
              <StatusBadge status={c.status} />
            </div>
            <div style={{ marginTop: '1.15rem' }}>
              <Timeline events={c.events} />
            </div>
          </section>
        ))}
    </div>
  )
}
