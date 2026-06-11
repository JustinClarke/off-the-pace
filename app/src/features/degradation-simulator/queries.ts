// Preset loader: pulls a real stint out of fct_cliff_prediction_features so the user can score an
// actual lapped tyre (all 42 features faithful) instead of hand-dialled sliders, and overlay the
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
  circuit_id: string | null
  season: number
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
  // v3 telemetry features (per-lap; ~90-100% populated 2018-2024). Carried so a loaded real stint
  // scores the full 41-wide vector instead of leaving these 11 as native-missing.
  n_gear_changes: number | null
  mean_rpm: number | null
  max_rpm: number | null
  pct_full_throttle: number | null
  pct_drs_active: number | null
  short_shift_index: number | null
  mid_corner_speed_loss_kph: number | null
  traction_wheelspin_proxy: number | null
  throttle_trace_decay: number | null
  braking_point_drift_m: number | null
  lift_coast_share: number | null
  /** The training target: observed next-lap degradation jump. NULL on the final lap of a stint. */
  next_lap_degradation_jump_s: number | null
}

/** A pickable physical circuit, with the per-circuit physics the recomposition needs. */
export interface CircuitOption {
  circuit_id: string
  circuit_name: string
  track_energy_index: number
  abrasiveness_index: number
  weight_penalty_factor: number
  fuel_consumption_rate_kg_per_lap: number
  era_start_year: number
}

/** Per-circuit compound constants + circuit physics for a chosen circuit/compound/era. */
export interface CircuitCompoundConstants {
  compound: string
  compound_grip_peak: number | null
  compound_wear_gradient: number | null
  compound_optimal_temp_low: number | null
  compound_optimal_temp_high: number | null
  compound_cliff_onset_laps: number | null
  compound_cliff_severity: number | null
  weight_penalty_factor: number | null
  fuel_consumption_rate_kg_per_lap: number | null
  track_energy_index: number | null
  abrasiveness_index: number | null
}

/** One lap-in-stint row of the historical envelope (absolute fuel-removed pace + deg-from-fresh). */
export interface HistoryEnvelopeRow {
  lap_in_stint: number
  n_observations: number
  ref_green_pace_s: number
  obs_fuel_removed_pace_p10_s: number
  obs_fuel_removed_pace_p50_s: number
  obs_fuel_removed_pace_p90_s: number
  obs_deg_from_fresh_p10_s: number
  obs_deg_from_fresh_p50_s: number
  obs_deg_from_fresh_p90_s: number
  /** Isotonic-fitted monotone degradation (0 violations; faithful to observed ± MAE ≤ 0.5s). */
  obs_deg_from_fresh_p10_mono_s: number | null
  obs_deg_from_fresh_p50_mono_s: number | null
  obs_deg_from_fresh_p90_mono_s: number | null
  /** Dirty-air multiplier [1.0, 1.15]; 1.0 when the sign/significance gate fails. Constant within a cell. */
  dirty_air_deg_mult: number
  /** °C of ambient_temp_delta before the compound-window overheating penalty engages. Constant within a cell. */
  temp_headroom_c: number
  /** s per °C of ambient_temp_delta past the headroom. Constant within a cell. */
  temp_penalty_s_per_deg: number
}

const TABLE = 'fct_cliff_prediction_features'

async function registerDims(): Promise<void> {
  const manifest = await loadManifest()
  await Promise.all([
    registerParquet('dim_circuits', getTablePath(manifest, 'dim_circuits')),
    registerParquet('dim_compounds_season', getTablePath(manifest, 'dim_compounds_season')),
    registerParquet(
      'mart_degradation_history_envelope',
      getTablePath(manifest, 'mart_degradation_history_envelope'),
    ),
  ])
}

/** Physical circuits with their fitted fuel/energy/abrasiveness physics, for the Circuit picker. */
export const queryCircuitOptions = registerQuery<Record<string, never>, CircuitOption[]>(
  'degradation-simulator.circuit-options',
  async () => {
    await registerDims()
    return rawQuery<CircuitOption>(`
      SELECT
        circuit_id,
        any_value(circuit_name)                   AS circuit_name,
        avg(track_energy_index)                   AS track_energy_index,
        round(avg(abrasiveness_index))            AS abrasiveness_index,
        avg(weight_penalty_factor)                AS weight_penalty_factor,
        avg(fuel_consumption_rate_kg_per_lap)     AS fuel_consumption_rate_kg_per_lap,
        max(era_start_year)                       AS era_start_year
      FROM dim_circuits
      GROUP BY circuit_id
      ORDER BY circuit_name
    `, [])
  }
)

/**
 * Per-circuit compound constants for a chosen circuit/compound/era. Averages the fitted
 * dim_compounds_season params over the circuit's event-keys and the era's seasons, and carries
 * the circuit-level physics from dim_circuits. Replaces COMPOUND_DEFAULTS once a circuit is picked.
 */
