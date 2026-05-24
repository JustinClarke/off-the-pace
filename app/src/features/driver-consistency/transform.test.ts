import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { DriverConsistencyRow } from './queries'

const makeRow = (overrides: Partial<DriverConsistencyRow>): DriverConsistencyRow => ({
  driver_id: 'VER',
  race_year: 2024,
  driver_residual_mean_s: 0,
  driver_residual_stddev_s: 0.5,
  clean_lap_count: 50,
  constructor_id: 'red_bull',
  ...overrides,
})

describe('transform', () => {
  it('returns empty result for empty input', () => {
    const result = transform([])
    expect(result.points).toHaveLength(0)
  })

  it('assigns fast-consistent quadrant to driver below both medians', () => {
    const rows: DriverConsistencyRow[] = [
      makeRow({ driver_id: 'VER', driver_residual_mean_s: -0.5, driver_residual_stddev_s: 0.3 }),
      makeRow({ driver_id: 'HAM', driver_residual_mean_s:  0.5, driver_residual_stddev_s: 0.7 }),
    ]
    const result = transform(rows)
    const ver = result.points.find(p => p.driver_id === 'VER')!
    expect(ver.quadrant).toBe('fast-consistent')
  })

  it('assigns slow-erratic quadrant to driver above both medians', () => {
    const rows: DriverConsistencyRow[] = [
      makeRow({ driver_id: 'VER', driver_residual_mean_s: -0.5, driver_residual_stddev_s: 0.3 }),
      makeRow({ driver_id: 'SLO', driver_residual_mean_s:  0.8, driver_residual_stddev_s: 0.9 }),
    ]
    const result = transform(rows)
    const slo = result.points.find(p => p.driver_id === 'SLO')!
    expect(slo.quadrant).toBe('slow-erratic')
  })

  it('preserves all rows', () => {
    const rows = [makeRow({ driver_id: 'A' }), makeRow({ driver_id: 'B' }), makeRow({ driver_id: 'C' })]
    expect(transform(rows).points).toHaveLength(3)
  })

  it('computes medians correctly for even-length arrays', () => {
    const rows: DriverConsistencyRow[] = [
      makeRow({ driver_residual_mean_s: -1, driver_residual_stddev_s: 0.2 }),
      makeRow({ driver_residual_mean_s: -0.5, driver_residual_stddev_s: 0.4 }),
      makeRow({ driver_residual_mean_s:  0.5, driver_residual_stddev_s: 0.6 }),
      makeRow({ driver_residual_mean_s:  1, driver_residual_stddev_s: 0.8 }),
    ]
    const result = transform(rows)
    expect(result.medianMean).toBeCloseTo(0, 5)
    expect(result.medianStddev).toBeCloseTo(0.5, 5)
  })
})
