import { describe, it, expect } from 'vitest'
import { computeKM, parseNStints, transform } from './transform'
import type { StintSummaryRow } from './queries'

const makeStint = (overrides: Partial<StintSummaryRow>): StintSummaryRow => ({
  stint_id: 'test_stint',
  driver_id: 'VER',
  stint_length: 20,
  cliffed: false,
  degradation_s: 0.5,
  ...overrides,
})

describe('computeKM', () => {
  it('returns empty for no stints', () => {
    expect(computeKM([])).toHaveLength(0)
  })

  it('returns flat curve at 1.0 when no stints cliffed', () => {
    const stints = [
      makeStint({ stint_length: 20, cliffed: false }),
      makeStint({ stint_length: 25, cliffed: false }),
    ]
    const km = computeKM(stints)
    expect(km[0]).toEqual({ lap: 0, survival: 1 })
    expect(km[km.length-1].survival).toBe(1)
  })

  it('KM curve starts at 1.0', () => {
    const stints = [
      makeStint({ stint_length: 10, cliffed: true }),
      makeStint({ stint_length: 20, cliffed: false }),
    ]
    const km = computeKM(stints)
    expect(km[0]).toEqual({ lap: 0, survival: 1 })
  })

  it('single event: S(t) drops correctly at event time', () => {
    // 2 stints, 1 cliff at lap 10-at lap 10: 2 at risk, 1 event -> S = 1 * (1-1/2) = 0.5
    const stints = [
      makeStint({ stint_length: 10, cliffed: true }),
      makeStint({ stint_length: 15, cliffed: false }),
    ]
    const km = computeKM(stints)
    const atTen = km.find(p => p.lap === 10)
    expect(atTen).toBeDefined()
    expect(atTen!.survival).toBeCloseTo(0.5, 5)
  })

  it('two events: survival decreases monotonically', () => {
    const stints = [
      makeStint({ stint_length: 10, cliffed: true }),
      makeStint({ stint_length: 15, cliffed: true }),
      makeStint({ stint_length: 20, cliffed: false }),
    ]
    const km = computeKM(stints)
    for (let i = 1; i < km.length; i++) {
      expect(km[i].survival).toBeLessThanOrEqual(km[i-1].survival)
    }
  })

  it('censored stints reduce at-risk pool correctly', () => {
    // At lap 20: 3 stints at risk (all last >= 20). 1 event. S = 1-1/3 = 2/3.
    // At lap 25: only stint c at risk (a cliffed at 20, b pitted at 22, both < 25).
    // So at-risk = 1, events = 1 -> S = (2/3) * (1-1/1) = 0.
    const stints = [
      makeStint({ stint_id: 'a', stint_length: 20, cliffed: true }),
      makeStint({ stint_id: 'b', stint_length: 22, cliffed: false }),
      makeStint({ stint_id: 'c', stint_length: 25, cliffed: true }),
    ]
    const km = computeKM(stints)
    const at20 = km.find(p => p.lap === 20)!
    expect(at20.survival).toBeCloseTo(2 / 3, 5)
    // Verify curve is monotonically non-increasing
    for (let i = 1; i < km.length; i++) {
      expect(km[i].survival).toBeLessThanOrEqual(km[i-1].survival)
    }
  })

  it('survival never goes below 0', () => {
    const stints = Array.from({ length: 5 }, (_, i) =>
      makeStint({ stint_id: `s${i}`, stint_length: 10, cliffed: true })
    )
    const km = computeKM(stints)
    for (const p of km) {
      expect(p.survival).toBeGreaterThanOrEqual(0)
    }
  })
})

describe('parseNStints', () => {
  it('parses correctly from standard notes', () => {
    expect(parseNStints('fitted from 12 stints via cox_km_survival')).toBe(12)
  })

  it('returns null for non-standard notes', () => {
    expect(parseNStints('insufficient data (0 stints); used class defaults')).toBeNull()
  })

  it('returns null for null input', () => {
    expect(parseNStints(null)).toBeNull()
  })
})

describe('transform', () => {
  it('returns empty curve for empty stints', () => {
    const result = transform(null, [], 'SOFT')
    expect(result.kmCurve).toHaveLength(0)
    expect(result.stintObservations).toHaveLength(0)
    expect(result.compound).toBe('SOFT')
    expect(result.actualStintCount).toBe(0)
  })

  it('maps profile metadata onto result', () => {
    const profile = {
      circuit_key: '2023_1',
      compound_code: 'SOFT',
      season: 2023,
      compound_cliff_onset_laps: 18,
      compound_cliff_severity: 0.86,
      compound_wear_gradient: 0.07,
      compound_grip_peak: 1.03,
      compound_optimal_temp_low: 82,
      compound_optimal_temp_high: 108,
      fit_date: '2026-05-21',
      data_window: '2018_to_2024',
      notes: 'fitted from 33 stints via cox_km_survival',
    }
    const stints = [makeStint({ stint_length: 15, cliffed: false })]
    const result = transform(profile, stints, 'SOFT')
    expect(result.cliffOnsetLap).toBe(18)
    expect(result.cliffSeverity).toBe(0.86)
    expect(result.fitDate).toBe('2026-05-21')
    expect(result.dataWindow).toBe('2018_to_2024')
    expect(result.nStints).toBe(33)
  })

  it('builds one observation per stint', () => {
    const stints = [
      makeStint({ stint_id: 'a', driver_id: 'VER', stint_length: 18, cliffed: true, degradation_s: 1.2 }),
      makeStint({ stint_id: 'b', driver_id: 'HAM', stint_length: 22, cliffed: false, degradation_s: 0.9 }),
    ]
    const result = transform(null, stints, 'MEDIUM')
    expect(result.stintObservations).toHaveLength(2)
    expect(result.stintObservations[0]).toMatchObject({ endLap: 18, cliffed: true, degradation_s: 1.2, driver_id: 'VER' })
    expect(result.stintObservations[1]).toMatchObject({ endLap: 22, cliffed: false, degradation_s: 0.9, driver_id: 'HAM' })
  })
})
