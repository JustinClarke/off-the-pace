import { describe, it, expect } from 'vitest'
import { transform, wilson, summarisePooled, hazardContext } from './transform'
import type { CautionLapRow, HazardRow, PooledRateRow } from './queries'

function lap(n: number, status: CautionLapRow['caution_status'], raceLaps = 10): CautionLapRow {
  return { lap_number: n, caution_status: status, race_laps: raceLaps }
}

describe('transform', () => {
  it('returns an empty timeline for no rows', () => {
    const r = transform([])
    expect(r.raceLaps).toBe(0)
    expect(r.segments).toHaveLength(0)
  })

  it('merges contiguous laps of the same kind into one segment', () => {
    const r = transform([
      lap(1, 'green'), lap(2, 'safety_car'), lap(3, 'safety_car'),
      lap(4, 'safety_car'), lap(5, 'green'),
    ])
    expect(r.segments).toHaveLength(1)
    expect(r.segments[0]).toMatchObject({ kind: 'safety_car', startLap: 2, endLap: 4, laps: 3 })
    expect(r.cautionLaps).toBe(3)
    expect(r.greenLaps).toBe(2)
  })

  it('splits when the kind changes with no green lap between', () => {
    const r = transform([lap(1, 'safety_car'), lap(2, 'vsc'), lap(3, 'vsc')])
    expect(r.segments.map(s => s.kind)).toEqual(['safety_car', 'vsc'])
    expect(r.segments[1].laps).toBe(2)
  })

  it('splits on a gap in lap numbers even within the same kind', () => {
    const r = transform([lap(2, 'vsc'), lap(7, 'vsc')])
    expect(r.segments).toHaveLength(2)
    expect(r.segments.every(s => s.laps === 1)).toBe(true)
  })

  it('closes a segment that runs to the chequered flag', () => {
    const r = transform([lap(8, 'green'), lap(9, 'red_flag'), lap(10, 'red_flag')])
    expect(r.segments).toHaveLength(1)
    expect(r.segments[0].endLap).toBe(10)
  })
})

describe('wilson', () => {
  it('is degenerate at n = 0 rather than NaN', () => {
    expect(wilson(0, 0)).toEqual([0, 0])
  })

  it('brackets the point estimate and stays inside [0, 1] at the edges', () => {
    const [lo, hi] = wilson(110, 149)
    expect(lo).toBeLessThan(110 / 149)
    expect(hi).toBeGreaterThan(110 / 149)
    const [elo, ehi] = wilson(6, 6)
    expect(elo).toBeGreaterThanOrEqual(0)
    expect(ehi).toBeLessThanOrEqual(1)
    // The whole point of the ruling: 6/6 does NOT report as a certainty.
    expect(elo).toBeLessThan(0.7)
  })
})

describe('summarisePooled', () => {
  const rows: PooledRateRow[] = [
    { race_year: 2018, races: 2, races_with_caution: 2, races_with_sc: 1, races_with_vsc: 1, races_with_red: 0, caution_laps: 4, total_laps: 20 },
    { race_year: 2019, races: 2, races_with_caution: 1, races_with_sc: 1, races_with_vsc: 0, races_with_red: 0, caution_laps: 2, total_laps: 20 },
    { race_year: null, races: 4, races_with_caution: 3, races_with_sc: 2, races_with_vsc: 1, races_with_red: 0, caution_laps: 6, total_laps: 40 },
  ]

  it('reads the total from the ROLLUP row and keeps the seasons separate', () => {
    const s = summarisePooled(rows)!
    expect(s.races).toBe(4)
    expect(s.anyCaution.rate).toBeCloseTo(0.75)
    expect(s.cautionLapShare).toBeCloseTo(0.15)
    expect(s.perSeason.map(p => p.season)).toEqual([2018, 2019])
  })

  it('returns null when the total row is absent rather than inventing one', () => {
    expect(summarisePooled(rows.filter(r => r.race_year !== null))).toBeNull()
  })
})

describe('hazardContext', () => {
  const base: HazardRow = {
    circuit_slug: 'monaco_grand_prix',
    season: 2019,
    prior_races_n: 1,
    prior_racing_laps: 78,
    sc_hazard_per_lap_shrunk: 0.024,
    vsc_hazard_per_lap_shrunk: 0.01,
    any_hazard_per_lap_shrunk: 0.031,
  }

  it('flags an all-null rate row as unmeasurable, never as zero', () => {
    const c = hazardContext([{
      ...base,
      season: 2018,
      prior_races_n: 0,
      prior_racing_laps: 0,
      sc_hazard_per_lap_shrunk: null,
      vsc_hazard_per_lap_shrunk: null,
      any_hazard_per_lap_shrunk: null,
    }])
    expect(c.unmeasurable).toBe(true)
    expect(c.ownDataWeight).toBe(0)
  })

  it('reports how little of a shrunk value is the circuit own data', () => {
    const c = hazardContext([base])
    expect(c.unmeasurable).toBe(false)
    expect(c.ownDataWeight).toBeCloseTo(78 / 678, 4)
    expect(c.ownDataWeight).toBeLessThan(0.15)
  })

  it('handles a venue with no row at all', () => {
    expect(hazardContext([]).unmeasurable).toBe(true)
  })
})
