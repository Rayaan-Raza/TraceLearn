import type { EvidenceItem, ModelPrediction, ModelTopK } from '../api/types'
import { confidenceBandLabel, confidencePct, decisionSourceLabel, misconceptionLabel } from '../lib/labels'

type StoredPrediction = Partial<ModelPrediction>

/** The record the panel describes: the latest stored decision, never a shadow run when a real one exists. */
function pickModelRecord(items: EvidenceItem[]): { item: EvidenceItem; shadow: boolean } | null {
  const model = items.filter((i) => i.source_type === 'model')
  const item = [...model].reverse().find((i) => i.evidence_code !== 'MODEL_SHADOW') ?? model[model.length - 1]
  return item ? { item, shadow: item.evidence_code === 'MODEL_SHADOW' } : null
}

/**
 * What the teacher sees for the model's part of a diagnosis. A rule or repair can decide before the
 * classifier, so the panel says which stage decided, shows that stage's confidence as the measured
 * precision of the check (it is not a probability), and keeps the classifier's own answer and
 * probabilities under their own title.
 */
export function ModelPanel({ items }: { items: EvidenceItem[] }) {
  const picked = pickModelRecord(items)
  if (!picked) return null
  let details: StoredPrediction
  try {
    details = JSON.parse(picked.item.details_json ?? '{}')
  } catch {
    return null
  }
  const topK: ModelTopK[] = details.top_k ?? []
  const abstained = details.abstained ?? false
  // Records written before the stage was stored have no decision_source. A rule decision then carried
  // top_probability 1.0, which a calibrated classifier never reports.
  const olderRule = details.decision_source == null && details.top_probability === 1
  const source = details.decision_source ?? 'model'
  const byClassifier = source === 'model' && !olderRule
  const stage = olderRule ? 'rule or repair (record from before stages were stored)' : decisionSourceLabel(source)
  const p = details.top_probability
  const band = p != null ? confidenceBandLabel(p) : ''
  const classifierLabel = details.classifier_label

  return (
    <section className="card" data-testid="model-panel">
      <div className="card-label">Model prediction</div>
      {picked.shadow ? (
        <p className="muted" style={{ margin: '0.3rem 0 0' }}>Shadow run: recorded for comparison, not used for this diagnosis.</p>
      ) : null}
      <p className="muted" style={{ margin: '0.3rem 0 0' }}>Decided by: {stage}</p>
      <div className="split-header" style={{ alignItems: 'flex-start', marginTop: '0.3rem' }}>
        <div>
          <h2 style={{ margin: 0 }}>{abstained ? 'Abstained' : misconceptionLabel(details.top_label)}</h2>
          {details.variant ? <p className="muted" style={{ margin: '0.2rem 0 0' }}>Variant: {details.variant}</p> : null}
        </div>
        {!abstained && p != null ? (
          <span className="badge completed">
            {byClassifier ? `${confidencePct(p)} · ${band}` : olderRule ? 'not a measured probability' : `Measured precision of this check: ${confidencePct(p)} · ${band}`}
          </span>
        ) : null}
      </div>
      {!byClassifier && classifierLabel ? (
        <p className="muted" style={{ margin: '0.5rem 0 0' }}>
          The classifier itself said {misconceptionLabel(classifierLabel)}
          {details.classifier_probability != null ? ` (${confidencePct(details.classifier_probability)})` : ''}
          {details.classifier_abstained ? ', below its threshold' : ''}.
        </p>
      ) : null}
      {topK.length > 0 && (
        <div style={{ marginTop: '0.9rem' }}>
          <div className="card-label">Classifier probabilities (top {topK.length})</div>
          <ul className="evidence-list" style={{ marginTop: '0.4rem' }}>
            {topK.map((tk) => (
              <li key={tk.label}>
                <strong>{misconceptionLabel(tk.label)}</strong>
                <span className="muted"> — {confidencePct(tk.p)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
