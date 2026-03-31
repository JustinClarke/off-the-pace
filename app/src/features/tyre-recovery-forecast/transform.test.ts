import { describe, it, expect } from 'vitest'
import { toCsvRows } from './transform'
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
