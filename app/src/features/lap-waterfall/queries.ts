// fct_lap_residuals is already filtered to green racing laps upstream: its
// is_safety_car_lap / is_vsc_lap / is_red_flag_lap columns are FALSE on all
// 137,447 rows (re-measured 2026-09-20). Filtering on them here changed no row
// and implied a neutralisation exclusion this query was not performing, so the
// three predicates are gone and the fact is recorded instead. The table with
// live caution flags is int_stint_geometry; the app surfaces it through
// race_caution_timeline on the Race Control Timeline.
import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface LapResidualRow {
  driver_id: string
  /** race_id when a race is selected; 'season' when aggregated across the full season */
  race_id: string
  race_year: number
  // A component is NULL when no lap in the group has a measured value (AP-01).
  // It is never coalesced to 0 s.
  fuel_component_s: number | null
  compound_component_s: number | null
  constructor_component_s: number | null
  /** Mean over laps with pace_delta_s IS NOT NULL only (TX-03: unmeasured dirty air is written as 0.0) */
  dirty_air_tax_s: number | null
  driver_skill_residual_s: number | null
  track_unexplained_s: number | null
  // AP-06: the identity pace_delta = fuel + compound + constructor + dirty_air + skill is
  // only checked on ONE lap set: the laps where all five terms and pace_delta_s are
  // non-NULL. The closed_* means are over that set; the means above each cover their own
  // (possibly larger) set and are the fallback when the closed set is empty.
  closed_fuel_component_s: number | null
  closed_compound_component_s: number | null
  closed_constructor_component_s: number | null
  closed_dirty_air_tax_s: number | null
  closed_driver_skill_residual_s: number | null
  /** AVG(pace_delta_s) over the closed set; NULL when the set is empty */
  pace_delta_s: number | null
  /** Size of the closed set */
  n_closed_laps: number
  n_laps: number
  /** Laps behind each mean (COUNT of the non-NULL values); less than n_laps = partial coverage */
  n_fuel_component_s: number
  n_compound_component_s: number
  n_constructor_component_s: number
  n_dirty_air_tax_s: number
  n_driver_skill_residual_s: number
  n_track_unexplained_s: number
}

interface Params {
  season: number
  raceId: string | null
}

export const queryLapWaterfall = registerQuery<Params, LapResidualRow[]>(
  'lap-waterfall.race',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'fct_lap_residuals', season)
    await registerParquet(`fct_lap_residuals_${season}`, path)

    if (raceId) {
      // Single race: one row per driver for that race
      return rawQuery<LapResidualRow>(`
        WITH laps AS (
          SELECT *, (pace_delta_s IS NOT NULL
            AND compound_component_s IS NOT NULL
            AND constructor_component_s IS NOT NULL
            AND dirty_air_tax_s IS NOT NULL
            AND driver_skill_residual_s IS NOT NULL) AS in_closed_set
          FROM fct_lap_residuals_${season}
        )
        SELECT
          driver_id,
          race_id,
          race_year,
          AVG(fuel_component_s)                       AS fuel_component_s,
          AVG(compound_component_s)                   AS compound_component_s,
          AVG(constructor_component_s)                AS constructor_component_s,
          AVG(CASE WHEN pace_delta_s IS NOT NULL THEN dirty_air_tax_s END) AS dirty_air_tax_s,
          AVG(driver_skill_residual_s)                AS driver_skill_residual_s,
          AVG(track_unexplained_s)                    AS track_unexplained_s,
          AVG(fuel_component_s)         FILTER (WHERE in_closed_set) AS closed_fuel_component_s,
          AVG(compound_component_s)     FILTER (WHERE in_closed_set) AS closed_compound_component_s,
          AVG(constructor_component_s)  FILTER (WHERE in_closed_set) AS closed_constructor_component_s,
          AVG(dirty_air_tax_s)          FILTER (WHERE in_closed_set) AS closed_dirty_air_tax_s,
          AVG(driver_skill_residual_s)  FILTER (WHERE in_closed_set) AS closed_driver_skill_residual_s,
          AVG(pace_delta_s)             FILTER (WHERE in_closed_set) AS pace_delta_s,
          COUNT(*) FILTER (WHERE in_closed_set) AS n_closed_laps,
          COUNT(*)                                    AS n_laps,
          COUNT(fuel_component_s)                     AS n_fuel_component_s,
          COUNT(compound_component_s)                 AS n_compound_component_s,
          COUNT(constructor_component_s)              AS n_constructor_component_s,
          COUNT(CASE WHEN pace_delta_s IS NOT NULL THEN dirty_air_tax_s END) AS n_dirty_air_tax_s,
          COUNT(driver_skill_residual_s)              AS n_driver_skill_residual_s,
          COUNT(track_unexplained_s)                  AS n_track_unexplained_s
        FROM laps
        WHERE race_year = ?
          AND race_id = ?
          AND NOT is_major_outlier_lap
          AND fuel_component_s IS NOT NULL
        GROUP BY driver_id, race_id, race_year
        ORDER BY driver_id
      `, [season, raceId])
    }

    // No race selected: season average per driver (one row per driver)
    return rawQuery<LapResidualRow>(`
      WITH laps AS (
        SELECT *, (pace_delta_s IS NOT NULL
            AND compound_component_s IS NOT NULL
            AND constructor_component_s IS NOT NULL
            AND dirty_air_tax_s IS NOT NULL
            AND driver_skill_residual_s IS NOT NULL) AS in_closed_set
        FROM fct_lap_residuals_${season}
      )
      SELECT
        driver_id,
        'season'                                      AS race_id,
        race_year,
        AVG(fuel_component_s)                       AS fuel_component_s,
        AVG(compound_component_s)                   AS compound_component_s,
        AVG(constructor_component_s)                AS constructor_component_s,
        AVG(CASE WHEN pace_delta_s IS NOT NULL THEN dirty_air_tax_s END) AS dirty_air_tax_s,
        AVG(driver_skill_residual_s)                AS driver_skill_residual_s,
        AVG(track_unexplained_s)                    AS track_unexplained_s,
        AVG(fuel_component_s)         FILTER (WHERE in_closed_set) AS closed_fuel_component_s,
        AVG(compound_component_s)     FILTER (WHERE in_closed_set) AS closed_compound_component_s,
        AVG(constructor_component_s)  FILTER (WHERE in_closed_set) AS closed_constructor_component_s,
        AVG(dirty_air_tax_s)          FILTER (WHERE in_closed_set) AS closed_dirty_air_tax_s,
        AVG(driver_skill_residual_s)  FILTER (WHERE in_closed_set) AS closed_driver_skill_residual_s,
        AVG(pace_delta_s)             FILTER (WHERE in_closed_set) AS pace_delta_s,
        COUNT(*) FILTER (WHERE in_closed_set) AS n_closed_laps,
        COUNT(*)                                    AS n_laps,
        COUNT(fuel_component_s)                     AS n_fuel_component_s,
        COUNT(compound_component_s)                 AS n_compound_component_s,
        COUNT(constructor_component_s)              AS n_constructor_component_s,
        COUNT(CASE WHEN pace_delta_s IS NOT NULL THEN dirty_air_tax_s END) AS n_dirty_air_tax_s,
        COUNT(driver_skill_residual_s)              AS n_driver_skill_residual_s,
        COUNT(track_unexplained_s)                  AS n_track_unexplained_s
      FROM laps
      WHERE race_year = ?
        AND NOT is_major_outlier_lap
        AND fuel_component_s IS NOT NULL
      GROUP BY driver_id, race_year
      ORDER BY driver_id
    `, [season])
  }
)
