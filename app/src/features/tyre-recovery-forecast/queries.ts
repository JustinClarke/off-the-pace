import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface RecoveryRow {
  compound: string
  post_cliff_laps: number
  recovery_rate_pct: number
  avg_recovery_prob_pct: number
  avg_surface_bulk_ratio: number
  avg_thermal_s: number
}

export const queryRecoveryForecast = registerQuery<Record<string, never>, RecoveryRow[]>(
  'tyre-recovery-forecast.all',
  async () => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_tyre_surface_vs_bulk_decoupling')
    await registerParquet('int_tyre_surface_vs_bulk_decoupling', path)

    return rawQuery<RecoveryRow>(`
      SELECT
        compound,
        COUNT(*)                                                                AS post_cliff_laps,
        ROUND(100.0 * AVG(CASE WHEN recovery_flag THEN 1.0 ELSE 0.0 END), 1)  AS recovery_rate_pct,
        ROUND(AVG(recovery_probability) * 100, 1)                              AS avg_recovery_prob_pct,
        ROUND(AVG(surface_bulk_ratio), 3)                                      AS avg_surface_bulk_ratio,
        ROUND(AVG(thermal_attribution_s), 3)                                   AS avg_thermal_s
      FROM int_tyre_surface_vs_bulk_decoupling
      WHERE laps_past_cliff > 0
        AND compound NOT IN ('INTERMEDIATE', 'WET')
      GROUP BY compound
      ORDER BY compound
    `, [])
  }
)
