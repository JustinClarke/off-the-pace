import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface WetRaceRow {
  driver_id: string
  wet_races: number
  dry_races: number
  wet_skill_s: number
  dry_skill_s: number
  wet_advantage_s: number
}

export const queryWetRaceSpecialist = registerQuery<void, WetRaceRow[]>(
  'wet-race.career',
  async () => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'fct_driver_skill_features')
    await registerParquet('fct_driver_skill_features', path)

    return rawQuery<WetRaceRow>(`
      SELECT
        driver_id,
        SUM(CASE WHEN race_wet_flag THEN 1 ELSE 0 END)               AS wet_races,
        SUM(CASE WHEN NOT race_wet_flag THEN 1 ELSE 0 END)           AS dry_races,
        AVG(CASE WHEN race_wet_flag THEN driver_skill_proxy_mean_s END)      AS wet_skill_s,
        AVG(CASE WHEN NOT race_wet_flag THEN driver_skill_proxy_mean_s END)  AS dry_skill_s,
        AVG(CASE WHEN race_wet_flag THEN driver_skill_proxy_mean_s END)
          - AVG(CASE WHEN NOT race_wet_flag THEN driver_skill_proxy_mean_s END)  AS wet_advantage_s
      FROM fct_driver_skill_features
      WHERE driver_skill_proxy_mean_s IS NOT NULL
        AND clean_lap_count >= 5
      GROUP BY driver_id
      HAVING wet_races >= 4 AND dry_races >= 5
      ORDER BY wet_advantage_s DESC
    `, [])
  }
)
