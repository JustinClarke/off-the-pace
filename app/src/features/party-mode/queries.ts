import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface PartyModeRow {
  constructor_id: string
  race_pace_s: number
  quali_pace_s: number
  delta_s: number
  /** Race grain: SE of each side (delta SE = sqrt(se_q² + se_r²)). Season grain: NULL. */
  race_se_s: number | null
  quali_se_s: number | null
  /** Season grain only (AP-07): SE of the mean per-race delta, NULL below 3 races */
  delta_se_s?: number | null
  /** Season grain only: k, the races with both a quali and a race estimate */
  races_n?: number
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
          r.constructor_structural_pace_se_s AS race_se_s,
          q.constructor_structural_pace_se_s AS quali_se_s,
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

    // Season grain (AP-07): over races where BOTH a race and a quali estimate
    // exist, the delta is AVG(q - r) (the old AVG(q) - AVG(r) averaged
    // different races once race pace was NULL). Its SE follows the Structural
    // Pace season rule applied to the per-race deltas d = q - r with
    // se_d² = se_q² + se_r²:
    //
    //   SE = sqrt(GREATEST(VAR_SAMP(d), mean(se_d²)) / k),  NULL when k < 3
    //
    // transform.ts turns it into a CI with the t quantile for k - 1 df.
    return rawQuery<PartyModeRow>(`
      SELECT
        r.constructor_id,
        AVG(r.constructor_structural_pace_s)   AS race_pace_s,
        AVG(q.constructor_structural_pace_s)   AS quali_pace_s,
        AVG(q.constructor_structural_pace_s - r.constructor_structural_pace_s) AS delta_s,
        CAST(NULL AS DOUBLE)                   AS race_se_s,
        CAST(NULL AS DOUBLE)                   AS quali_se_s,
        CASE WHEN COUNT(*) >= 3 THEN SQRT(GREATEST(
            VAR_SAMP(q.constructor_structural_pace_s - r.constructor_structural_pace_s),
            SUM(q.constructor_structural_pace_se_s * q.constructor_structural_pace_se_s
              + r.constructor_structural_pace_se_s * r.constructor_structural_pace_se_s) / COUNT(*)
          ) / COUNT(*)) END                    AS delta_se_s,
        COUNT(*)                               AS races_n,
        SUM(r.panel_observations_n)            AS race_obs,
        SUM(q.panel_observations_n)            AS quali_obs
      FROM int_constructor_structural_pace r
      JOIN int_constructor_structural_pace_qualifying q
        ON r.constructor_id = q.constructor_id
       AND r.race_id = q.race_id
      WHERE r.race_year = ?
        AND r.constructor_structural_pace_s IS NOT NULL
        AND q.constructor_structural_pace_s IS NOT NULL
      GROUP BY r.constructor_id
      ORDER BY delta_s
    `, [season])
  }
)
