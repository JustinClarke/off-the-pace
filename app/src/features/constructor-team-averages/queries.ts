import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface TeamAverageRow {
  constructor_id: string
  drivers_n: number
  laps_n: number
  /** Mean of the team's per-race car component (s). NULL when no race has a reading. */
  avg_car_component_s: number | null
  /** Mean of the team's per-race dirty-air tax (s). NULL when unmeasured. */
  avg_dirty_air_tax_s: number | null
  /** Mean of the team's per-race driver-skill residual (s). NULL when unmeasured. */
  avg_driver_skill_residual_s: number | null
}

// Each constructor is averaged within each race first (constructor_component_s is one value per
// race and constructor), then across the season's races with equal weight per race.
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
          AVG(constructor_component_s)      AS car_component_s,
          AVG(dirty_air_tax_s)              AS dirty_air_tax_s,
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
        ROUND(AVG(r.car_component_s), 3)          AS avg_car_component_s,
        ROUND(AVG(r.dirty_air_tax_s), 3)          AS avg_dirty_air_tax_s,
        ROUND(AVG(r.driver_skill_residual_s), 3)  AS avg_driver_skill_residual_s
      FROM per_race r
      JOIN drivers d USING (constructor_id)
      GROUP BY r.constructor_id
      ORDER BY avg_car_component_s NULLS LAST
    `, [])
  }
)
