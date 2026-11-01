import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

/**
 * One row per driver for one race, from int_lap_wake_placeholder_cost (WC-11).
 *
 * Every cost here is a PLACEHOLDER: an assumed per-lap loss for the race (WC-12:
 * the layout's corner mix x a regulation-era factor; a flagged circuit-class
 * fallback when the race has no corner structure), scaled by the lap's measured exposure (time within 1 s of the car
 * ahead, tapering to nothing at 2 s). WC-13: per lap the race value is multiplied
 * by an assumed tyre factor (WC-16: the lap's C-number against the race's medium;
 * 2018: the relative dry compound) and a car factor
 * (neutral 1.00 for every team: no per-team claim), bounded and flagged.
 * Modelled, never measured. A lap with no
 * value (no gap measured, or a neutralised lap) is counted in
 * `laps_unavailable` with its reason, never summed as 0.
 */
export interface DirtyAirCostRow {
  driver_id: string
  /** Sum over laps with a value; NULL when the driver has none. */
  total_placeholder_cost_s: number | null
  /** Mean over laps with a value; NULL when the driver has none. */
  avg_placeholder_cost_s: number | null
  laps_modelled: number
  laps_unavailable: number
  total_laps: number
  /** Distinct reasons for the unavailable laps, '; '-joined; NULL when none. */
  unavailable_reasons: string | null
  corner_class: string
  /** The race's assumed loss for a full lap within 1 s, before the tyre and car factors. */
  race_loss_s_per_lap_within_1s: number
  /** WC-13: mean per-lap assumed loss (race x tyre x car) over the driver's modelled laps. */
  avg_lap_loss_s: number | null
  /** WC-13: tyre factors on the driver's modelled laps, e.g. 'HARD (C3) x0.96, MEDIUM (C4) x1.00' (C-number since WC-16; none in 2018). */
  tyre_factors: string | null
  /** WC-13: modelled laps whose tyre factor is neutral by rule (wet / intermediate) or a missing-compound fallback. */
  laps_tyre_neutral: number
  constructor_id: string | null
  constructor_factor: number
  /** 'neutral_default' (the seed's neutral 1.00), 'public_concept', or a flagged missing-key fallback. */
  constructor_factor_source: string
  constructor_basis: string
  /** WC-13: modelled laps (with a value) whose race x tyre x car value was held to the 0.15-0.55 s bounds. */
  laps_lap_loss_bounded: number
  /** WC-13: distinct factor fallback flags on the modelled laps, '; '-joined; NULL when every factor resolved. */
  factor_flags: string | null
  /** WC-12: regulation era and its assumed factor for the season. */
  era: string
  era_factor: number
  /** 'race_structure' (the rule) or 'class_fallback' (no corner structure for the race). */
  loss_source: string
  loss_bounded: boolean
  /** One line stating how the race's assumed loss was set. */
  loss_basis: string
  value_kind: string
  disclaimer: string
  disclaimer_placeholder: string
}

interface Params {
  season: number
  raceId: string
}

/** WC-16: a lap's tyre label with its C-number when it has one, e.g. 'SOFT (C4) x1.10' or 'HARD x0.96' (2018). */
export const TYRE_LABEL_SQL =
  "COALESCE(compound_class, 'unresolved') || COALESCE(' (' || tyre_c_number || ')', '') || ' x' || printf('%.2f', compound_factor)"

