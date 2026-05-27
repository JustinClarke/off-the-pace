// Pure shaping of the ONNX layer's per-lap predictions into the simulator's three views:
//   1. the quantile fan (predicted next-lap degradation jump p10/p50/p90 across the stint)
//   2. the cliff-class probability bars at the current lap
//   3. the remaining-stint-life gauge at the current lap
// Plus the SimulatorInputs <- real-stint derivation and the CSV export. No ONNX, no DB, no React
// here, so the analytical logic is unit-tested in isolation.

import type { LapPrediction } from '../../ml'
import type { FanPoint } from '../../ui/charts/QuantileFanChart'
import type { SimulatorInputs } from './inputs'
import {
  compoundConstants,
  DEFAULT_FUEL_CONSUMPTION_RATE,
  DEFAULT_WEIGHT_PENALTY_FACTOR,
} from './inputs'
import type { StintFeatureRow, HistoryEnvelopeRow } from './queries'

/** Inputs the recomposition needs beyond the ONNX jumps all already in the app's data. */
export interface RecomposeOptions {
  /** Per-circuit/era/compound fuel-removed fresh-tyre anchor (s). */
  refGreenPaceS: number
  /** The user's Fuel slider value (start-of-stint fuel mass, kg). */
  fuelStartKg: number
  /** Circuit fuel burn (kg/lap) for the deterministic fuel trajectory. */
  fuelConsumptionRateKgPerLap: number
  /** Circuit weight penalty (s/kg). */
  weightPenaltyFactor: number
  /** Historical envelope rows keyed by lap_in_stint (required for isotonic headline). */
  history?: HistoryEnvelopeRow[]
  /** User-facing dirty-air share [0..1]; > 0 activates the dirty-air bump. */
  dirtyAirShare?: number
  /** User-facing ambient temp delta above circuit typical (°C); activates the temp penalty when past headroom. */
  ambientTempDelta?: number
  /** Per-compound analytical deg rate (s/lap) fallback when no history is available. */
  analyticalDegRatePerLap?: number
}

/** One lap of the absolute-lap-time recomposition (Net = ref + fuel + tyre). */
export interface LaptimePoint {
  x: number          // lap_in_stint (1-based)
  net: number        // absolute projected lap time (s)
  ref: number        // historical fresh-tyre anchor (s)
  fuel: number       // deterministic fuel component at this lap (s)
  tyre: number       // cumulative tyre degradation from fresh (s)
  p10: number        // net − model band
  p90: number        // net + model band
}

/** One lap of the historical envelope, lifted onto the absolute axis (fuel re-added). */
export interface HistoryBandPoint {
  x: number
  p10: number
  p50: number
  p90: number
  obs?: number       // observed median absolute pace (alias of p50, for tooltips/overlay)
}

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
  /** Absolute lap-time recomposition per lap (empty when no recompose options supplied). */
  laptimeCurve: LaptimePoint[]
  /** Historical envelope on the absolute axis, aligned by lap_in_stint (empty if no history). */
  historyBand: HistoryBandPoint[]
  /** Absolute projected lap time at the current lap (the new headline). 0 when not recomposed. */
  currentLapTime: number
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
  recompose?: RecomposeOptions,
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

  const { laptimeCurve, historyBand } = recompose
    ? recomposeLapTimes(predictions, recompose)
    : { laptimeCurve: [] as LaptimePoint[], historyBand: [] as HistoryBandPoint[] }

  const currentLapTime = laptimeCurve[lap - 1]?.net ?? 0

  return {
    fan,
    cliffBars,
    cliffLabel: current ? prettyCliff(current.cliff.label) : '',
    remainingLifeLaps: current ? current.remaining_stint_life_laps : 0,
    currentJumpP50: current ? current.degradation_jump_s : 0,
    stintLength: n,
    currentLap: lap,
    laptimeCurve,
    historyBand,
    currentLapTime,
  }
}

/**
 * Physical recomposition: read the isotonic-fitted monotone degradation from the history
 * envelope, scale it by the physics modulation factor M (dirty-air bump + temp-window penalty),
 * add the deterministic fuel component, and anchor to the historical fresh-tyre pace.
 *
 * Formula:
 *   M(k) = clamp(1 + air_bump·𝟙[dirty_air] + temp_penalty·max(0, temp_delta−headroom), 1.0, 1.5)
 *   tyre(k) = mono_p50(k) × M    [monotone by construction; running-max guard as belt+suspenders]
 *   net(k)  = ref + fuel(k) + tyre(k)
 *   band(k) = ref + fuel(k) + mono_{p10,p90}(k) × M
 *
 * Empty-history guard: if no fitted history is available (even after the _all fallback), falls
 * back to the analytical ramp: tyre = max(0, analyticalDegRatePerLap × (k-1)) × M.
 *
 * The ONNX jump predictions are still used for the fan / cliff bars / stint-life gauge panels;
 * this function only drives the absolute-lap-time headline and band.
 */
