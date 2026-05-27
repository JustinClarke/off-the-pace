import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface QualityAuditRow {
  race_id: string
  total_laps: number
  usable_laps: number
  pct_usable: number
  neutralised_laps: number
  rain_laps: number
  out_in_laps: number
  major_outlier_laps: number
  anomaly_laps: number
}

interface Params {
  season: number
}

export const queryQualityAudit = registerQuery<Params, QualityAuditRow[]>(
  'data-quality-audit.season',
  async ({ season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_lap_anomaly_flags', season)
    await registerParquet(`int_lap_anomaly_flags_${season}`, path)

    return rawQuery<QualityAuditRow>(`
      SELECT
        race_id,
        COUNT(*)                                                              AS total_laps,
        SUM(CASE WHEN usable_for_modelling THEN 1 ELSE 0 END)                AS usable_laps,
        ROUND(100.0 * SUM(CASE WHEN usable_for_modelling THEN 1 ELSE 0 END)
              / NULLIF(COUNT(*), 0), 1)                                       AS pct_usable,
        SUM(CASE WHEN correction_class = 'neutralisation' THEN 1 ELSE 0 END) AS neutralised_laps,
        SUM(CASE WHEN is_rain_lap THEN 1 ELSE 0 END)                          AS rain_laps,
        SUM(CASE WHEN is_out_lap OR is_in_lap THEN 1 ELSE 0 END)             AS out_in_laps,
        SUM(CASE WHEN is_major_outlier_lap THEN 1 ELSE 0 END)                AS major_outlier_laps,
        SUM(CASE WHEN anomaly_class != 'normal' THEN 1 ELSE 0 END)           AS anomaly_laps
      FROM int_lap_anomaly_flags_${season}
      WHERE race_year = ?
      GROUP BY race_id
      ORDER BY race_id ASC
    `, [season])
  }
)
