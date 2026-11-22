import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface TeamAverageRow {
  constructor_id: string
  drivers_n: number
  laps_n: number
  /** Mean of the team's per-race car component (s) over MEASURED laps only (constructor_pace_is_filled = FALSE). NULL when no lap is measured. */
  avg_car_component_s: number | null
  /** Laps behind the car average (measured car term). 0 = unavailable. */
  constructor_measured_laps_n: number
  /** Filled laps / training-eligible laps for the team (1 when none is measured). */
  constructor_filled_share: number
  /** Mean of the team's per-race dirty-air tax (s), over laps with pace_delta_s IS NOT NULL only (TX-03: unmeasured dirty air is a filled 0.0). NULL when no lap is measured. */
  avg_dirty_air_tax_s: number | null
  /** Laps behind the dirty-air mean (pace_delta_s IS NOT NULL). 0 = unavailable (AP-05). */
  n_dirty_air_laps: number
  /** Mean of the team's per-race driver-skill residual (s). NULL when unmeasured. */
  avg_driver_skill_residual_s: number | null
}

// Each constructor is averaged within each race first (constructor_component_s is one value per
// race and constructor), then across the season's races with equal weight per race. The car term
// uses measured laps only: filled laps carry a 0.0 that is not a reading, and races with no measured
// lap drop out of the cross-race average.
// Teammates are not paired.
export const queryTeamAverages = registerQuery<{ season: number }, TeamAverageRow[]>(
  'constructor-team-averages.season',
  async ({ season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'fct_lap_residuals', season)
    await registerParquet(`fct_lap_residuals_${season}`, path)

    return rawQuery<TeamAverageRow>(`
      WITH per_race AS (
        SELECT
          constructor_id,
          race_id,
          COUNT(*)                          AS laps_n,
          AVG(CASE WHEN NOT constructor_pace_is_filled THEN constructor_component_s END) AS car_component_s,
          COUNT(CASE WHEN NOT constructor_pace_is_filled THEN 1 END) AS measured_laps_n,
          COUNT(CASE WHEN constructor_pace_is_filled THEN 1 END)     AS filled_laps_n,
          AVG(CASE WHEN pace_delta_s IS NOT NULL THEN dirty_air_tax_s END) AS dirty_air_tax_s,
          COUNT(CASE WHEN pace_delta_s IS NOT NULL THEN dirty_air_tax_s END) AS n_dirty_air_laps,
          AVG(driver_skill_residual_s)      AS driver_skill_residual_s
        FROM fct_lap_residuals_${season}
        WHERE ml_eligible
        GROUP BY constructor_id, race_id
      ),
      drivers AS (
        SELECT constructor_id, COUNT(DISTINCT driver_id) AS drivers_n
        FROM fct_lap_residuals_${season}
        WHERE ml_eligible
        GROUP BY constructor_id
      )
      SELECT
        r.constructor_id,
        MAX(d.drivers_n)                          AS drivers_n,
        SUM(r.laps_n)                             AS laps_n,
        CASE WHEN SUM(r.measured_laps_n) > 0
             THEN ROUND(AVG(r.car_component_s), 3) END AS avg_car_component_s,
        SUM(r.measured_laps_n)                    AS constructor_measured_laps_n,
        SUM(r.filled_laps_n) * 1.0 / SUM(r.laps_n) AS constructor_filled_share,
        CASE WHEN SUM(r.n_dirty_air_laps) > 0
             THEN ROUND(AVG(r.dirty_air_tax_s), 3) END AS avg_dirty_air_tax_s,
        SUM(r.n_dirty_air_laps)                   AS n_dirty_air_laps,
        ROUND(AVG(r.driver_skill_residual_s), 3)  AS avg_driver_skill_residual_s
      FROM per_race r
      JOIN drivers d USING (constructor_id)
      GROUP BY r.constructor_id
      ORDER BY avg_car_component_s NULLS LAST
    `, [])
  }
)
