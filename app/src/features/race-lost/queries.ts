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

export interface RaceLostRow {
  // A total is NULL when no lap in the group has a measured value (AP-01).
  // It is never coalesced to 0 s.
  total_fuel_s: number | null
  total_compound_s: number | null
  total_constructor_s: number | null
  /** Sum over laps with pace_delta_s IS NOT NULL only (TX-03: unmeasured dirty air is written as 0.0) */
  total_dirty_air_s: number | null
  total_skill_s: number | null
  total_track_s: number | null
  // AP-06: the identity pace_delta = fuel + compound + constructor + dirty_air + skill is
  // only checked on ONE lap set: the laps where all five terms and pace_delta_s are
  // non-NULL. The closed_* sums below are over that set; the total_* sums above each cover
  // their own (possibly larger) set and are the fallback when the closed set is empty.
  closed_fuel_s: number | null
  closed_compound_s: number | null
  closed_constructor_s: number | null
  closed_dirty_air_s: number | null
  closed_skill_s: number | null
  /** SUM(pace_delta_s) over the closed set; NULL when the set is empty */
  total_pace_delta_s: number | null
  /** Size of the closed set */
  n_closed_laps: number
  n_laps: number
  /** Laps behind each total (COUNT of the non-NULL values); less than n_laps = partial coverage */
  n_fuel_component_s: number
  n_compound_component_s: number
  n_constructor_component_s: number
  n_dirty_air_tax_s: number
  n_driver_skill_residual_s: number
  n_track_unexplained_s: number
}

interface Params {
  season: number
  raceId: string
  driverId: string
}

async function registerLapResiduals(season: number): Promise<string> {
  const manifest = await loadManifest()
  const path = getTablePath(manifest, 'fct_lap_residuals', season)
  const alias = `fct_lap_residuals_${season}`
  await registerParquet(alias, path)
  return alias
}

export const queryRaceLost = registerQuery<Params, RaceLostRow[]>(
  'race-lost.driver',
  async ({ season, raceId, driverId }) => {
    const alias = await registerLapResiduals(season)

    return rawQuery<RaceLostRow>(`
      WITH laps AS (
        SELECT
          *,
          (pace_delta_s IS NOT NULL
            AND compound_component_s IS NOT NULL
            AND constructor_component_s IS NOT NULL
            AND dirty_air_tax_s IS NOT NULL
            AND driver_skill_residual_s IS NOT NULL) AS in_closed_set
        FROM ${alias}
        WHERE race_year = ?
          AND race_id   = ?
          AND driver_id = ?
          AND NOT is_major_outlier_lap
          AND fuel_component_s IS NOT NULL
      )
      SELECT
        SUM(fuel_component_s)                       AS total_fuel_s,
        SUM(compound_component_s)                   AS total_compound_s,
        SUM(constructor_component_s)                AS total_constructor_s,
        SUM(CASE WHEN pace_delta_s IS NOT NULL THEN dirty_air_tax_s END) AS total_dirty_air_s,
        SUM(driver_skill_residual_s)                AS total_skill_s,
        SUM(track_unexplained_s)                    AS total_track_s,
        SUM(fuel_component_s)         FILTER (WHERE in_closed_set) AS closed_fuel_s,
        SUM(compound_component_s)     FILTER (WHERE in_closed_set) AS closed_compound_s,
        SUM(constructor_component_s)  FILTER (WHERE in_closed_set) AS closed_constructor_s,
        SUM(dirty_air_tax_s)          FILTER (WHERE in_closed_set) AS closed_dirty_air_s,
        SUM(driver_skill_residual_s)  FILTER (WHERE in_closed_set) AS closed_skill_s,
        SUM(pace_delta_s)             FILTER (WHERE in_closed_set) AS total_pace_delta_s,
        COUNT(*) FILTER (WHERE in_closed_set)       AS n_closed_laps,
        COUNT(*)                                    AS n_laps,
        COUNT(fuel_component_s)                     AS n_fuel_component_s,
        COUNT(compound_component_s)                 AS n_compound_component_s,
        COUNT(constructor_component_s)              AS n_constructor_component_s,
        COUNT(CASE WHEN pace_delta_s IS NOT NULL THEN dirty_air_tax_s END) AS n_dirty_air_tax_s,
        COUNT(driver_skill_residual_s)              AS n_driver_skill_residual_s,
        COUNT(track_unexplained_s)                  AS n_track_unexplained_s
      FROM laps
    `, [season, raceId, driverId])
  }
)

export const queryRaceLostDrivers = registerQuery<
  { season: number; raceId: string },
  { driver_id: string }[]
>(
  'race-lost.drivers',
  async ({ season, raceId }) => {
    const alias = await registerLapResiduals(season)

    return rawQuery<{ driver_id: string }>(`
      SELECT DISTINCT driver_id
      FROM ${alias}
      WHERE race_year = ?
        AND race_id   = ?
        AND fuel_component_s IS NOT NULL
      ORDER BY driver_id
    `, [season, raceId])
  }
)
