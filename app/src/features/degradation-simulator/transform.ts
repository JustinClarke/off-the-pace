// The simulator's absolute lap-time headline + the ONNX-derived panels.
//
// The headline is a coherent physical lap-time curve, DECOUPLED from ONNX, built over stint_length:
//
//   net(k) = base + fuel(k) + tyre(k)
//   base     = ref_green_pace + constructor_offset + per-lap conditions cost (air-state, rain) 
//              constant across the stint, so it shifts the whole curve.
//   fuel(k)  = weight_penalty × max(0, fuel_start − burn × (k−1))
//   tyre(k)  = working_deg(k) × track_scale × M + cliff_term(k)        [running-max → monotone]
//     working_deg(k) = obs_deg_from_fresh_p50_mono_s(k)  (isotonic; held flat past the observed range)
//     M              = clamp(1 + dirty_air_bump × dirty_air_share + temp_penalty × max(0, Δtemp −
//                      headroom), 1, 1.5) the degradation multiplier (mirrors the envelope mart /
//                      fit_degradation_isotonic). Dirty air and ambient heat ACCELERATE wear, so they
//                      scale the tyre term (it responds at EVERY lap) rather than shifting base pace;
//                      M = 1 at neutral inputs, recovering the pure observed working window.
//     cliff_term(k)  = CLIFF_GAIN × severity × max(0, k − onset_eff)^CLIFF_EXP   (0 pre-onset, C¹ join)
//     onset_eff      = clamp(cliff_onset − temp_bringfwd − dirtyair_bringfwd − abras_bringfwd, …)
//
// The working window (k ≤ onset_eff) is pure observed isotonic data honest. The cliff
// (k > onset_eff) is a convex extrapolation from the FITTED per-compound severity: the
// user-approved departure from "faithful-to-observed-only" that gives the headline a visible cliff
// overwhelming fuel burn-off late-stint. The headline NEVER depends on the ONNX jumps those drive
// only the fan / cliff-risk bars / remaining-life gauge. No ONNX, no DB, no React here.

import type { LapPrediction } from '../../ml'
import type { FanPoint } from '../../ui/charts/QuantileFanChart'
import type { SimulatorInputs } from './inputs'
import {
  compoundConstants,
  DEFAULT_FUEL_CONSUMPTION_RATE,
  DEFAULT_WEIGHT_PENALTY_FACTOR,
} from './inputs'
import type { StintFeatureRow, HistoryEnvelopeRow } from './queries'

// ── Physical recomposition constants (mirror fit_degradation_isotonic.py where noted) ──────────
// Cliff extrapolation past the survivor-collapsed observed window: convex acceleration scaled by
// the fitted per-compound severity. Calibrated so a HARD severity 0.82 gives
// onset+4 ≈ 0.5s, onset+8 ≈ 1.5s, onset+12 ≈ 2.8s believable and compound-ordered (a SOFT, sev
// ~1.28, reaches ~2.3s by onset+8, earlier and harder). Term and slope are both 0 at k = onset, so
// the join into the observed working window is C¹-continuous (no kink).
const CLIFF_GAIN = 0.08
const CLIFF_EXP = 1.5
// The fitted params are noisy in thin-data cells (severity spans ~0.4–3.3, onset ~6–50), so clamp.
const CLIFF_SEVERITY_MIN = 0.6
const CLIFF_SEVERITY_MAX = 1.6
const CLIFF_ONSET_MIN = 6
const CLIFF_ONSET_MAX = 40
const CLIFF_ONSET_DEFAULT = 22
// Dirty-air, overheating and abrasiveness bring the cliff forward (faster wear → earlier onset).
const DIRTY_AIR_BRINGFWD_LAPS = 6          // at share = 1.0, onset moves forward this many laps
const TEMP_BRINGFWD_LAPS_PER_DEG = 0.2     // per °C past the compound headroom
const ABRAS_BRINGFWD_LAPS_PER_INDEX = 1.5  // per abrasiveness index above the reference
// Per-lap pace costs folded into the anchor (constant across the stint → shift the whole curve).
// Dirty air and temperature are deliberately NOT here they accelerate tyre wear via the
// degradation multiplier M below, not as a flat pace shift (so the tyre readout actually responds).
const RAIN_LAP_PACE_S = 1.5
const AIR_STATE_PACE_S: Record<string, number> = {
  free_air: 0, dirty_air: 0.15, drs_train: 0.08, tow_zone: -0.05,
}
// Degradation multiplier M. The fitted per-cell dirty_air_deg_mult ∈ [1.0, 1.15] is exactly 1.0
// wherever the fit's significance gate failed (thin data), which would leave the dirty-air slider
// inert there so floor the full-share bump so dirty air always bites at least this much (the same
// "never inert" guarantee the air-state / constructor hooks use). M is clamped to the fit's [1, 1.5].
const DIRTY_AIR_DEG_BUMP_FLOOR = 0.08      // ≥ +8% deg at full dirty air, even in unfitted cells
const DEG_MULT_MAX = 1.5
// Abrasiveness (slider 2..4) scales cliff severity around the index-3 reference.
const ABRASIVENESS_REF = 3
const ABRASIVENESS_GAIN = 0.15             // ±1 index → ±15% severity
// Track energy index scales the working-window deg rate around the field reference (harder → more).
const TRACK_ENERGY_REF = 80
const TRACK_ENERGY_GAIN = 0.006            // per unit above/below the reference
const TRACK_SCALE_MIN = 0.5

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

