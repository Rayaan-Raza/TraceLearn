import { useEffect, useState } from 'react'
import { fetchSubmissionDiagnoses } from '../api/client'
import { useSession } from '../context/SessionContext'
import type { DiagnosisResult } from '../types'

function pick(diagnoses: DiagnosisResult[], mode: DiagnosisResult['mode']) {
  return diagnoses.find((d) => d.mode === mode) ?? null
}

export function ComparisonScreen() {
  const { lastResult } = useSession()
  const [diagnoses, setDiagnoses] = useState<DiagnosisResult[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!lastResult?.submission_id) {
      setDiagnoses(lastResult?.diagnoses ?? [])
      return
    }

    if (lastResult?.current_only || lastResult?.history_aware) {
      const built: DiagnosisResult[] = []
      if (lastResult.current_only) built.push({ ...lastResult.current_only, mode: 'current_only' })
      if (lastResult.history_aware) built.push({ ...lastResult.history_aware, mode: 'history_aware' })
      setDiagnoses(built)
      return
    }
    if (lastResult.diagnoses?.length) {
      setDiagnoses(lastResult.diagnoses)
      return
    }
    void (async () => {
      try {
        setDiagnoses(await fetchSubmissionDiagnoses(lastResult.submission_id))
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load diagnoses')
      }
    })()
  }, [lastResult])

  const current = pick(diagnoses, 'current_only')
  const history = pick(diagnoses, 'history_aware')

  const resultChanged =
    current &&
    history &&
    (current.primary_misconception !== history.primary_misconception ||
      Math.abs(current.primary_confidence - history.primary_confidence) > 0.05)

  return (
    <div className="screen">
      <header className="screen-header">
        <h2>Current vs History Comparison</h2>
        <p className="muted">Side-by-side diagnosis modes; highlighted when history changes the outcome.</p>
      </header>

      {!lastResult && <p className="muted">Run a submission to compare diagnoses.</p>}
      {error && <div className="banner error">{error}</div>}

      <div className={`comparison-grid ${resultChanged ? 'history-changed' : ''}`}>
        <div className="card compare-col">
          <h3>Current only</h3>
          {current ? (
            <>
              <p className="misconception">{current.primary_misconception}</p>
              <p>Confidence {(current.primary_confidence * 100).toFixed(1)}%</p>
              {current.alternative_misconception && (
                <p className="muted">Alt: {current.alternative_misconception}</p>
              )}
            </>
          ) : (
            <p className="muted">—</p>
          )}
        </div>
        <div className="card compare-col">
          <h3>History aware</h3>
          {history ? (
            <>
              <p className="misconception">{history.primary_misconception}</p>
              <p>Confidence {(history.primary_confidence * 100).toFixed(1)}%</p>
              {history.alternative_misconception && (
                <p className="muted">Alt: {history.alternative_misconception}</p>
              )}
            </>
          ) : (
            <p className="muted">—</p>
          )}
        </div>
      </div>
    </div>
  )
}
