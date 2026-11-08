import { describe, it, expect } from 'vitest'
import { formatMlModelsTile } from './manifest'

describe('formatMlModelsTile (TX-07)', () => {
  it('shows significant/total from the manifest', () => {
    expect(formatMlModelsTile({ ml_models: 4, ml_models_total: 5 })).toBe('4/5')
    expect(formatMlModelsTile({ ml_models: 5, ml_models_total: 5 })).toBe('5/5')
  })

  it('shows "unknown" when either count is null or absent, never a made-up 5', () => {
    expect(formatMlModelsTile({ ml_models: null, ml_models_total: null })).toBe('unknown')
    expect(formatMlModelsTile({ ml_models: 5, ml_models_total: null })).toBe('unknown')
    expect(formatMlModelsTile({ ml_models: 5 })).toBe('unknown')
  })
})
