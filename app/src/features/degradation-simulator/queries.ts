// Preset loader: pulls a real stint out of fct_cliff_prediction_features so the user can score an
// actual lapped tyre (all 38 features faithful) instead of hand-dialled sliders, and overlay the
// observed next-lap degradation jump against the model's predicted fan. This is the "load a real
// stint" affordance from the Feature 16 spec.

import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

/** A pickable real stint, summarised for the preset selector. */
export interface StintOption {
  stint_id: string
  race_id: string
  circuit_name: string
  driver_id: string
  constructor_id: string
  compound: string
  stint_length: number
  stint_number: number
}

/** One real lap of a stint: every feature the model reads, plus the observed jump for overlay. */
export interface StintFeatureRow {
  lap_in_stint: number
  age_in_stint: number
  lap_number: number
  fuel_mass_kg: number | null
  compound: string
  compound_grip_peak: number | null
  compound_wear_gradient: number | null
  compound_optimal_temp_low: number | null
  compound_optimal_temp_high: number | null
  compound_cliff_onset_laps: number | null
  compound_cliff_severity: number | null
  expected_compound_pace_s: number | null
  expected_degradation_rate_s_per_lap: number | null
  cliff_onset_passed: boolean | null
  laps_past_cliff: number | null
  cliff_candidate_flag: boolean | null
  push_residual: number | null
  cumulative_push_load_surface: number | null
  cumulative_push_load_bulk: number | null
  dirty_air_share_lap: number | null
  dirty_air_thermal_load_surface: number | null
  dirty_air_thermal_load_bulk: number | null
  air_state_dominant: string | null
  ambient_temp_delta: number | null
  is_rain_lap: boolean | null
  track_energy_index: number | null
  circuit_abrasiveness_index: number | null
  constructor_id: string
  event_flag_any: boolean | null
  anomaly_class: string | null
  /** The training target: observed next-lap degradation jump. NULL on the final lap of a stint. */
  next_lap_degradation_jump_s: number | null
}

const TABLE = 'fct_cliff_prediction_features'

async function registerSeason(season: number): Promise<string> {
  const manifest = await loadManifest()
  const path = getTablePath(manifest, TABLE, season)
  const view = `${TABLE}_${season}`
  await Promise.all([
    registerParquet(view, path),
    registerParquet('race_to_track', getTablePath(manifest, 'race_to_track')),
    registerParquet('dim_circuits', getTablePath(manifest, 'dim_circuits')),
  ])
  return view
}

/** A curated set of pickable stints for a season: real, complete, varied-compound. */
export const queryStintOptions = registerQuery<{ season: number }, StintOption[]>(
  'degradation-simulator.stint-options',
  async ({ season }) => {
    const view = await registerSeason(season)
    return rawQuery<StintOption>(`
      WITH base AS (
        SELECT
          stint_id,
          any_value(race_id)        AS race_id,
          any_value(driver_id)      AS driver_id,
          any_value(constructor_id) AS constructor_id,
          any_value(compound)       AS compound,
          max(lap_in_stint)         AS stint_length,
          -- extract the trailing stint number from stint_id (e.g. "2024_2024_1_LEC_2" → 2)
          TRY_CAST(REGEXP_EXTRACT(stint_id, '_([0-9]+)$', 1) AS INTEGER) AS stint_number
        FROM ${view}
        GROUP BY stint_id
      )
      SELECT
        b.stint_id,
        b.race_id,
        COALESCE(dc.circuit_name, b.race_id) AS circuit_name,
        b.driver_id,
        b.constructor_id,
        b.compound,
        b.stint_length,
        b.stint_number
      FROM base b
      LEFT JOIN race_to_track rt
        ON CAST(REPLACE(b.race_id, '_', '') AS INTEGER) = rt.race_id
      LEFT JOIN dim_circuits dc
        ON rt.track_id = dc.circuit_key
      ORDER BY b.race_id, b.driver_id, b.stint_number
    `, [])
  }
)

/** Every lap of one chosen stint, ordered, with all model features + the observed jump. */
export const queryStintRows = registerQuery<{ season: number; stintId: string }, StintFeatureRow[]>(
  'degradation-simulator.stint-rows',
  async ({ season, stintId }) => {
    const view = await registerSeason(season)
    return rawQuery<StintFeatureRow>(`
      SELECT
        lap_in_stint, age_in_stint, lap_number, fuel_mass_kg, compound,
        compound_grip_peak, compound_wear_gradient, compound_optimal_temp_low,
        compound_optimal_temp_high, compound_cliff_onset_laps, compound_cliff_severity,
        expected_compound_pace_s, expected_degradation_rate_s_per_lap,
        cliff_onset_passed, laps_past_cliff, cliff_candidate_flag,
        push_residual, cumulative_push_load_surface, cumulative_push_load_bulk,
        dirty_air_share_lap, dirty_air_thermal_load_surface, dirty_air_thermal_load_bulk,
        air_state_dominant, ambient_temp_delta, is_rain_lap,
        track_energy_index, circuit_abrasiveness_index, constructor_id,
        event_flag_any, anomaly_class, next_lap_degradation_jump_s
      FROM ${view}
      WHERE stint_id = ?
      ORDER BY lap_in_stint
    `, [stintId])
  }
)
