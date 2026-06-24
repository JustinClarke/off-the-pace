import { describe, it, expect } from 'vitest'
import { transform, toCsvRows, CONFIDENCE_FLOOR } from './transform'
import type { EraAffinityRow } from './queries'

function makeRow(overrides: Partial<EraAffinityRow> = {}): EraAffinityRow {
  return {
    driver_id: 'HAM',
    circuit_id: 'silverstone_circuit',
    circuit_name: 'Silverstone Circuit',
    era_key: 'post2022',
    era_label: '2022–2024',
    n_obs: 3,
    seasons_observed_n: 3,
    raw_affinity_s: -0.4,
    shrunk_affinity_s: -0.3,
    shrunk_affinity_se_s: 0.12,
    shrunk_affinity_ci_low_s: -0.54,
    shrunk_affinity_ci_high_s: -0.06,
    affinity_confidence: 0.375,
    constructor_id: 'Mercedes',
    ...overrides,
  }
}

describe('transform', () => {
  it('returns null for no rows', () => {
    expect(transform([])).toBeNull()
  })

  it('ranks entries fastest (most negative affinity) first', () => {
    const rows = [
      makeRow({ driver_id: 'VER', shrunk_affinity_s: -0.1 }),
      makeRow({ driver_id: 'HAM', shrunk_affinity_s: -0.5 }),
      makeRow({ driver_id: 'NOR', shrunk_affinity_s: 0.2 }),
    ]
    const r = transform(rows)!
    expect(r.entries.map(e => e.driverId)).toEqual(['HAM', 'VER', 'NOR'])
    expect(r.entries.map(e => e.rank)).toEqual([1, 2, 3])
  })

  it('computes gap-to-leader against the fastest row passed in', () => {
    const rows = [
      makeRow({ driver_id: 'VER', shrunk_affinity_s: -0.1 }),
      makeRow({ driver_id: 'HAM', shrunk_affinity_s: -0.5 }),
    ]
    const r = transform(rows)!
    expect(r.entries[0].gapToLeaderS).toBeCloseTo(0) // leader
    expect(r.entries[1].gapToLeaderS).toBeCloseTo(0.4) // -0.1 − (−0.5)
  })

  it('carries circuit + era metadata onto the result', () => {
    const r = transform([makeRow({ circuit_name: 'Monaco', era_label: '2018–2021' })])!
    expect(r.circuitName).toBe('Monaco')
    expect(r.eraLabel).toBe('2018–2021')
    expect(r.totalDrivers).toBe(1)
  })

  it('passes through confidence, races, seasons and CI', () => {
    const r = transform([
      makeRow({ affinity_confidence: 0.44, n_obs: 4, seasons_observed_n: 4, shrunk_affinity_ci_low_s: -0.6, shrunk_affinity_ci_high_s: -0.1 }),
    ])!
    const e = r.entries[0]
    expect(e.confidence).toBeCloseTo(0.44)
    expect(e.races).toBe(4)
    expect(e.seasons).toBe(4)
    expect(e.ciLowS).toBeCloseTo(-0.6)
    expect(e.ciHighS).toBeCloseTo(-0.1)
  })

  it('CONFIDENCE_FLOOR is the prior-dominated threshold (0.3)', () => {
    expect(CONFIDENCE_FLOOR).toBe(0.3)
  })

  it('toCsvRows produces one row per entry in rank order', () => {
    const rows = [
      makeRow({ driver_id: 'VER', shrunk_affinity_s: -0.1 }),
      makeRow({ driver_id: 'HAM', shrunk_affinity_s: -0.5 }),
    ]
    const csv = toCsvRows(transform(rows)!)
    expect(csv).toHaveLength(2)
    expect(csv[0].driver_id).toBe('HAM')
    expect(csv[0].rank).toBe(1)
  })
})
