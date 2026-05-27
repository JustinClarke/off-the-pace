import type { FieldPaceRow } from './queries'
import type { CIPoint } from '../../ui/charts'

export interface TransformResult {
  points: CIPoint[]
  /** True if any laps had low_sample_flag */
  hasLowSample: boolean
  minPace: number
  maxPace: number
}

export function transform(rows: FieldPaceRow[]): TransformResult {
  if (!rows.length) return { points: [], hasLowSample: false, minPace: 0, maxPace: 0 }

  // Use the smoothed line as primary (y), raw trimmed mean as the secondary (y2)
  // lo/hi = the range between smoothed and raw, giving a "spread" ribbon
  const points: CIPoint[] = rows.map(r => {
    const lo = Math.min(r.field_pace_smoothed_s, r.field_pace_trimmed_mean_s)
    const hi = Math.max(r.field_pace_smoothed_s, r.field_pace_trimmed_mean_s)
    return {
      x: r.lap_number,
      y: r.field_pace_smoothed_s,
      lo,
      hi,
      y2: r.field_pace_trimmed_mean_s,
    }
  })

  const allPaces = rows.flatMap(r => [r.field_pace_smoothed_s, r.field_pace_trimmed_mean_s])
  return {
    points,
    hasLowSample: rows.some(r => r.low_sample_flag),
    minPace: Math.min(...allPaces),
    maxPace: Math.max(...allPaces),
  }
}

export function toCsvRows(rows: FieldPaceRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    lap_number: r.lap_number,
    field_pace_smoothed_s: r.field_pace_smoothed_s.toFixed(4),
    field_pace_trimmed_mean_s: r.field_pace_trimmed_mean_s.toFixed(4),
    eligible_lap_count: r.eligible_lap_count,
    low_sample_flag: r.low_sample_flag,
  }))
}
