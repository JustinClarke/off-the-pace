import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface WorkloadRow {
  driver_id: string
  avg_stint_age_laps: number
  avg_push_residual: number
  avg_dirty_air_share: number
  cliff_flag_pct: number
  total_laps: number
}

export const queryDriverWorkload = registerQuery<{ season: number }, WorkloadRow[]>(
  'driver-workload.season',
  async ({ season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'fct_cliff_prediction_features', season)
    await registerParquet(`fct_cliff_prediction_features_${season}`, path)

    return rawQuery<WorkloadRow>(`
      SELECT
        driver_id,
        ROUND(AVG(age_in_stint), 1)                                          AS avg_stint_age_laps,
        ROUND(AVG(COALESCE(push_residual, 0.0)), 3)                          AS avg_push_residual,
        ROUND(AVG(dirty_air_share_lap), 3)                                   AS avg_dirty_air_share,
        ROUND(
          100.0 * COUNT(*) FILTER (WHERE cliff_candidate_flag)
          / NULLIF(COUNT(*), 0),
          1
        )                                                                    AS cliff_flag_pct,
        COUNT(*)                                                             AS total_laps
      FROM fct_cliff_prediction_features_${season}
      WHERE is_training_eligible
      GROUP BY driver_id
      HAVING COUNT(*) >= 50
      ORDER BY avg_push_residual DESC
    `, [])
  }
)
