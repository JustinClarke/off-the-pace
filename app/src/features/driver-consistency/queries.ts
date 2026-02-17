import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface DriverConsistencyRow {
  driver_id: string
  race_year: number
  driver_residual_mean_s: number
  driver_residual_stddev_s: number
  clean_lap_count: number
  constructor_id: string
}

interface Params {
  season: number
}

export const queryDriverConsistency = registerQuery<Params, DriverConsistencyRow[]>(
  'driver-consistency.season',
  async ({ season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'fct_driver_skill_features')
    await registerParquet('fct_driver_skill_features', path)

    return rawQuery<DriverConsistencyRow>(`
      SELECT
        driver_id,
        race_year,
        driver_residual_mean_s,
        driver_residual_stddev_s,
        clean_lap_count,
        constructor_id
      FROM fct_driver_skill_features
      WHERE race_year = ?
        AND driver_residual_mean_s IS NOT NULL
        AND driver_residual_stddev_s IS NOT NULL
        AND clean_lap_count >= 10
      ORDER BY driver_residual_stddev_s ASC
    `, [season])
  }
)