export function buildDirtyAirCostSql(season: number): string {
  return `
      SELECT
        driver_id,
        SUM(wake_cost_placeholder_s)                                AS total_placeholder_cost_s,
        AVG(wake_cost_placeholder_s)                                AS avg_placeholder_cost_s,
        COUNT(wake_cost_placeholder_s)                              AS laps_modelled,
        COUNT(*) - COUNT(wake_cost_placeholder_s)                   AS laps_unavailable,
        COUNT(*)                                                    AS total_laps,
        STRING_AGG(DISTINCT unavailable_reason, '; ')               AS unavailable_reasons,
        ANY_VALUE(corner_class)                                     AS corner_class,
        ANY_VALUE(race_loss_s_per_lap_within_1s)                    AS race_loss_s_per_lap_within_1s,
        AVG(loss_s_per_lap_within_1s) FILTER (WHERE wake_cost_placeholder_s IS NOT NULL)
                                                                    AS avg_lap_loss_s,
        STRING_AGG(DISTINCT ${TYRE_LABEL_SQL}, ', ' ORDER BY ${TYRE_LABEL_SQL})
          FILTER (WHERE wake_cost_placeholder_s IS NOT NULL)        AS tyre_factors,
        COUNT(*) FILTER (WHERE wake_cost_placeholder_s IS NOT NULL
                           AND compound_factor_source LIKE 'neutral%') AS laps_tyre_neutral,
        ANY_VALUE(constructor_id)                                   AS constructor_id,
        ANY_VALUE(constructor_factor)                               AS constructor_factor,
        ANY_VALUE(constructor_factor_source)                        AS constructor_factor_source,
        ANY_VALUE(constructor_basis)                                AS constructor_basis,
        COUNT(*) FILTER (WHERE wake_cost_placeholder_s IS NOT NULL
                           AND lap_loss_bounded)                    AS laps_lap_loss_bounded,
        STRING_AGG(DISTINCT factor_flag, '; ')
          FILTER (WHERE wake_cost_placeholder_s IS NOT NULL)        AS factor_flags,
        ANY_VALUE(era)                                              AS era,
        ANY_VALUE(era_factor)                                       AS era_factor,
        ANY_VALUE(loss_source)                                      AS loss_source,
        ANY_VALUE(loss_bounded)                                     AS loss_bounded,
        ANY_VALUE(loss_basis)                                       AS loss_basis,
        ANY_VALUE(value_kind)                                       AS value_kind,
        ANY_VALUE(disclaimer)                                       AS disclaimer,
        ANY_VALUE(disclaimer_placeholder)                           AS disclaimer_placeholder
      FROM int_lap_wake_placeholder_cost_${season}
      WHERE race_year = ?
        AND CAST(race_id AS VARCHAR) = ?
      GROUP BY driver_id
      ORDER BY total_placeholder_cost_s DESC NULLS LAST
    `
}

export const queryDirtyAirCost = registerQuery<Params, DirtyAirCostRow[]>(
  'dirty-air-cost.race',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_lap_wake_placeholder_cost', season)
    await registerParquet(`int_lap_wake_placeholder_cost_${season}`, path)
    return rawQuery<DirtyAirCostRow>(buildDirtyAirCostSql(season), [season, raceId])
  }
)

/**
 * One row per lap for one driver in one race (same table as above, no warehouse change).
 * Measured: share_lap_within_1s / share_lap_within_2s. Assumed: the loss columns.
 * A neutralised lap or one with no gap has a NULL cost and a reason.
 */
export interface DirtyAirLapRow {
  lap_number: number
  share_lap_within_1s: number | null
  share_lap_within_2s: number | null
  wake_exposure: number | null
  wake_cost_placeholder_s: number | null
  loss_s_per_lap_within_1s: number | null
  race_loss_s_per_lap_within_1s: number | null
  compound_class: string | null
  /** WC-16: the lap's Pirelli C-number; NULL in 2018 and for wet / missing compounds. */
  tyre_c_number: string | null
  compound_factor: number | null
  constructor_factor: number | null
  unavailable_reason: string | null
}

interface LapParams extends Params {
  driverId: string
}

export const DIRTY_AIR_LAPS_SQL = (season: number): string => `
      SELECT
        lap_number, share_lap_within_1s, share_lap_within_2s, wake_exposure,
        wake_cost_placeholder_s, loss_s_per_lap_within_1s, race_loss_s_per_lap_within_1s,
        compound_class, tyre_c_number, compound_factor, constructor_factor, unavailable_reason
      FROM int_lap_wake_placeholder_cost_${season}
      WHERE race_year = ?
        AND CAST(race_id AS VARCHAR) = ?
        AND driver_id = ?
      ORDER BY lap_number
    `

export const queryDirtyAirLaps = registerQuery<LapParams, DirtyAirLapRow[]>(
  'dirty-air-cost.laps',
  async ({ season, raceId, driverId }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_lap_wake_placeholder_cost', season)
    await registerParquet(`int_lap_wake_placeholder_cost_${season}`, path)
    return rawQuery<DirtyAirLapRow>(DIRTY_AIR_LAPS_SQL(season), [season, raceId, driverId])
  }
)
