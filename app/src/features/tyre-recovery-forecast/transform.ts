import type { RecoveryRow } from './queries'

/**
 * "57–64%": the whole-percent range of one column across the compound rows. The page's
 * interpretation note is built from this rather than typed in, because the typed-in
 * version said 86–89% while its own query returned 57.7–63.8% (F49, WI-15b).
 */
export function pctRange(rows: RecoveryRow[], key: 'recovery_rate_pct' | 'avg_recovery_prob_pct'): string {
  const xs = rows.map(r => r[key]).filter(x => Number.isFinite(x))
  if (xs.length === 0) return '–'
  const lo = Math.round(Math.min(...xs))
  const hi = Math.round(Math.max(...xs))
  return lo === hi ? `${lo}%` : `${lo}–${hi}%`
}

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
