import { describe, it, expect } from 'vitest'
import { transform, toCsvRows } from './transform'
import type { LapResidualRow } from './queries'

// fuel+compound+constructor+dirty_air = total_explained_s
const TOTAL_EXPLAINED = 1.4 + 2.5 + 0.5 + 0.1 // = 4.5
// pace_delta = total_explained + skill (track noise is informational, not summed)
const PACE_DELTA = TOTAL_EXPLAINED - 3.0 // = 1.5

const baseRow: LapResidualRow = {
  driver_id: 'VER',
  race_id: '2023_17',
  race_year: 2023,
  fuel_component_s: 1.4,
  compound_component_s: 2.5,
  constructor_component_s: 0.5,
  dirty_air_tax_s: 0.1,
  driver_skill_residual_s: -3.0,
  track_unexplained_s: -0.01,
  closed_fuel_component_s: 1.4,
  closed_compound_component_s: 2.5,
  closed_constructor_component_s: 0.5,
  closed_dirty_air_tax_s: 0.1,
  closed_driver_skill_residual_s: -3.0,
  pace_delta_s: PACE_DELTA,
  n_closed_laps: 40,
  n_laps: 40,
  n_fuel_component_s: 40,
  n_compound_component_s: 40,
  n_constructor_component_s: 40,
  n_dirty_air_tax_s: 40,
  n_driver_skill_residual_s: 40,
  n_track_unexplained_s: 40,
}

describe('transform', () => {
  it('produces five identity bars plus a track-noise diagnostic bar', () => {
    const result = transform(baseRow)
    expect(result.bars).toHaveLength(6)
    expect(result.bars[0].label).toBe('Fuel')
    expect(result.bars[3].label).toBe('Dirty Air')
    expect(result.bars[4].label).toBe('Driver Skill')
    expect(result.bars[5].label).toBe('Track noise')
  })

  it('track noise does not affect closure or the running cumsum', () => {
    const a = transform(baseRow)
    const b = transform({ ...baseRow, track_unexplained_s: 5 })
    expect(b.closureGap).toBeCloseTo(a.closureGap as number, 9)
    expect(b.bars[5].start).toBe(0)
  })

  it('assigns sign correctly', () => {
    const result = transform(baseRow)
    expect(result.bars[0].sign).toBe('positive')  // fuel = +1.4
    expect(result.bars[4].sign).toBe('negative')  // skill = -3.0
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
    expect(Math.abs(result.closureGap as number)).toBeLessThan(1e-9)
  })

  it('closure gap is non-zero when identity breaks', () => {
    const row = { ...baseRow, pace_delta_s: 99.0 }
    const result = transform(row)
    expect(Math.abs(result.closureGap as number)).toBeGreaterThan(1e-4)
  })

  it('preserves driver_id and n_laps', () => {
    const result = transform(baseRow)
    expect(result.driverId).toBe('VER')
    expect(result.nLaps).toBe(40)
  })

  it('a NULL component is an unavailable bar and the next bar ignores it', () => {
    const r = transform({
      ...baseRow, compound_component_s: null, n_compound_component_s: 0,
      pace_delta_s: null, n_closed_laps: 0,
    })
    expect(r.bars[1].unavailable).toBe(true)
    expect(r.bars[1].value).toBeNull()
    expect(r.bars[1].note).toBe('no measured laps')
    // Constructor starts where Fuel ended: compound added nothing
    expect(r.bars[2].start).toBeCloseTo(1.4, 9)
  })

  it('closure gap is NULL when any identity term is NULL, and unchanged otherwise', () => {
    expect(transform({ ...baseRow, driver_skill_residual_s: null, n_driver_skill_residual_s: 0, pace_delta_s: null, n_closed_laps: 0 }).closureGap).toBeNull()
    expect(transform({ ...baseRow, dirty_air_tax_s: null, n_dirty_air_tax_s: 0, n_closed_laps: 0, pace_delta_s: null }).closureGap).toBeNull()
    expect(Math.abs(transform(baseRow).closureGap as number)).toBeLessThan(1e-9)
  })

  it('a NULL track-noise diagnostic is unavailable and does not touch closure', () => {
    const r = transform({ ...baseRow, track_unexplained_s: null, n_track_unexplained_s: 0 })
    expect(r.bars[5].unavailable).toBe(true)
    expect(Math.abs(r.closureGap as number)).toBeLessThan(1e-9)
  })

  it('writes an empty CSV cell for a NULL component, not 0', () => {
    const r = transform({ ...baseRow, driver_skill_residual_s: null, n_driver_skill_residual_s: 0, pace_delta_s: null, n_closed_laps: 0 })
    const rows = toCsvRows([r])
    const skill = rows.find(x => x.component === 'Driver Skill')
    expect(skill?.value_s).toBe('')
    expect(skill?.closure_gap_s).toBe('')
    expect(rows.find(x => x.component === 'Fuel')?.value_s).toBe('1.400000')
  })

  it('n_component < n_laps sets the partial-coverage note', () => {
    const r = transform({ ...baseRow, n_closed_laps: 31 })
    expect(r.bars[1].note).toBe('based on 31 of 40 laps')
    expect(r.bars[1].unavailable).toBeUndefined()
  })

  // AP-06 fixture: 40 laps, 8 with compound unknown, so the closed set is 32 laps. Own-coverage means
  // (fuel 1.5 over 40 laps) differ from the closed-set mean (1.4); the bars must use the closed set.
  const mixed: LapResidualRow = {
    ...baseRow,
    fuel_component_s: 1.5, constructor_component_s: 0.55,
    n_compound_component_s: 32, n_dirty_air_tax_s: 32, n_driver_skill_residual_s: 32,
    n_closed_laps: 32,
  }

  it('AP-06: bars sum to the displayed pace delta over the same lap set', () => {
    const r = transform(mixed)
    const sum = r.bars.slice(0, 5).reduce((a, b) => a + (b.value as number), 0)
    expect(sum).toBeCloseTo(r.paceDeltaS as number, 9)
    expect(r.bars[0].value).toBe(1.4) // closed-set mean, not the 40-lap 1.5
    expect(r.bars[0].note).toBe('based on 32 of 40 laps')
    expect(r.nClosedLaps).toBe(32)
    expect(Math.abs(r.closureGap as number)).toBeLessThan(1e-9)
  })

  it('AP-06: empty closed set -> closure n/a; a NULL-only component keeps its unavailable bar', () => {
    const r = transform({
      ...mixed, n_closed_laps: 0, pace_delta_s: null,
      closed_fuel_component_s: null, closed_compound_component_s: null, closed_constructor_component_s: null,
      closed_dirty_air_tax_s: null, closed_driver_skill_residual_s: null,
      compound_component_s: null, n_compound_component_s: 0,
    })
    expect(r.closureGap).toBeNull()
    expect(r.paceDeltaS).toBeNull()
    expect(r.bars[1].unavailable).toBe(true)
    expect(r.bars[0].value).toBe(1.5) // fuel falls back to its own coverage
  })
})
