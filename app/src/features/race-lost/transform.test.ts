import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { RaceLostRow } from './queries'

const row: RaceLostRow = {
  total_fuel_s: -5.0,
  total_compound_s: 2.0,
  total_rubber_s: -1.5,
  total_ambient_s: 0.5,
  total_constructor_s: -3.0,
  total_dirty_air_s: 8.0,
  total_skill_s: -4.0,
  total_track_s: 0.0,
  total_explained_s: 1.0,
  total_pace_delta_s: -3.0,
  n_laps: 55,
}

describe('transform', () => {
  it('produces 8 bars', () => {
    const { bars } = transform(row)
    expect(bars).toHaveLength(8)
  })

  it('labels are correct', () => {
    const { bars } = transform(row)
    expect(bars[0].label).toBe('Fuel')
    expect(bars[6].label).toBe('Driver Skill')
  })

  it('computes cumulative starts correctly', () => {
    const { bars } = transform(row)
    // Fuel is -5, so it starts at -5 (value<0: start = 0 + -5)
    expect(bars[0].start).toBe(-5.0)
    // Compound is +2, starts at -5 (previous cumsum)
    expect(bars[1].start).toBeCloseTo(-5.0)
  })

  it('assigns correct signs', () => {
    const { bars } = transform(row)
    expect(bars[0].sign).toBe('negative') // fuel -5
    expect(bars[1].sign).toBe('positive') // compound +2
  })

  it('passes nLaps through', () => {
    const { nLaps } = transform(row)
    expect(nLaps).toBe(55)
  })
})
