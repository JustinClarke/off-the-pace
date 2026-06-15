import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { QualityAuditRow } from './queries'

const mkRow = (race_id: string, total = 100, usable = 75): QualityAuditRow => ({
  race_id,
  total_laps: total,
  usable_laps: usable,
  pct_usable: (usable / total) * 100,
  neutralised_laps: 2,
  rain_laps: 0,
  out_in_laps: 20,
  major_outlier_laps: 1,
  anomaly_laps: 5,
})

describe('transform', () => {
  it('returns empty for no rows', () => {
    expect(transform([])).toEqual([])
  })

  it('extracts round number from race_id', () => {
    const [r] = transform([mkRow('2024_3')])
    expect(r.round).toBe(3)
  })

  it('handles two-digit round numbers', () => {
    const [r] = transform([mkRow('2024_10')])
    expect(r.round).toBe(10)
  })

  it('sorts by round ascending', () => {
    const rows = [mkRow('2024_3'), mkRow('2024_1'), mkRow('2024_10')]
    const result = transform(rows)
    expect(result.map(r => r.round)).toEqual([1, 3, 10])
  })

  it('preserves all original fields', () => {
    const row = mkRow('2024_5')
    const [r] = transform([row])
    expect(r.total_laps).toBe(row.total_laps)
    expect(r.pct_usable).toBe(row.pct_usable)
  })
})
