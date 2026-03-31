import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface HiddenPerformanceRow {
  ego_driver_id: string
  race_id: string
  circuit_name: string | null
  race_year: number
  host_constructor_id: string
  ego_constructor_id: string | null
  predicted_finish_position: number
  actual_finish_position: number | null
  delta_vs_actual_position: number | null
  finish_pos_se: number
  avg_recombination_confidence: number
  laps_counted: number
  adjusted_delta: number | null
  adjusted_delta_z: number | null
  affinity_shrunk_s: number | null
  affinity_confidence: number | null
  driver_season_rating: number | null
}

export interface SeasonRow {
  ego_driver_id: string
  ego_constructor_id: string | null
  mean_raw_delta: number
  mean_adjusted_delta: number
  sd_adjusted_delta: number | null
  n_races: number
  total_laps: number
  mean_confidence: number
  driver_season_rating: number | null
}

async function registerTables(manifest: Awaited<ReturnType<typeof loadManifest>>) {
  await Promise.all([
    registerParquet('fct_ghost_race_finish', getTablePath(manifest, 'fct_ghost_race_finish')),
    registerParquet('race_to_track', getTablePath(manifest, 'race_to_track')),
    registerParquet('dim_circuits', getTablePath(manifest, 'dim_circuits')),
    registerParquet('int_driver_circuit_era_affinity', getTablePath(manifest, 'int_driver_circuit_era_affinity')),
    registerParquet('int_era_normalized_driver_rating', getTablePath(manifest, 'int_era_normalized_driver_rating')),
  ])
}

// CTE fragments shared between per-race and season queries.
// Params: season (×2), hostConstructorId
const WITH_BASE = `
  self_scenarios AS (
    SELECT DISTINCT ego_driver_id, race_id, host_constructor_id AS ego_constructor_id
    FROM fct_ghost_race_finish
    WHERE is_self_scenario = TRUE AND race_year = ?
  ),
  race_circuits AS (
    SELECT
      substr(CAST(rt.race_id AS VARCHAR), 1, 4) || '_' || substr(CAST(rt.race_id AS VARCHAR), 5) AS race_id,
      dc.circuit_id,
      dc.circuit_name
    FROM race_to_track rt
    LEFT JOIN dim_circuits dc ON rt.track_id = dc.circuit_key
  ),
  base AS (
    SELECT
      f.ego_driver_id,
      f.race_id,
      f.race_year,
      f.host_constructor_id,
      ss.ego_constructor_id,
      f.predicted_finish_position,
      f.actual_finish_position,
      f.delta_vs_actual_position,
      f.finish_pos_se,
      f.avg_recombination_confidence,
      f.laps_counted
    FROM fct_ghost_race_finish f
    LEFT JOIN self_scenarios ss ON f.ego_driver_id = ss.ego_driver_id AND f.race_id = ss.race_id
    WHERE f.race_year = ?
      AND f.host_constructor_id = ?
      AND f.avg_recombination_confidence >= 0.3
      AND f.is_short_run = FALSE
      AND f.delta_vs_actual_position IS NOT NULL
      AND f.actual_finish_position IS NOT NULL
  ),
  constructor_avgs AS (
    SELECT ego_constructor_id, AVG(delta_vs_actual_position) AS constructor_avg_delta
    FROM base
    GROUP BY ego_constructor_id
  ),
  adjusted AS (
    SELECT
      b.*,
      b.delta_vs_actual_position - ca.constructor_avg_delta AS adjusted_delta,
      (b.delta_vs_actual_position - ca.constructor_avg_delta) / NULLIF(b.finish_pos_se, 0) AS adjusted_delta_z
    FROM base b
    LEFT JOIN constructor_avgs ca USING (ego_constructor_id)
  )
`

export const queryHiddenPerformance = registerQuery<
  { season: number; hostConstructorId: string },
  HiddenPerformanceRow[]
>(
  'hidden-performance.data',
  async ({ season, hostConstructorId }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    const eraKey = season >= 2022 ? 'post2022' : 'pre2022'

    return rawQuery<HiddenPerformanceRow>(`
      WITH ${WITH_BASE}
      SELECT
        a.ego_driver_id,
        a.race_id,
        rc.circuit_name,
        a.race_year,
        a.host_constructor_id,
        a.ego_constructor_id,
        a.predicted_finish_position,
        a.actual_finish_position,
        a.delta_vs_actual_position,
        a.finish_pos_se,
        a.avg_recombination_confidence,
        a.laps_counted,
        a.adjusted_delta,
        a.adjusted_delta_z,
        aff.shrunk_affinity_s  AS affinity_shrunk_s,
        aff.affinity_confidence,
        dr.era_adjusted_rating AS driver_season_rating
      FROM adjusted a
      LEFT JOIN race_circuits rc ON a.race_id = rc.race_id
      LEFT JOIN int_driver_circuit_era_affinity aff
        ON aff.driver_id  = a.ego_driver_id
        AND aff.circuit_id = rc.circuit_id
        AND aff.era_key   = '${eraKey}'
      LEFT JOIN int_era_normalized_driver_rating dr
        ON dr.driver_id = a.ego_driver_id
        AND dr.season   = a.race_year
      ORDER BY a.adjusted_delta ASC
    `, [season, season, hostConstructorId])
  }
)

export const queryHiddenSeason = registerQuery<
  { season: number; hostConstructorId: string; minRaces: number },
  SeasonRow[]
>(
  'hidden-performance.season',
  async ({ season, hostConstructorId, minRaces }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    return rawQuery<SeasonRow>(`
      WITH ${WITH_BASE},
      season_agg AS (
        SELECT
          ego_driver_id,
          ego_constructor_id,
          AVG(delta_vs_actual_position)      AS mean_raw_delta,
          AVG(adjusted_delta)                AS mean_adjusted_delta,
          STDDEV_SAMP(adjusted_delta)        AS sd_adjusted_delta,
          COUNT(*)                           AS n_races,
          SUM(laps_counted)                  AS total_laps,
          AVG(avg_recombination_confidence)  AS mean_confidence
        FROM adjusted
        GROUP BY ego_driver_id, ego_constructor_id
        HAVING COUNT(*) >= ?
      )
      SELECT
        sa.*,
        dr.era_adjusted_rating AS driver_season_rating
      FROM season_agg sa
      LEFT JOIN int_era_normalized_driver_rating dr
        ON dr.driver_id = sa.ego_driver_id
        AND dr.season   = ?
      ORDER BY sa.mean_adjusted_delta ASC
    `, [season, season, hostConstructorId, minRaces, season])
  }
)

export const queryHiddenConstructorOptions = registerQuery<
  { season: number },
  { host_constructor_id: string }[]
>(
  'hidden-performance.constructors',
  async ({ season }) => {
    const manifest = await loadManifest()
    await registerParquet('fct_ghost_race_finish', getTablePath(manifest, 'fct_ghost_race_finish'))

    return rawQuery<{ host_constructor_id: string }>(`
      SELECT DISTINCT host_constructor_id
      FROM fct_ghost_race_finish
      WHERE race_year = ?
      ORDER BY host_constructor_id
    `, [season])
  }
)
