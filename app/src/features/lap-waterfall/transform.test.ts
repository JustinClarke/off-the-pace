import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { LapResidualRow } from './queries'

// fuel+compound+rubber+ambient+constructor+dirty_air = total_explained_s
const TOTAL_EXPLAINED = 1.4 + 2.5-0.01 + 0.002 + 0.5 + 0.1 // = 4.492
// pace_delta = total_explained + skill + track
const PACE_DELTA = TOTAL_EXPLAINED-3.0-0.01 // = 1.482

const baseRow: LapResidualRow = {
  driver_id: 'VER',
  race_id: '2023_17',
  race_year: 2023,
  fuel_component_s: 1.4,
  compound_component_s: 2.5,
  rubber_component_s: -0.01,
  ambient_component_s: 0.002,
  constructor_component_s: 0.5,
  dirty_air_tax_s: 0.1,
  driver_skill_residual_s: -3.0,
  track_unexplained_s: -0.01,
  total_explained_s: TOTAL_EXPLAINED,
  pace_delta_s: PACE_DELTA,
  n_laps: 40,
}

describe('transform', () => {
  it('produces one bar per component in order', () => {
    const result = transform(baseRow)
    expect(result.bars).toHaveLength(8)
    expect(result.bars[0].label).toBe('Fuel')
    expect(result.bars[5].label).toBe('Dirty Air')
    expect(result.bars[6].label).toBe('Driver Skill')
  })

  it('assigns sign correctly', () => {
    const result = transform(baseRow)
    expect(result.bars[0].sign).toBe('positive')  // fuel = +1.4
    expect(result.bars[6].sign).toBe('negative')  // skill = -3.0
  })

  it('bar start offsets form a running cumsum', () => {
    const result = transform(baseRow)
    // Fuel bar: value=1.4, positive → start=0
    expect(result.bars[0].start).toBeCloseTo(0, 5)
    // Compound bar: value=2.5, positive → start=1.4
    expect(result.bars[1].start).toBeCloseTo(1.4, 5)
  })

  it('closure gap is near zero when components sum to pace_delta_s', () => {
    const result = transform(baseRow)
    expect(Math.abs(result.closureGap)).toBeLessThan(1e-9)
  })

  it('closure gap is non-zero when identity breaks', () => {
    const row = { ...baseRow, pace_delta_s: 99.0 }
    const result = transform(row)
    expect(Math.abs(result.closureGap)).toBeGreaterThan(1e-4)
  })

  it('preserves driver_id and n_laps', () => {
    const result = transform(baseRow)
    expect(result.driverId).toBe('VER')
    expect(result.nLaps).toBe(40)
  })
})
