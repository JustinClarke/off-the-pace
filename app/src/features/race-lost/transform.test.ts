import { describe, it, expect } from 'vitest'
import { transform, toCsvRows } from './transform'
import type { RaceLostRow } from './queries'

const row: RaceLostRow = {
  total_fuel_s: -5.0,
  total_compound_s: 2.0,
  total_constructor_s: -3.0,
  total_dirty_air_s: 8.0,
  total_skill_s: -4.0,
  total_track_s: 0.0,
  closed_fuel_s: -5.0,
  closed_compound_s: 2.0,
  closed_constructor_s: -3.0,
  closed_dirty_air_s: 8.0,
  closed_skill_s: -4.0,
  total_pace_delta_s: -2.0,
  n_closed_laps: 55,
  n_laps: 55,
  n_fuel_component_s: 55,
  n_compound_component_s: 55,
  n_constructor_component_s: 55,
  n_dirty_air_tax_s: 55,
  n_driver_skill_residual_s: 55,
  n_track_unexplained_s: 55,
}

describe('transform', () => {
  it('produces 6 bars', () => {
    const { bars } = transform(row)
    expect(bars).toHaveLength(6)
  })

  it('labels are correct', () => {
    const { bars } = transform(row)
    expect(bars[0].label).toBe('Fuel')
    expect(bars[4].label).toBe('Driver Skill')
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

  it('a NULL total is an unavailable bar and the next bar ignores it', () => {
    const { bars } = transform({ ...row, total_compound_s: null, n_compound_component_s: 0, total_pace_delta_s: null, n_closed_laps: 0 })
    expect(bars[1].unavailable).toBe(true)
    expect(bars[1].value).toBeNull()
    expect(bars[2].start).toBe(-8.0) // constructor -3 starts at fuel -5 + -3
  })

  it('closure gap is NULL when a term is NULL and ~0 otherwise', () => {
    expect(transform({ ...row, total_skill_s: null, n_driver_skill_residual_s: 0, total_pace_delta_s: null, n_closed_laps: 0 }).closureGap).toBeNull()
    expect(Math.abs(transform(row).closureGap as number)).toBeLessThan(1e-9)
  })

  it('CSV cell is empty for a NULL total', () => {
    const csv = toCsvRows('RIC', { ...row, total_skill_s: null, n_driver_skill_residual_s: 0, total_pace_delta_s: null, n_closed_laps: 0 })
    expect(csv.find(r => r.component === 'Driver Skill')?.total_s).toBe('')
    expect(csv.find(r => r.component === 'Fuel')?.total_s).toBe('-5.0000')
  })

  it('n_component < n_laps sets the partial-coverage note', () => {
    const { bars } = transform({ ...row, n_closed_laps: 40 })
    expect(bars[3].note).toBe('based on 40 of 55 laps')
  })

  // AP-06 fixture: 60 laps, but compound is unknown on 10 of them, so the closed set is 50 laps.
  // Own-coverage sums (total_*) mix 60 and 50 laps; the closed_* sums and the pace delta are over the same 50.
  const mixed: RaceLostRow = {
    ...row,
    total_fuel_s: -6.0, total_compound_s: 2.0, total_constructor_s: -3.6, total_dirty_air_s: 8.0, total_skill_s: -4.0,
    closed_fuel_s: -5.0, closed_compound_s: 2.0, closed_constructor_s: -3.0, closed_dirty_air_s: 8.0, closed_skill_s: -4.0,
    total_pace_delta_s: -2.0, // -5 + 2 - 3 + 8 - 4, over the 50 closed laps
    n_closed_laps: 50, n_laps: 60,
    n_fuel_component_s: 60, n_compound_component_s: 50, n_constructor_component_s: 60,
    n_dirty_air_tax_s: 50, n_driver_skill_residual_s: 50, n_track_unexplained_s: 60,
  }

  it('AP-06: the five identity bars sum to the displayed pace delta, and closure is ~0', () => {
    const r = transform(mixed)
    const sum = r.bars.slice(0, 5).reduce((a, b) => a + (b.value as number), 0)
    expect(sum).toBeCloseTo(r.totalPaceDelta as number, 9)
    expect(Math.abs(r.closureGap as number)).toBeLessThan(1e-9)
    expect(r.nClosedLaps).toBe(50)
    // bars use the closed set (-5, not the 60-lap -6) and say so
    expect(r.bars[0].value).toBe(-5.0)
    expect(r.bars[0].note).toBe('based on 50 of 60 laps')
  })

  it('AP-06: Track Noise stays out of the identity and the closure', () => {
    const r = transform({ ...mixed, total_track_s: 9 })
    expect(Math.abs(r.closureGap as number)).toBeLessThan(1e-9)
  })

  it('AP-06: a pace delta that does not match the closed terms shows a gap', () => {
    expect(Math.abs(transform({ ...mixed, total_pace_delta_s: 5 }).closureGap as number)).toBeGreaterThan(1e-4)
  })

  it('AP-06: empty closed set -> closure n/a, a NULL-only component keeps its unavailable bar, others use own coverage', () => {
    const r = transform({
      ...mixed, n_closed_laps: 0, total_pace_delta_s: null,
      closed_fuel_s: null, closed_compound_s: null, closed_constructor_s: null, closed_dirty_air_s: null, closed_skill_s: null,
      total_compound_s: null, n_compound_component_s: 0,
    })
    expect(r.closureGap).toBeNull()
    expect(r.totalPaceDelta).toBeNull()
    expect(r.bars[1].unavailable).toBe(true)
    expect(r.bars[0].value).toBe(-6.0)
  })

  it('AP-06: CSV carries the displayed (closed-set) values', () => {
    const csv = toCsvRows('RIC', mixed)
    expect(csv.find(x => x.component === 'Fuel')?.total_s).toBe('-5.0000')
  })
})
