import { describe, it, expect } from 'vitest'
import {
  misconceptionLabel,
  misconceptionDescription,
  misconceptionColor,
  confidenceBand,
  confidenceBandLabel,
} from '../lib/labels'

const MODEL_LABELS = [
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

describe('misconceptionLabel', () => {
  it('returns a non-empty string for every model label', () => {
    for (const label of MODEL_LABELS) {
      const result = misconceptionLabel(label)
      expect(result, `label missing for ${label}`).toBeTruthy()
      expect(result).not.toBe('—')
    }
  })

  it('returns dash for null/undefined', () => {
    expect(misconceptionLabel(null)).toBe('—')
    expect(misconceptionLabel(undefined)).toBe('—')
  })

  it('falls back gracefully for unknown codes', () => {
    const result = misconceptionLabel('SOME_UNKNOWN_CODE')
    expect(result).toBeTruthy()
    expect(result).not.toBe('—')
  })
})

describe('misconceptionDescription', () => {
  it('returns a non-empty string for every model label', () => {
    for (const label of MODEL_LABELS) {
      const result = misconceptionDescription(label)
      expect(result, `description missing for ${label}`).toBeTruthy()
    }
  })

  it('returns empty string for null/undefined', () => {
    expect(misconceptionDescription(null)).toBe('')
    expect(misconceptionDescription(undefined)).toBe('')
  })
})

describe('misconceptionColor', () => {
  it('returns a hex color for every model label', () => {
    for (const label of MODEL_LABELS) {
      const result = misconceptionColor(label)
      expect(result, `color missing for ${label}`).toMatch(/^#[0-9a-fA-F]{6}$/)
    }
  })

  it('returns a neutral grey for null', () => {
    expect(misconceptionColor(null)).toMatch(/^#[0-9a-fA-F]{6}$/)
  })
})

describe('confidenceBand', () => {
  it('returns high for p >= 0.75', () => {
    expect(confidenceBand(0.75)).toBe('high')
    expect(confidenceBand(0.90)).toBe('high')
    expect(confidenceBand(1.0)).toBe('high')
  })

  it('returns medium for 0.5 <= p < 0.75', () => {
    expect(confidenceBand(0.50)).toBe('medium')
    expect(confidenceBand(0.60)).toBe('medium')
    expect(confidenceBand(0.74)).toBe('medium')
  })

  it('returns low for p < 0.5 or null', () => {
    expect(confidenceBand(0.49)).toBe('low')
    expect(confidenceBand(0.0)).toBe('low')
    expect(confidenceBand(null)).toBe('low')
    expect(confidenceBand(undefined)).toBe('low')
  })
})

describe('confidenceBandLabel', () => {
  it('returns correct label for each band', () => {
    expect(confidenceBandLabel(0.80)).toBe('High confidence')
    expect(confidenceBandLabel(0.60)).toBe('Some confidence')
    expect(confidenceBandLabel(0.30)).toBe('Low confidence')
  })
})