export function recomposeLapTimes(
  predictions: LapPrediction[],
  opts: RecomposeOptions,
): { laptimeCurve: LaptimePoint[]; historyBand: HistoryBandPoint[] } {
  const rate = opts.fuelConsumptionRateKgPerLap || DEFAULT_FUEL_CONSUMPTION_RATE
  const histByLap = new Map<number, HistoryEnvelopeRow>()
  for (const h of opts.history ?? []) histByLap.set(h.lap_in_stint, h)

  // Read modulation coefficients from the first history row (constant within a cell).
  const firstHist = opts.history?.[0]
  const dirtyAirMult   = firstHist?.dirty_air_deg_mult    ?? 1.0
  const tempHeadroom   = firstHist?.temp_headroom_c       ?? 8.0
  const tempPenaltyPer = firstHist?.temp_penalty_s_per_deg ?? 0.01

  // Compute M constant across the stint (the isotonic curve, not M, varies per lap).
  const dirtyAirShare = opts.dirtyAirShare ?? 0
  const tempDelta     = opts.ambientTempDelta ?? 0
  const airBump  = dirtyAirShare > 0 ? (dirtyAirMult - 1) : 0
  const tempBump = tempPenaltyPer * Math.max(0, tempDelta - tempHeadroom)
  const M = Math.min(1.5, Math.max(1.0, 1 + airBump + tempBump))

  const hasFittedHistory = [...histByLap.values()].some(
    h => h.obs_deg_from_fresh_p50_mono_s !== null && h.obs_deg_from_fresh_p50_mono_s !== undefined
  )
  const analyticalRate = opts.analyticalDegRatePerLap ?? 0

  const laptimeCurve: LaptimePoint[] = []
  const historyBand:  HistoryBandPoint[] = []
  let prevTyre = -Infinity // running-max guard: belt-and-suspenders monotonicity

  for (let i = 0; i < predictions.length; i++) {
    const k = i + 1
    const fuelMass = Math.max(0, opts.fuelStartKg - rate * (k - 1))
    const fuel = opts.weightPenaltyFactor * fuelMass

    const h = histByLap.get(k)
    let rawTyre: number
    if (hasFittedHistory && h?.obs_deg_from_fresh_p50_mono_s != null) {
      // Modulation only amplifies positive degradation multiplying a negative base by M > 1
      // would worsen it (drying track appears faster → more credit), which is unphysical.
      const base = h.obs_deg_from_fresh_p50_mono_s
      rawTyre = base >= 0 ? base * M : base
    } else {
      // Empty-history fallback: analytical ramp (0 on lap 1, linear from lap 2 onward).
      rawTyre = Math.max(0, analyticalRate * (k - 1)) * M
    }
    // Running-max guard: enforce tyre is non-decreasing even if the fit has a plateau issue.
    const tyre = Math.max(prevTyre, rawTyre)
    prevTyre = tyre

    const net = opts.refGreenPaceS + fuel + tyre

    // Band edges: use fitted p10/p90 × M; fall back to analytical ramp ± small fraction.
    let p10Net: number
    let p90Net: number
    if (hasFittedHistory && h?.obs_deg_from_fresh_p10_mono_s != null && h?.obs_deg_from_fresh_p90_mono_s != null) {
      const b10 = h.obs_deg_from_fresh_p10_mono_s
      const b90 = h.obs_deg_from_fresh_p90_mono_s
      p10Net = opts.refGreenPaceS + fuel + (b10 >= 0 ? b10 * M : b10)
      p90Net = opts.refGreenPaceS + fuel + (b90 >= 0 ? b90 * M : b90)
    } else {
      p10Net = net - tyre * 0.2
      p90Net = net + tyre * 0.5
    }

    laptimeCurve.push({ x: k, net, ref: opts.refGreenPaceS, fuel, tyre, p10: p10Net, p90: p90Net })

    if (h) {
      historyBand.push({
        x: k,
        p10: h.obs_fuel_removed_pace_p10_s + fuel,
        p50: h.obs_fuel_removed_pace_p50_s + fuel,
        p90: h.obs_fuel_removed_pace_p90_s + fuel,
        obs: h.obs_fuel_removed_pace_p50_s + fuel,
      })
    }
  }

  return { laptimeCurve, historyBand }
}

export function toCsvRows(result: SimulatorResult): Record<string, unknown>[] {
  const lt = new Map(result.laptimeCurve.map(p => [p.x, p]))
  return result.fan.map(p => {
    const k = p.x as number
    const l = lt.get(k)
    return {
      lap_in_stint: p.x,
      predicted_jump_p10_s: p.p10.toFixed(4),
      predicted_jump_p50_s: p.p50.toFixed(4),
      predicted_jump_p90_s: p.p90.toFixed(4),
      observed_jump_s: p.actual !== undefined ? p.actual.toFixed(4) : '',
      projected_lap_time_s: l ? l.net.toFixed(4) : '',
      ref_green_pace_s: l ? l.ref.toFixed(4) : '',
      fuel_component_s: l ? l.fuel.toFixed(4) : '',
      tyre_component_s: l ? l.tyre.toFixed(4) : '',
      projected_lap_time_p10_s: l ? l.p10.toFixed(4) : '',
      projected_lap_time_p90_s: l ? l.p90.toFixed(4) : '',
    }
  })
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
    // Circuit context is enriched by the page from the loaded stint's circuit; defaults here.
    circuit_id: null,
    circuit_name: '',
    era: 'post2022',
    weight_penalty_factor: DEFAULT_WEIGHT_PENALTY_FACTOR,
    fuel_consumption_rate_kg_per_lap: DEFAULT_FUEL_CONSUMPTION_RATE,
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
