import type { DriverConsistencyRow } from './queries'

export interface ConsistencyPoint {
  driver_id: string
  mean_s: number
  stddev_s: number
  clean_lap_count: number
  constructor_id: string
  /** Quadrant label derived from mean/stddev relative to season medians */
  quadrant: 'fast-consistent' | 'fast-erratic' | 'slow-consistent' | 'slow-erratic'
}

export interface TransformResult {
  points: ConsistencyPoint[]
  medianMean: number
  medianStddev: number
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid]
}

export function transform(rows: DriverConsistencyRow[]): TransformResult {
  if (!rows.length) return { points: [], medianMean: 0, medianStddev: 0 }

  const medianMean = median(rows.map(r => r.driver_residual_mean_s))
  const medianStddev = median(rows.map(r => r.driver_residual_stddev_s))

  const points: ConsistencyPoint[] = rows.map(r => {
    const fast = r.driver_residual_mean_s <= medianMean
    const consistent = r.driver_residual_stddev_s <= medianStddev
    const quadrant =
      fast && consistent ? 'fast-consistent' :
      fast ? 'fast-erratic' :
      consistent ? 'slow-consistent' : 'slow-erratic'

    return {
      driver_id: r.driver_id,
      mean_s: r.driver_residual_mean_s,
      stddev_s: r.driver_residual_stddev_s,
      clean_lap_count: r.clean_lap_count,
      constructor_id: r.constructor_id,
      quadrant,
    }
  })

  return { points, medianMean, medianStddev }
}

export function toCsvRows(result: TransformResult): Record<string, unknown>[] {
  return result.points.map(p => ({
    driver_id: p.driver_id,
    mean_residual_s: p.mean_s.toFixed(4),
    stddev_residual_s: p.stddev_s.toFixed(4),
    clean_lap_count: p.clean_lap_count,
    constructor_id: p.constructor_id,
    quadrant: p.quadrant,
  }))
}