export const queryCircuitCompoundConstants = registerQuery<
  { circuitId: string; compound: string; era: string },
  CircuitCompoundConstants[]
>(
  'degradation-simulator.circuit-compound-constants',
  async ({ circuitId, compound, era }) => {
    await registerDims()
    const seasonPredicate = era === 'pre2022' ? 'cs.season < 2022' : 'cs.season >= 2022'
    return rawQuery<CircuitCompoundConstants>(`
      WITH circ AS (
        SELECT
          circuit_id,
          any_value(weight_penalty_factor)            AS weight_penalty_factor,
          any_value(fuel_consumption_rate_kg_per_lap) AS fuel_consumption_rate_kg_per_lap,
          avg(track_energy_index)                     AS track_energy_index,
          round(avg(abrasiveness_index))              AS abrasiveness_index
        FROM dim_circuits
        WHERE circuit_id = ?
        GROUP BY circuit_id
      ),
      keys AS (
        SELECT DISTINCT circuit_key FROM dim_circuits WHERE circuit_id = ?
      ),
      cmp AS (
        SELECT
          avg(cs.compound_grip_peak)        AS compound_grip_peak,
          avg(cs.compound_wear_gradient)    AS compound_wear_gradient,
          avg(cs.compound_optimal_temp_low) AS compound_optimal_temp_low,
          avg(cs.compound_optimal_temp_high) AS compound_optimal_temp_high,
          avg(cs.compound_cliff_onset_laps) AS compound_cliff_onset_laps,
          avg(cs.compound_cliff_severity)   AS compound_cliff_severity
        FROM dim_compounds_season cs
        JOIN keys k ON cs.circuit_key = k.circuit_key
        WHERE cs.compound_code = ? AND ${seasonPredicate}
      )
      SELECT
        ? AS compound,
        cmp.compound_grip_peak, cmp.compound_wear_gradient,
        cmp.compound_optimal_temp_low, cmp.compound_optimal_temp_high,
        cmp.compound_cliff_onset_laps, cmp.compound_cliff_severity,
        circ.weight_penalty_factor, circ.fuel_consumption_rate_kg_per_lap,
        circ.track_energy_index, circ.abrasiveness_index
      FROM circ, cmp
    `, [circuitId, circuitId, compound, compound])
  }
)

/** Historical stint envelope for a circuit/era/compound, with a compound='_all' fallback. */
export const queryHistoryEnvelope = registerQuery<
  { circuitId: string; era: string; compound: string },
  HistoryEnvelopeRow[]
>(
  'degradation-simulator.history-envelope',
  async ({ circuitId, era, compound }) => {
    await registerDims()
    return rawQuery<HistoryEnvelopeRow>(`
      WITH picked AS (
        SELECT *,
          CASE WHEN compound = ? THEN 0 ELSE 1 END AS fallback_rank
        FROM mart_degradation_history_envelope
        WHERE circuit_id = ? AND era = ? AND compound IN (?, '_all')
      ),
      best AS (
        SELECT min(fallback_rank) AS r FROM picked
      )
      SELECT
        lap_in_stint, n_observations, ref_green_pace_s,
        obs_fuel_removed_pace_p10_s, obs_fuel_removed_pace_p50_s, obs_fuel_removed_pace_p90_s,
        obs_deg_from_fresh_p10_s, obs_deg_from_fresh_p50_s, obs_deg_from_fresh_p90_s,
        obs_deg_from_fresh_p10_mono_s, obs_deg_from_fresh_p50_mono_s, obs_deg_from_fresh_p90_mono_s,
        COALESCE(dirty_air_deg_mult, 1.0)      AS dirty_air_deg_mult,
        COALESCE(temp_headroom_c, 8.0)         AS temp_headroom_c,
        COALESCE(temp_penalty_s_per_deg, 0.01) AS temp_penalty_s_per_deg
      FROM picked, best
      WHERE picked.fallback_rank = best.r
      ORDER BY lap_in_stint
    `, [compound, circuitId, era, compound])
  }
)

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
        dc.circuit_id,
        TRY_CAST(SPLIT_PART(b.race_id, '_', 1) AS INTEGER) AS season,
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
        event_flag_any, anomaly_class,
        n_gear_changes, mean_rpm, max_rpm, pct_full_throttle, pct_drs_active, short_shift_index,
        mid_corner_speed_loss_kph, traction_wheelspin_proxy, throttle_trace_decay,
        braking_point_drift_m, lift_coast_share,
        next_lap_degradation_jump_s
      FROM ${view}
      WHERE stint_id = ?
      ORDER BY lap_in_stint
    `, [stintId])
  }
)
