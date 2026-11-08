import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export type PaceMode = 'race' | 'qualifying'

export interface ConstructorPaceRow {
  constructor_id: string
  constructor_structural_pace_s: number
  /** Season grain: NULL below 3 races (AP-07). Race grain: per-race SE. */
  constructor_structural_pace_se_s: number | null
  /** Race grain: stored +/-1.96 CI. Season grain: NULL, computed in transform.ts with the t quantile. */
  constructor_structural_pace_ci_low_s: number | null
  constructor_structural_pace_ci_high_s: number | null
  panel_observations_n: number
  races_n?: number
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

export const queryConstructorPace = registerQuery<
  { season: number; raceId: string | null; mode: PaceMode },
  ConstructorPaceRow[]
>(
  'constructor-structural-pace.data',
  async ({ season, raceId, mode }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    const table = mode === 'qualifying'
      ? 'int_constructor_structural_pace_qualifying'
      : 'int_constructor_structural_pace'

    if (raceId) {
      return rawQuery<ConstructorPaceRow>(`
        SELECT
          constructor_id,
          constructor_structural_pace_s,
          constructor_structural_pace_se_s,
          constructor_structural_pace_ci_low_s,
          constructor_structural_pace_ci_high_s,
          panel_observations_n,
          1 AS races_n
        FROM ${table}
        WHERE race_year = ?
          AND race_id = ?
        ORDER BY constructor_structural_pace_s
      `, [season, raceId])
    }

    // Season aggregate (AP-07, supersedes AP-03): the point is the plain mean
    // of the k race estimates. The SE treats the season's races as a sample of
    // circuits and weekends and takes the larger of the race-to-race spread and
    // the per-race estimation error:
    //
    //   SE = sqrt(GREATEST(VAR_SAMP(p), mean(se^2)) / k),  NULL when k < 3
    //
    // Identity: Var(mean) = tau^2/k + sum(se^2)/k^2 with tau^2 = max(0, s^2 -
    // mean se^2), which equals max(s^2, mean se^2)/k. The CI needs a t
    // quantile (df = k-1), which DuckDB lacks, so ci_low/ci_high are NULL here
    // and transform.ts fills them from its t975() table. Keep seasonMeanSe()
    // in transform.ts in step with this SQL.
    //
    // k counts races with an estimate (pace is NULL below 10 measured laps,
    // CO-04, and its SE is NULL with it). races_n = k and Obs is summed over
    // those k races only.
    return rawQuery<ConstructorPaceRow>(`
      WITH agg AS (
        SELECT
          constructor_id,
          COUNT(constructor_structural_pace_s)                  AS k,
          AVG(constructor_structural_pace_s)                    AS pace_s,
          VAR_SAMP(constructor_structural_pace_s)               AS s2,
          SUM(constructor_structural_pace_se_s * constructor_structural_pace_se_s)
            / COUNT(constructor_structural_pace_s)              AS msq,
          SUM(panel_observations_n)
            FILTER (WHERE constructor_structural_pace_s IS NOT NULL) AS panel_observations_n
        FROM ${table}
        WHERE race_year = ?
        GROUP BY constructor_id
      )
      SELECT
        constructor_id,
        pace_s                AS constructor_structural_pace_s,
        CASE WHEN k >= 3 THEN SQRT(GREATEST(s2, msq) / k) END AS constructor_structural_pace_se_s,
        CAST(NULL AS DOUBLE)  AS constructor_structural_pace_ci_low_s,
        CAST(NULL AS DOUBLE)  AS constructor_structural_pace_ci_high_s,
        panel_observations_n,
        k                     AS races_n
      FROM agg
      WHERE k > 0
      ORDER BY pace_s
    `, [season])
  }
)
