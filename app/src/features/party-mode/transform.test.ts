import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { PartyModeRow } from './queries'

const makeRow = (overrides: Partial<PartyModeRow> = {}): PartyModeRow => ({
  constructor_id: 'Ferrari',
  race_pace_s: -0.83,
  quali_pace_s: -0.67,
  delta_s: 0.16,
  race_obs: 101,
  quali_obs: 12,
  ...overrides,
})

describe('transform', () => {
  it('classifies negative delta as party mode', () => {
    const entries = transform([makeRow({ delta_s: -0.38 })])
    expect(entries[0].mode).toBe('party')
  })

  it('classifies positive delta as race mode', () => {
    const entries = transform([makeRow({ delta_s: 0.59 })])
    expect(entries[0].mode).toBe('race')
  })

  it('classifies small delta as balanced', () => {
    const entries = transform([makeRow({ delta_s: 0.05 })])
    expect(entries[0].mode).toBe('balanced')
  })

  it('maps constructor_id to constructor', () => {
    const entries = transform([makeRow({ constructor_id: 'Red Bull Racing' })])
    expect(entries[0].constructor).toBe('Red Bull Racing')
  })

  it('returns empty for empty input', () => {
    expect(transform([])).toEqual([])
  })
})
