import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { ConstructorPaceRow } from './queries'

const makeRow = (overrides: Partial<ConstructorPaceRow> = {}): ConstructorPaceRow => ({
  constructor_id: 'Ferrari',
  constructor_structural_pace_s: -0.83,
  constructor_structural_pace_se_s: 0.10,
  constructor_structural_pace_ci_low_s: -1.03,
  constructor_structural_pace_ci_high_s: -0.63,
  panel_observations_n: 101,
  races_n: 1,
  ...overrides,
})

describe('transform', () => {
  it('assigns rank starting at 1', () => {
    const entries = transform([makeRow(), makeRow({ constructor_id: 'McLaren' })])
    expect(entries[0].rank).toBe(1)
    expect(entries[1].rank).toBe(2)
  })

  it('maps constructor_id to constructor field', () => {
    const entries = transform([makeRow({ constructor_id: 'Red Bull Racing' })])
    expect(entries[0].constructor).toBe('Red Bull Racing')
  })

  it('carries pace and CI through', () => {
    const entries = transform([makeRow()])
    expect(entries[0].pace_s).toBeCloseTo(-0.83)
    expect(entries[0].ci_low_s).toBeCloseTo(-1.03)
    expect(entries[0].ci_high_s).toBeCloseTo(-0.63)
  })

  it('returns empty for empty input', () => {
    expect(transform([])).toEqual([])
  })
})
