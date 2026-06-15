import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface PartyModeRow {
  constructor_id: string
  race_pace_s: number
  quali_pace_s: number
  delta_s: number
  race_obs: number
  quali_obs: number
}

async function registerTables(manifest: Awaited<ReturnType<typeof loadManifest>>) {
  const [racePath, qualiPath] = await Promise.all([
    getTablePath(manifest, 'int_constructor_structural_pace'),
    getTablePath(manifest, 'int_constructor_structural_pace_qualifying'),
  ])
  await Promise.all([
    registerParquet('int_constructor_structural_pace', racePath),
    registerParquet('int_constructor_structural_pace_qualifying', qualiPath),
  ])
}

export const queryPartyMode = registerQuery<
  { season: number; raceId: string | null },
  PartyModeRow[]
>(
  'party-mode.data',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    if (raceId) {
      return rawQuery<PartyModeRow>(`
        SELECT
          r.constructor_id,
          r.constructor_structural_pace_s   AS race_pace_s,
          q.constructor_structural_pace_s   AS quali_pace_s,
          q.constructor_structural_pace_s - r.constructor_structural_pace_s AS delta_s,
          r.panel_observations_n            AS race_obs,
          q.panel_observations_n            AS quali_obs
        FROM int_constructor_structural_pace r
        JOIN int_constructor_structural_pace_qualifying q
          ON r.constructor_id = q.constructor_id
         AND r.race_id = q.race_id
        WHERE r.race_year = ?
          AND r.race_id = ?
        ORDER BY delta_s
      `, [season, raceId])
    }

    return rawQuery<PartyModeRow>(`
      SELECT
        r.constructor_id,
        AVG(r.constructor_structural_pace_s)   AS race_pace_s,
        AVG(q.constructor_structural_pace_s)   AS quali_pace_s,
        AVG(q.constructor_structural_pace_s) - AVG(r.constructor_structural_pace_s) AS delta_s,
        SUM(r.panel_observations_n)            AS race_obs,
        SUM(q.panel_observations_n)            AS quali_obs
      FROM int_constructor_structural_pace r
      JOIN int_constructor_structural_pace_qualifying q
        ON r.constructor_id = q.constructor_id
       AND r.race_id = q.race_id
      WHERE r.race_year = ?
      GROUP BY r.constructor_id
      ORDER BY delta_s
    `, [season])
  }
)
