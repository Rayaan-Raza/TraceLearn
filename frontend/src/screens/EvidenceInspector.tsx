import { useEffect, useMemo, useState } from 'react'
import { fetchSubmissionEvidence } from '../api/client'
import { useSession } from '../context/SessionContext'
import type { EvidenceItem } from '../types'

function groupBySource(items: EvidenceItem[]): Record<string, EvidenceItem[]> {
  return items.reduce<Record<string, EvidenceItem[]>>((acc, item) => {
    const key = item.source_type || 'unknown'
    acc[key] = acc[key] ?? []
    acc[key].push(item)
    return acc
  }, {})
}

export function EvidenceInspectorScreen() {
  const { lastResult } = useSession()
  const [items, setItems] = useState<EvidenceItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!lastResult?.submission_id) {
      setItems(lastResult?.evidence ?? [])
      return
    }
    setLoading(true)
    void (async () => {
      try {
        if (lastResult.evidence?.length) {
          setItems(lastResult.evidence)
          return
        }
        const fetched = await fetchSubmissionEvidence(lastResult.submission_id)
        setItems(fetched)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load evidence')
        setItems(lastResult.evidence ?? [])
      } finally {
        setLoading(false)
      }
    })()
  }, [lastResult])

  const grouped = useMemo(() => groupBySource(items), [items])

  return (
    <div className="screen">
      <header className="screen-header">
        <h2>Evidence Inspector</h2>
        <p className="muted">Grouped by source_type for the latest submission.</p>
      </header>

      {!lastResult && <p className="muted">Submit code on the Student Submission tab first.</p>}
      {loading && <p className="muted">Loading evidence…</p>}
      {error && <div className="banner error">{error}</div>}

      {Object.keys(grouped).length === 0 && lastResult && !loading && (
        <p className="muted">No evidence items returned yet.</p>
      )}

      <div className="evidence-groups">
        {Object.entries(grouped)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([sourceType, group]) => (
            <section key={sourceType} className="card evidence-group">
              <h3>{sourceType}</h3>
              <ul>
                {group.map((ev) => (
                  <li key={ev.id}>
                    <strong>{ev.evidence_code}</strong>
                    <span className={`pill ${ev.direction}`}>{ev.direction}</span>
                    <span className="muted">w={ev.weight.toFixed(2)}</span>
                    {ev.misconception_id && <span className="tag">{ev.misconception_id}</span>}
                    <p>{ev.description}</p>
                  </li>
                ))}
              </ul>
            </section>
          ))}
      </div>
    </div>
  )
}
