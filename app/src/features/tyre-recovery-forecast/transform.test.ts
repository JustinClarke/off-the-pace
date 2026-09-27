import { describe, it, expect } from 'vitest'
import { pctRange, toCsvRows } from './transform'
import type { RecoveryRow } from './queries'

const mkRow = (compound: string): RecoveryRow => ({
  compound,
  post_cliff_laps: 1000,
  recovery_rate_pct: 87.5,
  avg_recovery_prob_pct: 24.0,
  avg_surface_bulk_ratio: 0.38,
  avg_thermal_s: 0.15,
})

describe('toCsvRows', () => {
  it('returns one row per compound', () => {
    const result = toCsvRows([mkRow('SOFT'), mkRow('HARD')])
    expect(result).toHaveLength(2)
    expect(result[0].compound).toBe('SOFT')
  })

  it('preserves numeric fields', () => {
    const [row] = toCsvRows([mkRow('MEDIUM')])
    expect(row.recovery_rate_pct).toBe(87.5)
    expect(row.avg_recovery_prob_pct).toBe(24.0)
  })
})

describe('pctRange', () => {
  // F49 (WI-15b): the note once said 86–89% while the query returned 57.7–63.8%.
  it('reports the range the rows actually hold', () => {
    const rows = [
      { ...mkRow('HARD'), recovery_rate_pct: 59.1, avg_recovery_prob_pct: 26.7 },
      { ...mkRow('MEDIUM'), recovery_rate_pct: 57.7, avg_recovery_prob_pct: 28.9 },
      { ...mkRow('ULTRASOFT'), recovery_rate_pct: 63.8, avg_recovery_prob_pct: 25.4 },
    ]
    expect(pctRange(rows, 'recovery_rate_pct')).toBe('58–64%')
    expect(pctRange(rows, 'avg_recovery_prob_pct')).toBe('25–29%')
  })

  it('collapses a single value and survives no rows', () => {
    expect(pctRange([mkRow('SOFT')], 'recovery_rate_pct')).toBe('88%')
    expect(pctRange([], 'recovery_rate_pct')).toBe('–')
  })
})