/** Inputs the recomposition needs all already in the app's published data + the slider state. */
export interface RecomposeOptions {
  /** Per-circuit/era/compound fuel-removed fresh-tyre anchor (s). 0 for a generic (relative) curve. */
  refGreenPaceS: number
  /** Number of laps to sweep (lap_in_stint = 1..stintLength). Decoupled from the ONNX output length. */
  stintLength: number
  /** The user's Fuel slider value (start-of-stint fuel mass, kg). */
  fuelStartKg: number
  /** Circuit fuel burn (kg/lap) for the deterministic fuel trajectory. */
  fuelConsumptionRateKgPerLap: number
  /** Circuit weight penalty (s/kg). */
  weightPenaltyFactor: number
  /** Historical envelope rows keyed by lap_in_stint (drives the isotonic working window + band). */
  history?: HistoryEnvelopeRow[]
  /** User-facing dirty-air share [0..1]; adds a per-lap pace cost and brings the cliff forward. */
  dirtyAirShare?: number
  /** User-facing ambient temp delta above circuit typical (°C); penalty + cliff bring-forward past headroom. */
  ambientTempDelta?: number
  /** Per-compound analytical deg rate (s/lap) fallback when no history is available. */
  analyticalDegRatePerLap?: number
  /** Fitted compound cliff onset (laps). Enables the cliff extrapolation when set with cliffSeverity. */
  cliffOnsetLaps?: number
  /** Fitted compound cliff severity. The cliff term is inactive (0) unless this is provided. */
  cliffSeverity?: number
  /** Circuit abrasiveness index (slider 2..4); scales cliff severity and brings the onset forward. */
  abrasivenessIndex?: number
  /** Track energy index; scales the working-window degradation rate. */
  trackEnergyIndex?: number
  /** Dominant air state; baseline per-lap pace cost so the control is never inert on the headline. */
  airState?: string
  /** Rain lap flag; flat wet-pace penalty on the curve. */
  isRainLap?: boolean
  /** Constructor pace offset (s) applied to the anchor so Constructor moves the headline. */
  constructorPaceOffsetS?: number
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
  /** AFT log-normal median remaining stint life (laps) at the current lap. */
  remainingLifeLaps: number
  /** 10th/90th percentile of the same fitted distribution. The gauge renders the
   *  median against this band because remaining life is censored on 46% of the
   *  training rows -- a lone number to one decimal claims more than the fit has. */
  remainingLifeP10: number
  remainingLifeP90: number
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
  /** Effective cliff-onset lap from the physical model (0 when the cliff term is inactive). */
  cliffOnsetLap: number
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
  // The headline curve is built from `recompose` alone independent of the ONNX output so the
  // marker/length must follow whichever is longer (ONNX may be slow, failed, or 404).
  const { laptimeCurve, historyBand, cliffOnsetLap } = recompose
    ? recomposeLapTimes(recompose)
    : { laptimeCurve: [] as LaptimePoint[], historyBand: [] as HistoryBandPoint[], cliffOnsetLap: 0 }

  const n = Math.max(predictions.length, laptimeCurve.length)
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

  const currentLapTime = laptimeCurve[lap - 1]?.net ?? 0

  return {
    fan,
    cliffBars,
    cliffLabel: current ? prettyCliff(current.cliff.label) : '',
    remainingLifeLaps: current ? current.remaining_stint_life_laps : 0,
    remainingLifeP10: current ? current.remaining_stint_life_p10_laps : 0,
    remainingLifeP90: current ? current.remaining_stint_life_p90_laps : 0,
    currentJumpP50: current ? current.degradation_jump_s : 0,
    stintLength: n,
    currentLap: lap,
    laptimeCurve,
    historyBand,
    currentLapTime,
    cliffOnsetLap,
  }
}

