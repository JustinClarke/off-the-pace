import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface PitGanttRow {
  driver_id: string
  constructor_id: string
  stint_number: number
  compound: string
  start_lap: number
  end_lap: number
  stint_length_laps: number
  // from fct_stint_features
  cliff_lap_in_stint: number | null
  tyre_management_score: number | null
  // from int_pit_strategy_value
  verdict: string | null
  overrun_laps: number | null
  opportunity_cost_s: number | null
  optimal_pit_lap_in_stint: number | null
  pit_lane_loss_s: number | null
  optimal_pit_lap_confidence: number | null
}

export interface RaceSummaryRow {
  total_laps: number
  driver_count: number
}

interface SeasonParams {
  season: number
}

interface GanttParams {
  race_id: string
  season: number
}

/** Available race_ids for a season (used to populate the race selector). */
export const queryRaceOptions = registerQuery<SeasonParams, { race_id: string }[]>(
  'pit-strategy.race-options',
  async ({ season }) => {
    const manifest = await loadManifest()
    const stintPath = getTablePath(manifest, 'fct_stint_features')
    await registerParquet('fct_stint_features', stintPath)

    return rawQuery<{ race_id: string }>(`
      SELECT DISTINCT race_id
      FROM fct_stint_features
      WHERE race_year = ?
      ORDER BY race_id
    `, [season])
  }
)

/**
 * Loads per-stint Gantt data for a race.
 *
 * Derives contiguous start/end laps from int_pit_strategy_value using window
 * functions: start_lap = prev actual_pit_lap + 1 (or 1), end_lap = actual_pit_lap
 * (or total_laps for the final stint). This avoids the gaps that arise when using
 * fct_lap_residuals, which excludes pit/safety-car laps from its coverage.
 */
export const queryPitGantt = registerQuery<GanttParams, PitGanttRow[]>(
  'pit-strategy.gantt',
  async ({ race_id, season }) => {
    const manifest = await loadManifest()

    const stintPath = getTablePath(manifest, 'fct_stint_features')
    const pvPath    = getTablePath(manifest, 'int_pit_strategy_value')
    const lapPath   = getTablePath(manifest, 'fct_lap_residuals', season)
    await Promise.all([
      registerParquet('fct_stint_features',    stintPath),
      registerParquet('int_pit_strategy_value', pvPath),
      registerParquet(`fct_lap_residuals_${season}`, lapPath),
    ])

    return rawQuery<PitGanttRow>(`
      WITH total_laps AS (
        SELECT MAX(lap_number) AS n
        FROM fct_lap_residuals_${season}
        WHERE race_id = ?
      ),
      ordered AS (
        SELECT
          pv.stint_id,
          pv.driver_id,
          pv.race_id,
          pv.compound,
          pv.stint_length_laps,
          pv.actual_pit_lap,
          pv.cliff_onset_lap_in_stint,
          pv.optimal_pit_lap_in_stint,
          pv.overrun_laps,
          pv.opportunity_cost_s,
          pv.strategy_verdict,
          pv.pit_lane_loss_s,
          pv.optimal_pit_lap_confidence,
          ROW_NUMBER() OVER (
            PARTITION BY pv.race_id, pv.driver_id
            ORDER BY pv.actual_pit_lap NULLS LAST
          ) AS stint_number,
          LAG(pv.actual_pit_lap) OVER (
            PARTITION BY pv.race_id, pv.driver_id
            ORDER BY pv.actual_pit_lap NULLS LAST
          ) AS prev_pit_lap
        FROM int_pit_strategy_value pv
        WHERE pv.race_id = ?
      )
      SELECT
        o.driver_id,
        s.constructor_id,
        CAST(o.stint_number AS INTEGER)                        AS stint_number,
        o.compound,
        CAST(COALESCE(o.prev_pit_lap + 1, 1) AS INTEGER)      AS start_lap,
        CAST(COALESCE(o.actual_pit_lap, tl.n) AS INTEGER)     AS end_lap,
        CAST(o.stint_length_laps AS INTEGER)                   AS stint_length_laps,
        CAST(s.cliff_lap_in_stint AS INTEGER)                  AS cliff_lap_in_stint,
        s.tyre_management_score,
        o.strategy_verdict                                     AS verdict,
        CAST(o.overrun_laps AS INTEGER)                        AS overrun_laps,
        o.opportunity_cost_s,
        CAST(o.optimal_pit_lap_in_stint AS INTEGER)            AS optimal_pit_lap_in_stint,
        o.pit_lane_loss_s,
        CAST(o.optimal_pit_lap_confidence AS DOUBLE)           AS optimal_pit_lap_confidence
      FROM ordered o
      CROSS JOIN total_laps tl
      LEFT JOIN fct_stint_features s ON o.stint_id = s.stint_id
      ORDER BY o.driver_id, o.stint_number
    `, [race_id, race_id])
  }
)

/**
 * Total laps for the race (used to set the Gantt x-axis extent).
 */
export const queryRaceSummary = registerQuery<GanttParams, RaceSummaryRow[]>(
  'pit-strategy.race-summary',
  async ({ race_id, season }) => {
    const manifest = await loadManifest()
    const lapPath = getTablePath(manifest, 'fct_lap_residuals', season)
    await registerParquet(`fct_lap_residuals_${season}`, lapPath)

    return rawQuery<RaceSummaryRow>(`
      SELECT
        MAX(lap_number)          AS total_laps,
        COUNT(DISTINCT driver_id) AS driver_count
      FROM fct_lap_residuals_${season}
      WHERE race_id = ?
    `, [race_id])
  }
)
