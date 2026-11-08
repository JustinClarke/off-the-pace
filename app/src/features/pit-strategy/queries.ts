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
  /** Compound of the next stint of this driver in stint-number order; null after the last one. */
  next_compound: string | null
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
 * AP-08: stints are taken from fct_stint_features (all of them) in stint-number order
 * (suffix of stint_id), with int_pit_strategy_value LEFT-joined for the verdict columns:
 * that mart lacks 734 of 8,945 stints in 136 races, and ordering by its rows alone gave
 * the wrong next compound on 142 stops. A stint with no mart row ends at the running sum of
 * stint_length_laps (exact on all 8,943 numbered stints against int_stint_end_regime; two
 * orphan ids with no stint number and no compound, 2018_2018_2_RIC_ and 2018_2018_10_HAR_, are skipped,
 * as they were before).
 * Contiguous start/end laps use window functions in that order: end_lap = the stop (actual_pit_lap) for a stint that ended in one, else
 * the stint's own last lap (the flag, or a retirement on track); start_lap = the
 * previous stint's end_lap + 1 (or 1). This avoids the gaps that arise when
 * using fct_lap_residuals, which excludes pit/safety-car laps from its coverage.
 *
 * No race-length fallback: every stint that ended in a stop carries its stop,
 * whatever flag was out (WI-13, F31; asserted by T23 in the transform). This
 * used to end a stint with no matched stop at the race's last valid lap, which
 * drew 194 of 653 SC-ended and 107 of 116 red-flag-ended stints to the
 * chequered flag.
 */
export const queryPitGantt = registerQuery<GanttParams, PitGanttRow[]>(
  'pit-strategy.gantt',
  async ({ race_id }) => {
    const manifest = await loadManifest()

    const stintPath = getTablePath(manifest, 'fct_stint_features')
    const pvPath    = getTablePath(manifest, 'int_pit_strategy_value')
    await Promise.all([
      registerParquet('fct_stint_features',    stintPath),
      registerParquet('int_pit_strategy_value', pvPath),
    ])

    return rawQuery<PitGanttRow>(`
      WITH base AS (
        SELECT
          f.stint_id, f.driver_id, f.race_id, f.constructor_id, f.compound,
          f.stint_length_laps, f.cliff_lap_in_stint, f.tyre_management_score,
          TRY_CAST(regexp_extract(f.stint_id, '([0-9]+)$', 1) AS INTEGER) AS stint_number
        FROM fct_stint_features f
        WHERE f.race_id = ?
          AND regexp_matches(f.stint_id, '[0-9]+$')
      ),
      chained AS (
        SELECT
          b.*,
          pv.actual_pit_lap,
          pv.optimal_pit_lap_in_stint,
          pv.overrun_laps,
          pv.opportunity_cost_s,
          pv.strategy_verdict,
          pv.pit_lane_loss_s,
          pv.optimal_pit_lap_confidence,
          SUM(b.stint_length_laps) OVER (
            PARTITION BY b.race_id, b.driver_id
            ORDER BY b.stint_number
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
          ) AS cum_end_lap
        FROM base b
        LEFT JOIN int_pit_strategy_value pv ON pv.stint_id = b.stint_id
      ),
      ordered AS (
        SELECT
          c.*,
          COALESCE(c.actual_pit_lap, c.cum_end_lap) AS end_lap
        FROM chained c
      )
      SELECT
        o.driver_id,
        o.constructor_id,
        CAST(o.stint_number AS INTEGER)                        AS stint_number,
        o.compound,
        CAST(COALESCE(LAG(o.end_lap) OVER w + 1, 1) AS INTEGER) AS start_lap,
        CAST(o.end_lap AS INTEGER)                             AS end_lap,
        CAST(o.stint_length_laps AS INTEGER)                   AS stint_length_laps,
        LEAD(o.compound) OVER w                                AS next_compound,
        CAST(o.cliff_lap_in_stint AS INTEGER)                  AS cliff_lap_in_stint,
        o.tyre_management_score,
        o.strategy_verdict                                     AS verdict,
        CAST(o.overrun_laps AS INTEGER)                        AS overrun_laps,
        o.opportunity_cost_s,
        CAST(o.optimal_pit_lap_in_stint AS INTEGER)            AS optimal_pit_lap_in_stint,
        o.pit_lane_loss_s,
        CAST(o.optimal_pit_lap_confidence AS DOUBLE)           AS optimal_pit_lap_confidence
      FROM ordered o
      WINDOW w AS (PARTITION BY o.race_id, o.driver_id ORDER BY o.stint_number)
      ORDER BY o.driver_id, o.stint_number
    `, [race_id])
  }
)

/**
 * Total laps for the race: the last VALID lap (fct_lap_residuals holds valid
 * laps only), so a race that finished under a safety car or red flag reads
 * short. transform() widens the Gantt axis to the last stint's end lap.
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
