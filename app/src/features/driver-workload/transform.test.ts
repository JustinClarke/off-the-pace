import { describe, it, expect } from 'vitest'
import { transform, toCsvRows } from './transform'
import type { WorkloadRow } from './queries'

const mkRow = (driver_id: string, overrides: Partial<WorkloadRow> = {}): WorkloadRow => ({
  driver_id,
  avg_stint_age_laps: 18.5,
  avg_push_residual: 0.12,
  avg_dirty_air_share: 0.08,
  cliff_flag_pct: 12.3,
  total_laps: 300,
  ...overrides,
})

describe('transform', () => {
  it('passes through rows unchanged', () => {
    const rows = [mkRow('VER'), mkRow('HAM')]
    expect(transform(rows)).toStrictEqual(rows)
  })

  it('handles empty input', () => {
    expect(transform([])).toEqual([])
  })
})

describe('toCsvRows', () => {
  it('formats numeric fields correctly', () => {
    const rows = [mkRow('VER', { avg_push_residual: 0.1234, avg_dirty_air_share: 0.0856, cliff_flag_pct: 9.7 })]
    const csv = toCsvRows(rows)
    expect(csv[0].avg_push_residual_s).toBe('0.123')
    expect(csv[0].avg_dirty_air_share_pct).toBe('8.6')
    expect(csv[0].cliff_flag_pct).toBe('9.7')
  })

  it('includes all expected keys', () => {
    const csv = toCsvRows([mkRow('HAM')])
    expect(Object.keys(csv[0])).toEqual([
      'driver_id',
      'avg_stint_age_laps',
      'avg_push_residual_s',
      'avg_dirty_air_share_pct',
      'cliff_flag_pct',
      'total_eligible_laps',
    ])
  })
})
