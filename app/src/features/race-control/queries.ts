// Caution timeline + hazard context.
//
// Two sources, deliberately kept apart on the page because they are different
// kinds of statement:
//
//   race_caution_timeline  - one row per (race, lap), derived in
//     scripts/export_app_data.py from int_stint_geometry's per-driver lap
//     flags. This is a RECORD. Lap 24 ran under safety car or it did not.
//
//   int_sc_hazard_history  - one row per (circuit_slug, season), season-lagged
//     and empirical-Bayes shrunk. This is an ESTIMATE, and at ~4 races per
//     circuit a weak one. Only the *_shrunk columns are selected here; the raw
//     per-circuit rates are never read into the app. See methodology.tsx.
import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface CautionLapRow {
  lap_number: number
  caution_status: 'green' | 'safety_car' | 'vsc' | 'red_flag'
  race_laps: number
}

export interface HazardRow {
  circuit_slug: string
  season: number
  /** Prior races at this venue the estimate is built from. 0 = nothing to estimate from. */
  prior_races_n: number
  prior_racing_laps: number
  /** Shrunk per-racing-lap rates. NULL across all of 2018: no prior season exists. */
  sc_hazard_per_lap_shrunk: number | null
  vsc_hazard_per_lap_shrunk: number | null
  any_hazard_per_lap_shrunk: number | null
}

/** Pooled, all-circuits caution frequency per season plus the grand total. */
export interface PooledRateRow {
  race_year: number | null
  races: number
  races_with_caution: number
  races_with_sc: number
  races_with_vsc: number
  races_with_red: number
  caution_laps: number
  total_laps: number
}

async function registerTimeline(): Promise<void> {
  const manifest = await loadManifest()
  await registerParquet('race_caution_timeline', getTablePath(manifest, 'race_caution_timeline'))
}

/** The lap-by-lap status of one race. Every lap, not only the caution ones. */
export const queryCautionTimeline = registerQuery<{ season: number; raceId: string }, CautionLapRow[]>(
  'race-control.timeline',
  async ({ season, raceId }) => {
    await registerTimeline()
    return rawQuery<CautionLapRow>(`
      SELECT
        CAST(lap_number AS INTEGER) AS lap_number,
        caution_status,
        CAST(race_laps AS INTEGER)  AS race_laps
      FROM race_caution_timeline
      WHERE race_year = ? AND race_id = ?
      ORDER BY lap_number
    `, [season, raceId])
  }
)

/**
 * Pooled caution frequency per season, and one grand-total row (race_year NULL).
 *
 * The denominator travels with every numerator: the page renders no rate without
 * the race count it was computed from.
 */
export const queryPooledRates = registerQuery<Record<string, never>, PooledRateRow[]>(
  'race-control.pooled-rates',
  async () => {
    await registerTimeline()
    return rawQuery<PooledRateRow>(`
      WITH per_race AS (
        SELECT
          race_year,
          race_id,
          MAX(CASE WHEN caution_status <> 'green' THEN 1 ELSE 0 END)    AS had_caution,
          MAX(CASE WHEN is_safety_car_lap THEN 1 ELSE 0 END)            AS had_sc,
          MAX(CASE WHEN is_vsc_lap        THEN 1 ELSE 0 END)            AS had_vsc,
          MAX(CASE WHEN is_red_flag_lap   THEN 1 ELSE 0 END)            AS had_red,
          COUNT(*) FILTER (WHERE caution_status <> 'green')             AS caution_laps,
          COUNT(*)                                                      AS total_laps
        FROM race_caution_timeline
        GROUP BY race_year, race_id
      ),
      rolled AS (
        SELECT
          CAST(race_year AS INTEGER) AS race_year,
          CAST(COUNT(*) AS INTEGER)              AS races,
          CAST(SUM(had_caution) AS INTEGER)      AS races_with_caution,
          CAST(SUM(had_sc) AS INTEGER)           AS races_with_sc,
          CAST(SUM(had_vsc) AS INTEGER)          AS races_with_vsc,
          CAST(SUM(had_red) AS INTEGER)          AS races_with_red,
          CAST(SUM(caution_laps) AS INTEGER)     AS caution_laps,
          CAST(SUM(total_laps) AS INTEGER)       AS total_laps
        FROM per_race
        GROUP BY ROLLUP (race_year)
      )
      SELECT * FROM rolled ORDER BY race_year NULLS LAST
    `)
  }
)

/**
 * Hazard context for one race's venue and season.
 *
 * Returns at most one row, and that row may be all-NULL on the rates: every
 * 2018 row is, by construction, because the model is season-lagged and 2018 is
 * the first season in the warehouse. The page declares that state; it does not
 * COALESCE it to zero, which would assert a measured zero hazard.
 */
export const queryCircuitHazard = registerQuery<{ season: number; raceId: string }, HazardRow[]>(
  'race-control.circuit-hazard',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    await Promise.all([
      registerParquet('int_sc_hazard_history', getTablePath(manifest, 'int_sc_hazard_history')),
      registerParquet('race_to_track', getTablePath(manifest, 'race_to_track')),
    ])
    return rawQuery<HazardRow>(`
      SELECT
        h.circuit_slug,
        CAST(h.season AS INTEGER)            AS season,
        CAST(h.prior_races_n AS INTEGER)     AS prior_races_n,
        CAST(h.prior_racing_laps AS INTEGER) AS prior_racing_laps,
        h.sc_hazard_per_lap_shrunk,
        h.vsc_hazard_per_lap_shrunk,
        h.any_hazard_per_lap_shrunk
      FROM race_to_track rt
      JOIN int_sc_hazard_history h
        ON rt.track_id = h.circuit_slug
       AND h.season = ?
      WHERE rt.race_id = ?
    `, [season, raceId])
  }
)
