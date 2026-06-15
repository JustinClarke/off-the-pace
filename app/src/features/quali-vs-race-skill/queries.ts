import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface QualiVsRaceRow {
  driver_id: string
  quali_skill_s: number
  race_skill_s: number
  delta_s: number
  n_races: number
}

interface Params {
  season: number
}

export const queryQualiVsRace = registerQuery<Params, QualiVsRaceRow[]>(
  'quali-vs-race.season',
  async ({ season }) => {
    const manifest = await loadManifest()
    const [qPath, fPath] = await Promise.all([
      getTablePath(manifest, 'int_qualifying_decomposed'),
      getTablePath(manifest, 'fct_driver_skill_features'),
    ])
    await Promise.all([
      registerParquet('int_qualifying_decomposed', qPath),
      registerParquet('fct_driver_skill_features', fPath),
    ])

    return rawQuery<QualiVsRaceRow>(`
      SELECT
        q.driver_id,
        AVG(q.quali_skill_session_avg_s)       AS quali_skill_s,
        AVG(f.driver_skill_proxy_mean_s)        AS race_skill_s,
        AVG(q.quali_skill_session_avg_s)
          - AVG(f.driver_skill_proxy_mean_s)    AS delta_s,
        COUNT(DISTINCT q.race_id)               AS n_races
      FROM int_qualifying_decomposed q
      JOIN fct_driver_skill_features f
        ON q.driver_id = f.driver_id
       AND q.race_id   = f.race_id
      WHERE q.race_year = ?
        AND q.session_type = 'Q'
        AND q.dnq_flag IS NOT TRUE
        AND q.quali_traffic_flag IS NOT TRUE
      GROUP BY q.driver_id
      HAVING COUNT(DISTINCT q.race_id) >= 3
      ORDER BY delta_s ASC
    `, [season])
  }
)
