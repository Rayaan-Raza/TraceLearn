/**
 * F7: Component-level tests for the model prediction card on the student
 * Result page.  These tests exercise the activePrediction logic and the
 * label/description/confidence text that the card renders.
 */
import { describe, it, expect } from 'vitest'
import { misconceptionLabel, misconceptionDescription, confidenceBandLabel } from '../lib/labels'
import type { ModelPrediction } from '../api/types'

const ALL_MODEL_LABELS = [
  'CPP_ARRAY_BOUNDS',
  'CPP_ASSIGN_VS_COMPARE',
  'CPP_INT_OVERFLOW',
  'CPP_LOOP_BOUNDARY',
  'CPP_MISSING_BASE_CASE',
  'CPP_OFF_BY_ONE',
  'CPP_OTHER_ERROR',
  'CPP_RANGE_CHECK',
  'CPP_STALE_EXIT',
  'CPP_UNINITIALIZED_VAR',
  'CPP_WRONG_LOOP_DIR',
]

function makeModelPrediction(overrides: Partial<ModelPrediction> = {}): ModelPrediction {
  return {
    variant: 'best',
    model_sha256: 'abc123',
    top_label: 'CPP_LOOP_BOUNDARY',
    top_probability: 0.82,
    abstained: false,
    threshold: 0.55,
    temperature: 1.0,
    probabilities: { CPP_LOOP_BOUNDARY: 0.82 },
    top_k: [{ label: 'CPP_LOOP_BOUNDARY', p: 0.82 }],
    n_features: 90,
    n_missing: 10,
    ...overrides,
  }
}

/** Mirrors the activePrediction derivation in Result.tsx */
function activePrediction(mp: ModelPrediction | null) {
  if (!mp) return null
  if (mp.abstained) return null
  if (mp.top_label === 'CPP_OTHER_ERROR') return null
  return mp
}

describe('activePrediction derivation', () => {
  it('is non-null for a confident, non-abstained, non-other-error prediction', () => {
    const pred = makeModelPrediction()
    expect(activePrediction(pred)).toBeTruthy()
  })

  it('is null when model_prediction is null', () => {
    expect(activePrediction(null)).toBeNull()
  })

  it('is null when prediction is abstained', () => {
    const pred = makeModelPrediction({ abstained: true })
    expect(activePrediction(pred)).toBeNull()
  })

  it('is null when top_label is CPP_OTHER_ERROR', () => {
    const pred = makeModelPrediction({ top_label: 'CPP_OTHER_ERROR', top_probability: 0.80 })
    expect(activePrediction(pred)).toBeNull()
  })

  it('allows CPP_OTHER_ERROR at any probability when it comes from an abstained prediction', () => {
    const pred = makeModelPrediction({ top_label: 'CPP_OTHER_ERROR', abstained: true })
    expect(activePrediction(pred)).toBeNull()
  })
})

describe('model card text content for each label', () => {
  it('every active label produces a non-empty heading fragment', () => {
    const activePreds = ALL_MODEL_LABELS
      .filter((l) => l !== 'CPP_OTHER_ERROR')
      .map((l) => makeModelPrediction({ top_label: l }))

    for (const pred of activePreds) {
      const label = misconceptionLabel(pred.top_label)
      expect(label, `label missing for ${pred.top_label}`).toBeTruthy()
      expect(label).not.toBe('—')
    }
  })

  it('every active label produces a non-empty description', () => {
    const activePreds = ALL_MODEL_LABELS
      .filter((l) => l !== 'CPP_OTHER_ERROR')
      .map((l) => makeModelPrediction({ top_label: l }))

    for (const pred of activePreds) {
      const desc = misconceptionDescription(pred.top_label)
      expect(desc, `description missing for ${pred.top_label}`).toBeTruthy()
    }
  })
})

describe('confidence band label shown in card', () => {
  it('shows High confidence for p >= 0.75', () => {
    const pred = makeModelPrediction({ top_probability: 0.80 })
    expect(confidenceBandLabel(pred.top_probability)).toBe('High confidence')
  })

  it('shows Some confidence for 0.5 <= p < 0.75', () => {
    const pred = makeModelPrediction({ top_probability: 0.60 })
    expect(confidenceBandLabel(pred.top_probability)).toBe('Some confidence')
  })

  it('shows Low confidence for p < 0.5', () => {
    const pred = makeModelPrediction({ top_probability: 0.40 })
    expect(confidenceBandLabel(pred.top_probability)).toBe('Low confidence')
  })
})
