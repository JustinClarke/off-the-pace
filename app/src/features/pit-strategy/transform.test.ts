import { describe, it, expect } from 'vitest'
import { transform, toCsvRows } from './transform'
import { pitConfidenceLabel } from '../../ui/charts/ganttLabels'
import type { PitGanttRow } from './queries'

const baseRow = (overrides: Partial<PitGanttRow> = {}): PitGanttRow => ({
  driver_id: 'VER',
  constructor_id: 'Red Bull',
  stint_number: 1,
  compound: 'SOFT',
  start_lap: 1,
  end_lap: 14,
  stint_length_laps: 14,
  next_compound: null,
  cliff_lap_in_stint: null,
  tyre_management_score: null,
  verdict: 'unknown',
  overrun_laps: null,
  opportunity_cost_s: null,
  optimal_pit_lap_in_stint: null,
  pit_lane_loss_s: 21.5,
  optimal_pit_lap_confidence: null,
  ...overrides,
})

describe('transform', () => {
  it('returns one stint per row', () => {
    const rows = [baseRow(), baseRow({ driver_id: 'LEC', stint_number: 1, start_lap: 1, end_lap: 12 })]
    const result = transform(rows, 57)
    expect(result.stints).toHaveLength(2)
    expect(result.totalLaps).toBe(57)
  })

  it('counts verdicts correctly', () => {
    const rows = [
      baseRow({ verdict: 'optimal' }),
      baseRow({ driver_id: 'LEC', verdict: 'overran', opportunity_cost_s: 3.5 }),
      baseRow({ driver_id: 'HAM', verdict: 'unknown' }),
    ]
    const result = transform(rows, 57)
    expect(result.verdictCounts.optimal).toBe(1)
    expect(result.verdictCounts.overran).toBe(1)
    expect(result.verdictCounts.unknown).toBe(1)
  })

  it('keeps early and undercut_forced as themselves, not null', () => {
    // The SQL has always been able to emit these two, but coerceVerdict used to
    // drop anything outside optimal/overran/unknown to null. It went unnoticed
    // while the threshold-based model produced 5 such stints across 7 seasons;
    // the Total_Cost(L) argmin produces 1,938, so a silent coercion here would
    // grey out a quarter of the chart.
    const rows = [
      baseRow({ verdict: 'early' }),
      baseRow({ driver_id: 'LEC', verdict: 'undercut_forced' }),
    ]
    const result = transform(rows, 57)
    expect(result.stints[0].verdict).toBe('early')
    expect(result.stints[1].verdict).toBe('undercut_forced')
    expect(result.verdictCounts.early).toBe(1)
    expect(result.verdictCounts.undercut_forced).toBe(1)
    expect(result.verdictCounts.unknown).toBe(0)
  })

  it('sums opportunity cost', () => {
    const rows = [
      baseRow({ opportunity_cost_s: 4.2 }),
      baseRow({ driver_id: 'LEC', opportunity_cost_s: 1.1 }),
      baseRow({ driver_id: 'HAM', opportunity_cost_s: null }),
    ]
    const result = transform(rows, 57)
    expect(result.totalOpportunityCostS).toBeCloseTo(5.3)
  })

  it('topCostStints excludes negligible costs', () => {
    const rows = [
      baseRow({ opportunity_cost_s: 0.05 }),
      baseRow({ driver_id: 'LEC', opportunity_cost_s: 15.0 }),
    ]
    const result = transform(rows, 57)
    expect(result.topCostStints).toHaveLength(1)
    expect(result.topCostStints[0].driverId).toBe('LEC')
  })

  it('widens the lap axis to a stint that ends past the last valid lap', () => {
    // WI-13 (F31): a stint now ends on the lap it really ended on. The race
    // summary's lap count is the last VALID lap, so a race that finished under a
    // safety car reads short of its final stint (12 of 172 races, up to 6 laps).
    const rows = [
      baseRow({ start_lap: 1, end_lap: 30 }),
      baseRow({ stint_number: 2, start_lap: 31, end_lap: 61 }),
    ]
    expect(transform(rows, 57).totalLaps).toBe(61)
    // ...and never shrinks it below the race's own count
    expect(transform([baseRow({ end_lap: 14 })], 57).totalLaps).toBe(57)
  })

  it('coerces unknown verdict strings to null', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deliberately invalid verdict to exercise null-coercion
    const rows = [baseRow({ verdict: 'something_else' as any })]
    const result = transform(rows, 57)
    expect(result.stints[0].verdict).toBeNull()
  })
})

describe('optimal pit lap confidence (AP-03)', () => {
  it('passes through to the stint and the CSV (3 dp)', () => {
    const result = transform([baseRow({ optimal_pit_lap_confidence: 0.98648648, optimal_pit_lap_in_stint: 12 })], 57)
    expect(result.stints[0].optimalPitLapConfidence).toBeCloseTo(0.98648648, 8)
    const [row] = toCsvRows(result)
    expect(row.optimal_pit_lap_confidence).toBe(0.986)
  })

  it('is on every CSV row, including 0.0', () => {
    const result = transform([
      baseRow({ optimal_pit_lap_confidence: 0 }),
      baseRow({ driver_id: 'LEC', optimal_pit_lap_confidence: 0.5, optimal_pit_lap_in_stint: 9 }),
    ], 57)
    const rows = toCsvRows(result)
    expect(rows.every(r => 'optimal_pit_lap_confidence' in r)).toBe(true)
    expect(rows.map(r => r.optimal_pit_lap_confidence)).toEqual([0, 0.5])
  })

  it('renders 0.0 with no optimum as "no cost curve", not 0% confident', () => {
    expect(pitConfidenceLabel(0, null)).toBe('no cost curve')
    expect(pitConfidenceLabel(null, null)).toBe('no cost curve')
  })

  it('renders 0.0 with an optimum as a flat curve, and other values as a share', () => {
    expect(pitConfidenceLabel(0, 14)).toBe('0% (flat curve)')
    expect(pitConfidenceLabel(0.62, 14)).toBe('62% of laps >1 s worse')
  })
})

describe('AP-08 next compound', () => {
  // 2018_10 SAI: the old page order (int_pit_strategy_value rows only) read no next compound after
  // stint 2; in stint-number order he went on to HARD. 142 stops differed this way across the 2018-2025 data.
  it('passes through the next compound from the stint-number order, per driver and stint', () => {
    const rows = [
      baseRow({ driver_id: 'SAI', stint_number: 1, compound: 'MEDIUM', next_compound: 'SOFT' }),
      baseRow({ driver_id: 'SAI', stint_number: 2, compound: 'SOFT', next_compound: 'HARD', start_lap: 15, end_lap: 30 }),
      baseRow({ driver_id: 'SAI', stint_number: 3, compound: 'HARD', next_compound: null, start_lap: 31, end_lap: 52 }),
    ]
    const { nextCompound } = transform(rows, 52)
    expect(nextCompound['SAI:2']).toBe('HARD')
    expect(nextCompound['SAI:3']).toBeNull()
    expect(nextCompound['SAI:1']).toBe('SOFT')
  })
})
