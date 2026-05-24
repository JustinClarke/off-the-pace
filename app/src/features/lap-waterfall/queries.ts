import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface LapResidualRow {
  driver_id: string
  /** race_id when a race is selected; 'season' when aggregated across the full season */
  race_id: string
  race_year: number
  fuel_component_s: number
  compound_component_s: number
  rubber_component_s: number
  ambient_component_s: number
  constructor_component_s: number
  dirty_air_tax_s: number
  driver_skill_residual_s: number
  track_unexplained_s: number
  total_explained_s: number
  /** Reconstructed observed delta: total_explained + skill + track (pace_delta_s is not exported) */
  pace_delta_s: number
  n_laps: number
}

interface Params {
  season: number
  raceId: string | null
}

export const queryLapWaterfall = registerQuery<Params, LapResidualRow[]>(
  'lap-waterfall.race',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'fct_lap_residuals', season)
    await registerParquet(`fct_lap_residuals_${season}`, path)

    if (raceId) {
      // Single race: one row per driver for that race
      return rawQuery<LapResidualRow>(`
        SELECT
          driver_id,
          race_id,
          race_year,
          COALESCE(AVG(fuel_component_s), 0)          AS fuel_component_s,
          COALESCE(AVG(compound_component_s), 0)      AS compound_component_s,
          COALESCE(AVG(rubber_component_s), 0)        AS rubber_component_s,
          COALESCE(AVG(ambient_component_s), 0)       AS ambient_component_s,
          COALESCE(AVG(constructor_component_s), 0)   AS constructor_component_s,
          COALESCE(AVG(dirty_air_tax_s), 0)           AS dirty_air_tax_s,
          COALESCE(AVG(driver_skill_residual_s), 0)   AS driver_skill_residual_s,
          COALESCE(AVG(track_unexplained_s), 0)       AS track_unexplained_s,
          COALESCE(AVG(total_explained_s), 0)         AS total_explained_s,
          COALESCE(AVG(total_explained_s), 0)
            + COALESCE(AVG(driver_skill_residual_s), 0)
            + COALESCE(AVG(track_unexplained_s), 0)  AS pace_delta_s,
          COUNT(*)                                    AS n_laps
        FROM fct_lap_residuals_${season}
        WHERE race_year = ?
          AND race_id = ?
          AND NOT is_safety_car_lap
          AND NOT is_major_outlier_lap
          AND fuel_component_s IS NOT NULL
        GROUP BY driver_id, race_id, race_year
        ORDER BY driver_id
      `, [season, raceId])
    }

    // No race selected: season average per driver (one row per driver)
    return rawQuery<LapResidualRow>(`
      SELECT
        driver_id,
        'season'                                      AS race_id,
        race_year,
        COALESCE(AVG(fuel_component_s), 0)          AS fuel_component_s,
        COALESCE(AVG(compound_component_s), 0)      AS compound_component_s,
        COALESCE(AVG(rubber_component_s), 0)        AS rubber_component_s,
        COALESCE(AVG(ambient_component_s), 0)       AS ambient_component_s,
        COALESCE(AVG(constructor_component_s), 0)   AS constructor_component_s,
        COALESCE(AVG(dirty_air_tax_s), 0)           AS dirty_air_tax_s,
        COALESCE(AVG(driver_skill_residual_s), 0)   AS driver_skill_residual_s,
        COALESCE(AVG(track_unexplained_s), 0)       AS track_unexplained_s,
        COALESCE(AVG(total_explained_s), 0)         AS total_explained_s,
        COALESCE(AVG(total_explained_s), 0)
          + COALESCE(AVG(driver_skill_residual_s), 0)
          + COALESCE(AVG(track_unexplained_s), 0)  AS pace_delta_s,
        COUNT(*)                                    AS n_laps
      FROM fct_lap_residuals_${season}
      WHERE race_year = ?
        AND NOT is_safety_car_lap
        AND NOT is_major_outlier_lap
        AND fuel_component_s IS NOT NULL
      GROUP BY driver_id, race_year
      ORDER BY driver_id
    `, [season])
  }
)
