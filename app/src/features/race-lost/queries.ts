import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface RaceLostRow {
  total_fuel_s: number
  total_compound_s: number
  total_rubber_s: number
  total_ambient_s: number
  total_constructor_s: number
  total_dirty_air_s: number
  total_skill_s: number
  total_track_s: number
  total_explained_s: number
  total_pace_delta_s: number
  n_laps: number
}

interface Params {
  season: number
  raceId: string
  driverId: string
}

async function registerLapResiduals(season: number): Promise<string> {
  const manifest = await loadManifest()
  const path = getTablePath(manifest, 'fct_lap_residuals', season)
  const alias = `fct_lap_residuals_${season}`
  await registerParquet(alias, path)
  return alias
}

export const queryRaceLost = registerQuery<Params, RaceLostRow[]>(
  'race-lost.driver',
  async ({ season, raceId, driverId }) => {
    const alias = await registerLapResiduals(season)

    return rawQuery<RaceLostRow>(`
      SELECT
        COALESCE(SUM(fuel_component_s), 0)          AS total_fuel_s,
        COALESCE(SUM(compound_component_s), 0)      AS total_compound_s,
        COALESCE(SUM(rubber_component_s), 0)        AS total_rubber_s,
        COALESCE(SUM(ambient_component_s), 0)       AS total_ambient_s,
        COALESCE(SUM(constructor_component_s), 0)   AS total_constructor_s,
        COALESCE(SUM(dirty_air_tax_s), 0)           AS total_dirty_air_s,
        COALESCE(SUM(driver_skill_residual_s), 0)   AS total_skill_s,
        COALESCE(SUM(track_unexplained_s), 0)       AS total_track_s,
        COALESCE(SUM(total_explained_s), 0)         AS total_explained_s,
        COALESCE(SUM(total_explained_s), 0)
          + COALESCE(SUM(driver_skill_residual_s), 0)
          + COALESCE(SUM(track_unexplained_s), 0)   AS total_pace_delta_s,
        COUNT(*)                                    AS n_laps
      FROM ${alias}
      WHERE race_year = ?
        AND race_id   = ?
        AND driver_id = ?
        AND NOT is_safety_car_lap
        AND NOT is_major_outlier_lap
        AND fuel_component_s IS NOT NULL
    `, [season, raceId, driverId])
  }
)

export const queryRaceLostDrivers = registerQuery<
  { season: number; raceId: string },
  { driver_id: string }[]
>(
  'race-lost.drivers',
  async ({ season, raceId }) => {
    const alias = await registerLapResiduals(season)

    return rawQuery<{ driver_id: string }>(`
      SELECT DISTINCT driver_id
      FROM ${alias}
      WHERE race_year = ?
        AND race_id   = ?
        AND fuel_component_s IS NOT NULL
      ORDER BY driver_id
    `, [season, raceId])
  }
)