/**
 * Physical recomposition (decoupled from ONNX): build the absolute lap-time curve from the
 * fitted observed degradation, a deterministic fuel term, a fitted cliff extrapolation, and the
 * conditions/constructor pace costs. See the formula block at the top of this file.
 *
 * Monotonicity of the tyre term is structural: working_deg is isotonic-fitted (held flat past the
 * observed range), track_scale ≥ 0 is constant, and the cliff term is 0 pre-onset then strictly
 * increasing a running-max guard backstops any plateau noise. The cliff term is INACTIVE unless
 * `cliffSeverity` is supplied, so the pure-observed working window is recovered when it is omitted.
 *
 * Empty-history guard: with no fitted history, falls back to the analytical ramp
 * working_deg = max(0, analyticalDegRatePerLap × (k−1)) so the curve still renders and responds.
 */
export function recomposeLapTimes(
  opts: RecomposeOptions,
): { laptimeCurve: LaptimePoint[]; historyBand: HistoryBandPoint[]; cliffOnsetLap: number } {
  const rate = opts.fuelConsumptionRateKgPerLap || DEFAULT_FUEL_CONSUMPTION_RATE
  const histByLap = new Map<number, HistoryEnvelopeRow>()
  for (const h of opts.history ?? []) histByLap.set(h.lap_in_stint, h)

  // Conditions coefficients from the first history row (constant within a cell).
  const firstHist = opts.history?.[0]
  const tempHeadroom   = firstHist?.temp_headroom_c       ?? 8.0
  const tempPenaltyPer = firstHist?.temp_penalty_s_per_deg ?? 0.01

  const dirtyAirShare = clamp(opts.dirtyAirShare ?? 0, 0, 1)
  const tempExcess    = Math.max(0, (opts.ambientTempDelta ?? 0) - tempHeadroom)

  // Degradation multiplier M: dirty air and ambient heat accelerate wear, so they scale the tyre
  // term (responds at every lap) rather than the base pace. dirty_air_bump = fitted per-cell mult − 1,
  // floored so the slider is never inert where the fit found no signal; temp adds a fractional bump
  // per °C past the compound's headroom (note temp_penalty_s_per_deg is a fractional bump, not seconds,
  // per fit_degradation_isotonic). Clamped to the fit's [1, 1.5]. At share 0 / Δtemp ≤ headroom, M = 1,
  // recovering the pure observed working window so neutral-input faithfulness (MAE gate) is preserved.
  const dirtyAirBump = Math.max((firstHist?.dirty_air_deg_mult ?? 1.0) - 1, DIRTY_AIR_DEG_BUMP_FLOOR)
  const degMult = clamp(
    1 + dirtyAirBump * dirtyAirShare + tempPenaltyPer * tempExcess,
    1, DEG_MULT_MAX,
  )

  // Per-lap pace cost folded into the anchor so anchor + fuel + tyre = net exactly. Only air-state and
  // rain are genuine pace shifts; dirty air and temp act through M above (on the tyre term).
  const conditionsCost =
    (AIR_STATE_PACE_S[opts.airState ?? 'free_air'] ?? 0) +
    (opts.isRainLap ? RAIN_LAP_PACE_S : 0)
  const adjustedBase = opts.refGreenPaceS + (opts.constructorPaceOffsetS ?? 0) + conditionsCost

  // Track energy scales the working-window degradation rate (harder track → more deg).
  const trackScale = Math.max(
    TRACK_SCALE_MIN,
    1 + TRACK_ENERGY_GAIN * ((opts.trackEnergyIndex ?? TRACK_ENERGY_REF) - TRACK_ENERGY_REF),
  )

  // Cliff extrapolation parameters. Active only when a fitted severity is supplied.
  const cliffActive = opts.cliffSeverity != null
  const abras = opts.abrasivenessIndex ?? ABRASIVENESS_REF
  const abrasScale = 1 + ABRASIVENESS_GAIN * (abras - ABRASIVENESS_REF)
  const severity = clamp((opts.cliffSeverity ?? 0) * abrasScale, CLIFF_SEVERITY_MIN, CLIFF_SEVERITY_MAX)
  const onsetEff = cliffActive
    ? clamp(
        (opts.cliffOnsetLaps ?? CLIFF_ONSET_DEFAULT) -
          TEMP_BRINGFWD_LAPS_PER_DEG * tempExcess -
          DIRTY_AIR_BRINGFWD_LAPS * dirtyAirShare -
          ABRAS_BRINGFWD_LAPS_PER_INDEX * (abras - ABRASIVENESS_REF),
        CLIFF_ONSET_MIN, CLIFF_ONSET_MAX,
      )
    : 0
  const cliffTerm = (k: number) =>
    cliffActive ? CLIFF_GAIN * severity * Math.pow(Math.max(0, k - onsetEff), CLIFF_EXP) : 0

  const hasFittedHistory = [...histByLap.values()].some(
    h => h.obs_deg_from_fresh_p50_mono_s !== null && h.obs_deg_from_fresh_p50_mono_s !== undefined
  )
  const analyticalRate = opts.analyticalDegRatePerLap ?? 0

  const laptimeCurve: LaptimePoint[] = []
  const historyBand:  HistoryBandPoint[] = []
  let prevTyre = -Infinity // running-max guard: belt-and-suspenders monotonicity
  // The observed working window is held flat past the last fitted lap; the cliff term supplies the rise.
  let lastWork = 0, lastWork10 = 0, lastWork90 = 0

  const stintLength = Math.max(0, Math.round(opts.stintLength))
  for (let k = 1; k <= stintLength; k++) {
    const fuelMass = Math.max(0, opts.fuelStartKg - rate * (k - 1))
    const fuel = opts.weightPenaltyFactor * fuelMass

    const h = histByLap.get(k)
    // working_deg(k): observed isotonic p50 (× track scale), held flat past the observed range.
    let work: number, work10: number, work90: number
    if (hasFittedHistory && h?.obs_deg_from_fresh_p50_mono_s != null) {
      lastWork   = h.obs_deg_from_fresh_p50_mono_s
      lastWork10 = h.obs_deg_from_fresh_p10_mono_s ?? lastWork - 0.3
      lastWork90 = h.obs_deg_from_fresh_p90_mono_s ?? lastWork + 0.5
      work = lastWork; work10 = lastWork10; work90 = lastWork90
    } else if (hasFittedHistory) {
      work = lastWork; work10 = lastWork10; work90 = lastWork90 // clip flat past observed range
    } else {
      work = Math.max(0, analyticalRate * (k - 1)) // empty-history fallback ramp
      work10 = work; work90 = work
    }
    // Track energy + the degradation multiplier scale the (positive) working-window deg; a negative
    // (drying) base is never amplified.
    const scale = (v: number) => (v >= 0 ? v * trackScale * degMult : v)

    const cliff = cliffTerm(k)
    const rawTyre = scale(work) + cliff
    const tyre = Math.max(prevTyre, rawTyre)
    prevTyre = tyre

    const net = adjustedBase + fuel + tyre

    // Band edges share the same cliff term (central extrapolation) so the band rises with it.
    let p10Net: number, p90Net: number
    if (hasFittedHistory) {
      p10Net = adjustedBase + fuel + scale(work10) + cliff
      p90Net = adjustedBase + fuel + scale(work90) + cliff
    } else {
      p10Net = net - tyre * 0.2
      p90Net = net + tyre * 0.5
    }

    laptimeCurve.push({ x: k, net, ref: adjustedBase, fuel, tyre, p10: p10Net, p90: p90Net })

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

  return { laptimeCurve, historyBand, cliffOnsetLap: onsetEff }
}

export function toCsvRows(result: SimulatorResult): Record<string, unknown>[] {
  // Key on the headline curve (always present) and merge the ONNX fan by lap when available, so the
  // export reflects the projected lap time even if the trained models are offline.
  const fanByLap = new Map(result.fan.map(p => [p.x as number, p]))
  const rows = result.laptimeCurve.length ? result.laptimeCurve : result.fan.map(p => ({ x: p.x } as LaptimePoint))
  return rows.map(l => {
    const f = fanByLap.get(l.x)
    return {
      lap_in_stint: l.x,
      predicted_jump_p10_s: f ? f.p10.toFixed(4) : '',
      predicted_jump_p50_s: f ? f.p50.toFixed(4) : '',
      predicted_jump_p90_s: f ? f.p90.toFixed(4) : '',
      observed_jump_s: f?.actual !== undefined ? f.actual.toFixed(4) : '',
      projected_lap_time_s: result.laptimeCurve.length ? l.net.toFixed(4) : '',
      ref_green_pace_s: result.laptimeCurve.length ? l.ref.toFixed(4) : '',
      fuel_component_s: result.laptimeCurve.length ? l.fuel.toFixed(4) : '',
      tyre_component_s: result.laptimeCurve.length ? l.tyre.toFixed(4) : '',
      projected_lap_time_p10_s: result.laptimeCurve.length ? l.p10.toFixed(4) : '',
      projected_lap_time_p90_s: result.laptimeCurve.length ? l.p90.toFixed(4) : '',
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
