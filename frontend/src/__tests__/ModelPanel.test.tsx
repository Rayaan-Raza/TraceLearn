/**
 * The teacher's model panel, mounted for real: one case per deciding stage, plus the cases that must
 * not look like a decision. A teacher has to be able to tell "a repair made every test pass" from
 * "the classifier thinks so", and never see a confidence of 100%.
 */
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { EvidenceItem, ModelPrediction } from '../api/types'
import { ModelPanel } from '../components/ModelPanel'

function prediction(overrides: Partial<ModelPrediction> = {}): ModelPrediction {
  return {
    variant: 'execution',
    model_sha256: 'abc123',
    top_label: 'CPP_LOOP_BOUNDARY',
    top_probability: 0.82,
    abstained: false,
    threshold: 0.44,
    temperature: 1.4,
    probabilities: { CPP_LOOP_BOUNDARY: 0.82, CPP_OTHER_ERROR: 0.18 },
    top_k: [{ label: 'CPP_LOOP_BOUNDARY', p: 0.82 }, { label: 'CPP_OTHER_ERROR', p: 0.18 }],
    n_features: 90,
    n_missing: 3,
    ...overrides,
  }
}

function record(details: Partial<ModelPrediction>, code = 'MODEL_PREDICTION', id = 1): EvidenceItem {
  return {
    id, submission_id: 1, source_type: 'model', evidence_code: code, misconception_id: null,
    direction: 'support', weight: 0.3, description: '', details_json: JSON.stringify(prediction(details)),
  }
}

/** A rule decided: the classifier said OFF_BY_ONE at 0.41 and abstained, the rule said LOOP_BOUNDARY. */
const ruleDecision = (source: string, precision: number): Partial<ModelPrediction> => ({
  decision_source: source,
  top_label: 'CPP_LOOP_BOUNDARY',
  top_probability: precision,
  abstained: false,
  classifier_label: 'CPP_OFF_BY_ONE',
  classifier_probability: 0.41,
  classifier_abstained: true,
  top_k: [{ label: 'CPP_OFF_BY_ONE', p: 0.41 }, { label: 'CPP_OTHER_ERROR', p: 0.3 }, { label: 'CPP_LOOP_BOUNDARY', p: 0.12 }],
})

describe('ModelPanel, one case per deciding stage', () => {
  it('classifier: says so, shows a probability with its band, and titles the list as the classifier\'s', () => {
    render(<ModelPanel items={[record({ decision_source: 'model' })]} />)
    const panel = screen.getByTestId('model-panel')
    expect(within(panel).getByText('Decided by: classifier')).toBeInTheDocument()
    expect(within(panel).getByRole('heading', { name: 'Loop Boundaries' })).toBeInTheDocument()
    expect(within(panel).getByText('82% · High confidence')).toBeInTheDocument()
    expect(within(panel).getByText(/Classifier probabilities/)).toBeInTheDocument()
    expect(within(panel).queryByText(/Measured precision/)).toBeNull()
  })

  it.each([
    ['repair', 'repair check', 0.817, '82%', 'High confidence'],
    ['narrow_repair', 'narrow repair', 0.65, '65%', 'Some confidence'],
    ['class_rule', 'class rule', 0.45, '45%', 'Low confidence'],
  ])('%s: names the stage, calls the figure a measured precision, applies the 0.50 / 0.75 bands', (source, name, precision, pct, band) => {
    render(<ModelPanel items={[record(ruleDecision(source, precision))]} />)
    const panel = screen.getByTestId('model-panel')
    expect(within(panel).getByText(`Decided by: ${name}`)).toBeInTheDocument()
    expect(within(panel).getByText(`Measured precision of this check: ${pct} · ${band}`)).toBeInTheDocument()
    expect(within(panel).getByRole('heading', { name: 'Loop Boundaries' })).toBeInTheDocument()
    expect(panel.textContent).not.toMatch(/100%/)
  })

  it('a rule decision keeps the classifier\'s own answer visible, so a disagreement can be seen', () => {
    render(<ModelPanel items={[record(ruleDecision('repair', 0.817))]} />)
    const panel = screen.getByTestId('model-panel')
    expect(within(panel).getByText(/The classifier itself said Off-by-one Indexing \(41%\), below its threshold\./)).toBeInTheDocument()
    expect(within(panel).getByText(/Classifier probabilities/)).toBeInTheDocument()
  })
})

describe('ModelPanel, outcomes that are not a named decision', () => {
  it('abstained: says Abstained and shows no confidence badge', () => {
    render(<ModelPanel items={[record({ abstained: true, top_probability: 0.3 }, 'MODEL_ABSTAINED')]} />)
    const panel = screen.getByTestId('model-panel')
    expect(within(panel).getByText('Abstained')).toBeInTheDocument()
    expect(within(panel).queryByText(/confidence/i)).toBeNull()
  })

  it('OTHER_ERROR: has its own display name, not the generic fallback', () => {
    render(<ModelPanel items={[record({ top_label: 'CPP_OTHER_ERROR', top_probability: 0.9, top_k: [] }, 'MODEL_OTHER_ERROR')]} />)
    expect(within(screen.getByTestId('model-panel')).getByText('Other error (no modelled misconception)')).toBeInTheDocument()
  })

  it('shadow run: labelled as not used, and a stored decision is shown in preference to it', () => {
    const shadow = record({ top_label: 'CPP_OFF_BY_ONE' }, 'MODEL_SHADOW', 2)
    const { rerender } = render(<ModelPanel items={[shadow]} />)
    expect(screen.getByText(/Shadow run: recorded for comparison, not used/)).toBeInTheDocument()
    rerender(<ModelPanel items={[record({ decision_source: 'model' }, 'MODEL_PREDICTION', 1), shadow]} />)
    expect(screen.queryByText(/Shadow run/)).toBeNull()
    expect(screen.getByRole('heading', { name: 'Loop Boundaries' })).toBeInTheDocument()
  })

  it('older record: a rule decision stored as 1.0 before stages were recorded is not shown as 100%', () => {
    const old = record({ top_probability: 1 })
    const details = JSON.parse(old.details_json)
    delete details.decision_source
    render(<ModelPanel items={[{ ...old, details_json: JSON.stringify(details) }]} />)
    const panel = screen.getByTestId('model-panel')
    expect(within(panel).getByText(/Decided by: rule or repair \(record from before stages were stored\)/)).toBeInTheDocument()
    expect(within(panel).getByText('not a measured probability')).toBeInTheDocument()
    expect(panel.textContent).not.toMatch(/100%/)
  })

  it('renders nothing without a model record, or with an unreadable one', () => {
    const none = render(<ModelPanel items={[]} />)
    expect(none.container).toBeEmptyDOMElement()
    none.unmount()
    const bad = render(<ModelPanel items={[{ ...record({}), details_json: '{not json' }]} />)
    expect(bad.container).toBeEmptyDOMElement()
  })
})
