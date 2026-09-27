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
    const qPath = await getTablePath(manifest, 'int_qualifying_decomposed')
    await registerParquet('int_qualifying_decomposed', qPath)

    return rawQuery<QualiVsRaceRow>(`
      WITH race_deltas AS (
        SELECT
          driver_id,
          race_id,
          AVG(quali_skill_session_avg_s) AS quali_skill_s,
          AVG(quali_vs_race_skill_delta_s) AS delta_s
        FROM int_qualifying_decomposed
        WHERE race_year = ?
          AND session_type = 'Q'
          AND dnq_flag IS NOT TRUE
          AND quali_traffic_flag IS NOT TRUE
        GROUP BY driver_id, race_id
      )
      SELECT
        driver_id,
        AVG(quali_skill_s) AS quali_skill_s,
        AVG(quali_skill_s - delta_s) AS race_skill_s,
        AVG(delta_s) AS delta_s,
        COUNT(*) AS n_races
      FROM race_deltas
      GROUP BY driver_id
      HAVING COUNT(*) >= 3
      ORDER BY delta_s ASC
    `, [season])
  }
)
