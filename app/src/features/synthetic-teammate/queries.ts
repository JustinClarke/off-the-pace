import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface SyntheticTmRow {
  driver_id: string
  teammate_driver_id: string
  constructor_id: string
  n_races: number
  avg_skill_proxy_s: number
  avg_quality_weight: number
}

interface Params {
  season: number
}

export const querySyntheticTeammate = registerQuery<Params, SyntheticTmRow[]>(
  'synthetic-teammate.season',
  async ({ season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_synthetic_teammate')
    await registerParquet('int_synthetic_teammate', path)

    return rawQuery<SyntheticTmRow>(`
      SELECT
        ego_driver_id                                    AS driver_id,
        ANY_VALUE(teammate_driver_id)                   AS teammate_driver_id,
        ANY_VALUE(constructor_id)                       AS constructor_id,
        COUNT(DISTINCT race_id)                         AS n_races,
        AVG(driver_skill_proxy_s)                       AS avg_skill_proxy_s,
        AVG(pair_quality_weight)                        AS avg_quality_weight
      FROM int_synthetic_teammate
      WHERE race_year = ?
        AND teammate_available_flag = true
        AND strategic_divergence_flag = false
      GROUP BY ego_driver_id
      HAVING COUNT(DISTINCT race_id) >= 3
      ORDER BY avg_skill_proxy_s ASC
    `, [season])
  }
)
