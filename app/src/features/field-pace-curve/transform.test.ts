import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { FieldPaceRow } from './queries'

const ROWS: FieldPaceRow[] = [
  { lap_number: 1, field_pace_smoothed_s: 94.5, field_pace_trimmed_mean_s: 94.2, eligible_lap_count: 5, low_sample_flag: false },
  { lap_number: 2, field_pace_smoothed_s: 95.0, field_pace_trimmed_mean_s: 95.4, eligible_lap_count: 3, low_sample_flag: true },
]

describe('transform', () => {
  it('returns empty for empty input', () => {
    expect(transform([]).points).toHaveLength(0)
  })

  it('detects low sample laps', () => {
    expect(transform(ROWS).hasLowSample).toBe(true)
  })

  it('sets lo/hi from min/max of smoothed and trimmed', () => {
    const { points } = transform(ROWS)
    expect(points[0].lo).toBeCloseTo(94.2)
    expect(points[0].hi).toBeCloseTo(94.5)
    expect(points[1].lo).toBeCloseTo(95.0)
    expect(points[1].hi).toBeCloseTo(95.4)
  })
})
