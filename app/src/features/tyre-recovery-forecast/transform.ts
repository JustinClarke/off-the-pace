import type { RecoveryRow } from './queries'

export function toCsvRows(rows: RecoveryRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    compound: r.compound,
    post_cliff_laps: r.post_cliff_laps,
    recovery_rate_pct: r.recovery_rate_pct,
    avg_recovery_prob_pct: r.avg_recovery_prob_pct,
    avg_surface_bulk_ratio: r.avg_surface_bulk_ratio,
    avg_thermal_s: r.avg_thermal_s,
  }))
}
