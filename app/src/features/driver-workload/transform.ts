import type { WorkloadRow } from './queries'

export function transform(rows: WorkloadRow[]): WorkloadRow[] {
  return rows
}

export function toCsvRows(rows: WorkloadRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    driver_id: r.driver_id,
    avg_stint_age_laps: r.avg_stint_age_laps,
    avg_push_residual_s: r.avg_push_residual.toFixed(3),
    avg_dirty_air_share_pct: (r.avg_dirty_air_share * 100).toFixed(1),
    cliff_flag_pct: r.cliff_flag_pct.toFixed(1),
    total_eligible_laps: r.total_laps,
  }))
}
