// Pure shaping of the ONNX layer's per-lap predictions into the simulator's three views:
//   1. the quantile fan (predicted next-lap degradation jump p10/p50/p90 across the stint)
//   2. the cliff-class probability bars at the current lap
//   3. the remaining-stint-life gauge at the current lap
// Plus the SimulatorInputs <- real-stint derivation and the CSV export. No ONNX, no DB, no React
// here, so the analytical logic is unit-tested in isolation.

import type { LapPrediction } from '../../ml'
import type { FanPoint } from '../../ui/charts/QuantileFanChart'
import type { SimulatorInputs } from './inputs'
import { compoundConstants } from './inputs'
import type { StintFeatureRow } from './queries'

export interface CliffBar {
  /** Class label from manifest class_order, prettified for display. */
  label: string
  rawLabel: string
  prob: number
}

export interface SimulatorResult {
  /** One fan point per swept lap. `actual` carries the observed jump when a real stint is loaded. */
  fan: FanPoint[]
  /** Cliff-class probabilities at the current lap, sorted high to low. */
  cliffBars: CliffBar[]
  /** Argmax cliff label at the current lap. */
  cliffLabel: string
  /** Remaining stint life (laps) predicted at the current lap. */
  remainingLifeLaps: number
  /** p50 predicted jump at the current lap (headline number). */
  currentJumpP50: number
  /** Stint length swept. */
  stintLength: number
  /** The 1-based current lap the bars/gauge read. */
  currentLap: number
}

const CLIFF_LABELS: Record<string, string> = {
  '0_to_2': 'Cliff in 0-2 laps',
  '3_to_5': 'Cliff in 3-5 laps',
  '6_plus': 'Cliff in 6+ laps',
  'none_in_stint': 'No cliff this stint',
}

function prettyCliff(raw: string): string {
  return CLIFF_LABELS[raw] ?? raw
}

/**
 * Combine the swept predictions with the (optional) observed jumps into the chart model.
 * `actuals[i]` aligns with prediction i (lap i+1); pass an empty array for the slider mode.
 * `currentLap` is clamped into [1, predictions.length].
 */
export function transform(
  predictions: LapPrediction[],
  currentLap: number,
  actuals: (number | null)[] = [],
): SimulatorResult {
  const n = predictions.length
  const lap = Math.min(Math.max(1, Math.round(currentLap)), Math.max(1, n))

  const fan: FanPoint[] = predictions.map((p, i) => {
    const actual = actuals[i]
    return {
      x: i + 1,
      p10: p.degradation_jump_p10_s,
      p50: p.degradation_jump_s,
      p90: p.degradation_jump_p90_s,
      ...(actual !== null && actual !== undefined ? { actual } : {}),
    }
  })

  const current = predictions[lap - 1]
  const cliffBars: CliffBar[] = current
    ? Object.entries(current.cliff.probabilities)
        .map(([rawLabel, prob]) => ({ rawLabel, label: prettyCliff(rawLabel), prob }))
        .sort((a, b) => b.prob - a.prob)
    : []

  return {
    fan,
    cliffBars,
    cliffLabel: current ? prettyCliff(current.cliff.label) : '',
    remainingLifeLaps: current ? current.remaining_stint_life_laps : 0,
    currentJumpP50: current ? current.degradation_jump_s : 0,
    stintLength: n,
    currentLap: lap,
  }
}

export function toCsvRows(result: SimulatorResult): Record<string, unknown>[] {
  return result.fan.map(p => ({
    lap_in_stint: p.x,
    predicted_jump_p10_s: p.p10.toFixed(4),
    predicted_jump_p50_s: p.p50.toFixed(4),
    predicted_jump_p90_s: p.p90.toFixed(4),
    observed_jump_s: p.actual !== undefined ? p.actual.toFixed(4) : '',
  }))
}

/**
 * Derive a full SimulatorInputs from a loaded real stint: take the static / context features from
 * the first lap, the compound constants from the row (falling back to the per-compound defaults
 * for any NULL), and the stint length from the row count. The result drives both the sliders
 * (so the user can perturb a real baseline) and the sweep.
 */
export function inputsFromStint(rows: StintFeatureRow[]): SimulatorInputs | null {
  if (!rows.length) return null
  const first = rows[0]
  const defaults = compoundConstants(first.compound)
  // DuckDB-Wasm may return numerics as bigint / Decimal-like; coerce to a plain finite number,
  // falling back to the default when NULL or unparseable. The swept rows do arithmetic on these.
  const num = (v: number | null, d: number) => {
    if (v === null || v === undefined) return d
    const n = Number(v)
    return Number.isFinite(n) ? n : d
  }

  return {
    stint_length: rows.length,
    current_lap: Math.min(Math.ceil(rows.length / 2), rows.length),
    lap_number: num(first.lap_number, 15),
    fuel_mass_kg: num(first.fuel_mass_kg, 60),
    dirty_air_share_lap: num(first.dirty_air_share_lap, 0),
    air_state_dominant: first.air_state_dominant ?? 'free_air',
    ambient_temp_delta: num(first.ambient_temp_delta, 0),
    is_rain_lap: first.is_rain_lap ?? false,
    track_energy_index: num(first.track_energy_index, 80),
    circuit_abrasiveness_index: num(first.circuit_abrasiveness_index, 3),
    constructor_id: first.constructor_id,
    constants: {
      compound: first.compound,
      compound_grip_peak: num(first.compound_grip_peak, defaults.compound_grip_peak),
      compound_wear_gradient: num(first.compound_wear_gradient, defaults.compound_wear_gradient),
      compound_optimal_temp_low: num(first.compound_optimal_temp_low, defaults.compound_optimal_temp_low),
      compound_optimal_temp_high: num(first.compound_optimal_temp_high, defaults.compound_optimal_temp_high),
      compound_cliff_onset_laps: num(first.compound_cliff_onset_laps, defaults.compound_cliff_onset_laps),
      compound_cliff_severity: num(first.compound_cliff_severity, defaults.compound_cliff_severity),
      expected_compound_pace_s: num(first.expected_compound_pace_s, defaults.expected_compound_pace_s),
      expected_degradation_rate_s_per_lap: num(
        first.expected_degradation_rate_s_per_lap, defaults.expected_degradation_rate_s_per_lap,
      ),
    },
  }
}

/**
 * The observed-jump series aligned to lap_in_stint 1..N (for the fan's `actual` overlay).
 * DuckDB-Wasm can hand back numerics as bigint / Decimal-like objects, so coerce to a plain
 * JS number (NULL / non-finite -> null)-the chart formatters call .toFixed() on these.
 */
export function observedJumps(rows: StintFeatureRow[]): (number | null)[] {
  return rows.map(r => {
    if (r.next_lap_degradation_jump_s === null || r.next_lap_degradation_jump_s === undefined) return null
    const n = Number(r.next_lap_degradation_jump_s)
    return Number.isFinite(n) ? n : null
  })
}
