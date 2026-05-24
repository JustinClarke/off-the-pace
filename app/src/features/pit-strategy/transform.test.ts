import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { PitGanttRow } from './queries'

const baseRow = (overrides: Partial<PitGanttRow> = {}): PitGanttRow => ({
  driver_id: 'VER',
  constructor_id: 'Red Bull',
  stint_number: 1,
  compound: 'SOFT',
  start_lap: 1,
  end_lap: 14,
  stint_length_laps: 14,
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

  it('coerces unknown verdict strings to null', () => {
    const rows = [baseRow({ verdict: 'something_else' as any })]
    const result = transform(rows, 57)
    expect(result.stints[0].verdict).toBeNull()
  })
})
