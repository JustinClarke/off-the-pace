import { describe, it, expect } from 'vitest'
import { transform, toCsvRows, meanOfRaces } from './transform'
import type { TeamAverageRow } from './queries'

const mkRow = (constructor_id: string, overrides: Partial<TeamAverageRow> = {}): TeamAverageRow => ({
  constructor_id,
  drivers_n: 2,
  laps_n: 400,
  avg_car_component_s: 0.1,
  avg_dirty_air_tax_s: 0.05,
  n_dirty_air_laps: 300,
  avg_driver_skill_residual_s: -0.02,
  ...overrides,
})

describe('transform', () => {
  it('ranks teams in the order given and keeps driver counts', () => {
    const out = transform([mkRow('MERCEDES'), mkRow('FERRARI', { drivers_n: 1 })])
    expect(out.map(e => [e.rank, e.constructor, e.drivers])).toEqual([[1, 'MERCEDES', 2], [2, 'FERRARI', 1]])
  })

  it('keeps null team averages as null', () => {
    const [e] = transform([mkRow('ALPINE', { avg_dirty_air_tax_s: null, n_dirty_air_laps: 0 })])
    expect(e.dirty_air_s).toBeNull()
  })

  it('AP-05: a team-season whose dirty-air laps are all unmeasured is unavailable, never 0', () => {
    // A stale 0.0 average with zero measured laps must not surface as a measured zero.
    const [e] = transform([mkRow('HAAS', { avg_dirty_air_tax_s: 0, n_dirty_air_laps: 0 })])
    expect(e.dirty_air_s).toBeNull()
    expect(e.n_dirty_air_laps).toBe(0)
    expect(toCsvRows([e])[0].dirty_air_tax_avg_s).toBe('')
  })

  it('AP-05: a measured team-season keeps its mean and its measured-lap count', () => {
    const [e] = transform([mkRow('MERCEDES', { avg_dirty_air_tax_s: 0.2, n_dirty_air_laps: 120 })])
    expect(e.dirty_air_s).toBe(0.2)
    expect(e.n_dirty_air_laps).toBe(120)
  })
})

describe('meanOfRaces', () => {
  it('averages within each race first, then across races', () => {
    // Race A: both drivers run (1, 3) -> race mean 2. Race B: one driver (10) -> race mean 10.
    // Per-race answer is 6; a plain mean over all readings (or per driver) would give 4.67 or 6.5.
    const v = meanOfRaces([
      { race: 'A', value: 1 },
      { race: 'A', value: 3 },
      { race: 'B', value: 10 },
    ])
    expect(v).toBeCloseTo(6, 10)
  })

  it('returns null when there are no readings', () => {
    expect(meanOfRaces([])).toBeNull()
  })
})

describe('toCsvRows', () => {
  it('formats to three decimals and leaves missing readings blank', () => {
    const csv = toCsvRows(transform([mkRow('HAAS', { avg_dirty_air_tax_s: null, n_dirty_air_laps: 0, avg_car_component_s: 0.12345 })]))
    expect(csv[0].car_component_avg_s).toBe('0.123')
    expect(csv[0].dirty_air_tax_avg_s).toBe('')
  })
})
