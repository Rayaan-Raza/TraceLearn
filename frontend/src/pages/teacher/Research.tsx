import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { ErrorState, Loading } from '../../components/PageState'
import { useApi } from '../../lib/useApi'

type Metrics = { accuracy?: number; macro_precision?: number; macro_recall?: number; macro_f1?: number }

function pct(v: unknown) {
  return typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—'
}

export function ResearchPage() {
  const status = useApi(() => api.demoStatus(), [])
  const exp = useApi(() => api.experiment(), [])
  const students = useApi(() => api.students(), [])
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label)
    setMsg('')
    try {
      await fn()
      setMsg(`${label} complete.`)
      exp.reload()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : `${label} failed`)
    } finally {
      setBusy('')
    }
  }

  if (status.loading || exp.loading) return <Loading />
  if (exp.error) return <ErrorState message={exp.error} onRetry={exp.reload} />

  const m = exp.data ?? {}
  const cur = (m.current_only_metrics ?? {}) as Metrics
  const hist = (m.history_aware_metrics ?? {}) as Metrics
  const synthetic = (students.data ?? []).filter((s) => s.is_synthetic)
  const rows: [string, unknown, unknown][] = [
    ['Accuracy', pct(cur.accuracy), pct(hist.accuracy)],
    ['Macro precision', pct(cur.macro_precision), pct(hist.macro_precision)],
    ['Macro recall', pct(cur.macro_recall), pct(hist.macro_recall)],
    ['Macro F1', pct(cur.macro_f1), pct(hist.macro_f1)],
    ['False persistent', m.false_persistent_current_only ?? '—', m.false_persistent_history_aware ?? '—'],
    ['Persistent cases detected', m.persistent_cases_detected_current_only ?? '—', m.persistent_cases_detected_history_aware ?? '—'],
  ]

  return (
    <div className="stack">
      <header className="page-header">
        <h1>Research</h1>
        <p>Current-only vs history-aware diagnosis, calculated live from labelled synthetic submissions. Nothing here is hardcoded.</p>
      </header>

      <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1.1rem 1.25rem 0.4rem' }}>
          <div className="card-label">Experiment metrics</div>
          <p className="muted" style={{ margin: 0 }}>
            History changed {String(m.history_changed_predictions ?? 0)} predictions, {String(m.history_changed_correctly ?? 0)} of them correctly · learner-state accuracy{' '}
            {pct(m.learner_state_accuracy)}
          </p>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Current-only</th>
              <th>History-aware</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, a, b]) => (
              <tr key={name}>
                <td>{name}</td>
                <td>{String(a)}</td>
                <td>{String(b)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card stack">
        <div>
          <div className="card-label">Synthetic demo sequences</div>
          <h2 style={{ margin: 0 }}>Replay the proposal demo</h2>
        </div>
        {status.data?.enabled ? (
          <>
            <p className="muted" style={{ margin: 0 }}>Affects synthetic SYN* students only. Real students are never touched.</p>
            <div className="btn-row" style={{ marginTop: 0 }}>
              <button type="button" className="btn btn-secondary" disabled={!!busy} onClick={() => void run('Reset', api.demoReset)}>
                Reset synthetic data
              </button>
              {status.data.sequences.map((s) => (
                <button key={s} type="button" className="btn btn-ghost" disabled={!!busy} onClick={() => void run(`Run ${s}`, () => api.demoRun(s))}>
                  Run {s}
                </button>
              ))}
            </div>
          </>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            Demo endpoints are disabled on this server. Set <code>ENABLE_DEMO_ENDPOINTS=true</code> (development only), or run{' '}
            <code>python scripts/run_synthetic_experiment.py</code>.
          </p>
        )}
        {busy ? <p className="muted">{busy}…</p> : null}
        {msg ? <p className="toast-msg">{msg}</p> : null}
        {synthetic.length > 0 && (
          <div className="student-checkboxes">
            {synthetic.map((s) => (
              <Link key={s.id} className="check-pill" to={`/teacher/students/${s.id}`}>
                {s.display_name}
              </Link>
            ))}
          </div>
        )}
      </section>

      {status.data ? (
        <section className="card">
          <div className="card-label">Code execution sandbox</div>
          <p style={{ margin: 0 }}>
            {status.data.sandbox.isolated
              ? 'Student code runs inside bubblewrap: no network, no access to server files, resource limits enforced.'
              : status.data.sandbox.required
                ? 'bubblewrap is not available on this server, so code execution is refused.'
                : 'Warning: bubblewrap is not available. Code runs with resource limits only — do not expose this server to untrusted students.'}
          </p>
        </section>
      ) : null}
    </div>
  )
}
