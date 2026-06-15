import { describe, it, expect } from 'vitest'
import { transform, toCsvRows, inputsFromStint, observedJumps, recomposeLapTimes } from './transform'
import type { RecomposeOptions } from './transform'
import { buildStintRows, DEFAULT_INPUTS } from './inputs'
import type { LapPrediction } from '../../ml'
import type { StintFeatureRow, HistoryEnvelopeRow } from './queries'
import { projectedDegMAE, monotoneViolations } from './accuracy'
import type { TyrePoint } from './accuracy'
import accuracyBasket from './__fixtures__/accuracy_basket.json'

function pred(p10: number, p50: number, p90: number, life: number, probs: Record<string, number>, label: string): LapPrediction {
  return {
    degradation_jump_p10_s: p10,
    degradation_jump_s: p50,
    degradation_jump_p90_s: p90,
    remaining_stint_life_laps: life,
    cliff: { label, probabilities: probs },
  }
}

const PROBS = { '0_to_2': 0.1, '3_to_5': 0.2, '6_plus': 0.3, none_in_stint: 0.4 }

// A historical-envelope row with isotonic-fitted mono columns.
// monoP50 = the fitted (monotone) degradation from fresh at this lap.
function hRow(lap: number, monoP50: number, monoP10?: number, monoP90?: number): HistoryEnvelopeRow {
  const p10 = monoP10 ?? monoP50 - 0.3
  const p90 = monoP90 ?? monoP50 + 0.5
  const ref = 90
  return {
    lap_in_stint: lap,
    n_observations: 50,
    ref_green_pace_s: ref,
    obs_fuel_removed_pace_p10_s: ref + p10 - 0.3,
    obs_fuel_removed_pace_p50_s: ref + monoP50,
    obs_fuel_removed_pace_p90_s: ref + p90 + 0.5,
    obs_deg_from_fresh_p10_s: p10 - 0.3,
    obs_deg_from_fresh_p50_s: monoP50,
    obs_deg_from_fresh_p90_s: p90 + 0.5,
    obs_deg_from_fresh_p10_mono_s: p10,
    obs_deg_from_fresh_p50_mono_s: monoP50,
    obs_deg_from_fresh_p90_mono_s: p90,
    dirty_air_deg_mult: 1.05,    // a cell with a mild dirty-air signal
    temp_headroom_c: 10.0,        // penalty kicks in after 10 °C delta
    temp_penalty_s_per_deg: 0.01,
  }
}

describe('transform', () => {
  const preds = [
    pred(0.1, 0.2, 0.4, 20, PROBS, 'none_in_stint'),
    pred(0.2, 0.4, 0.7, 10, PROBS, 'none_in_stint'),
    pred(0.3, 0.6, 1.0, 3, { ...PROBS, '0_to_2': 0.5, none_in_stint: 0.0 }, '0_to_2'),
  ]

  it('builds one fan point per prediction in lap order', () => {
    const r = transform(preds, 2)
    expect(r.fan).toHaveLength(3)
    expect(r.fan.map(f => f.x)).toEqual([1, 2, 3])
    expect(r.fan[0]).toMatchObject({ p10: 0.1, p50: 0.2, p90: 0.4 })
    expect(r.stintLength).toBe(3)
  })

  it('reads cliff bars and remaining life at the current lap (1-based)', () => {
    const r = transform(preds, 3)
    expect(r.currentLap).toBe(3)
    expect(r.remainingLifeLaps).toBe(3)
    expect(r.currentJumpP50).toBe(0.6)
    // bars sorted high -> low; argmax at lap 3 is 0_to_2
    expect(r.cliffBars[0].rawLabel).toBe('0_to_2')
    expect(r.cliffLabel).toBe('Cliff in 0-2 laps')
  })

  it('clamps current lap into [1, n]', () => {
    expect(transform(preds, 0).currentLap).toBe(1)
    expect(transform(preds, 99).currentLap).toBe(3)
  })

  it('overlays observed jumps when provided, omits actual otherwise', () => {
    const withActual = transform(preds, 1, [0.25, null, 0.55])
    expect(withActual.fan[0].actual).toBe(0.25)
    expect(withActual.fan[1].actual).toBeUndefined() // null -> omitted
    expect(withActual.fan[2].actual).toBe(0.55)

    const sliderMode = transform(preds, 1)
    expect(sliderMode.fan.every(f => f.actual === undefined)).toBe(true)
  })

  it('cliff bar probabilities sum to ~1 and are sorted descending', () => {
    const r = transform(preds, 1)
    const sum = r.cliffBars.reduce((s, b) => s + b.prob, 0)
    expect(sum).toBeCloseTo(1, 6)
    for (let i = 1; i < r.cliffBars.length; i++) {
      expect(r.cliffBars[i - 1].prob).toBeGreaterThanOrEqual(r.cliffBars[i].prob)
    }
  })

  it('handles an empty prediction set without throwing', () => {
    const r = transform([], 1)
    expect(r.fan).toHaveLength(0)
    expect(r.cliffBars).toHaveLength(0)
    expect(r.remainingLifeLaps).toBe(0)
  })
})

describe('recomposeLapTimes (P2.2 isotonic base × M)', () => {
  // Three laps with monotone fitted deg: 0.2, 0.5, 0.8s. Bands: p10 = mono−0.3, p90 = mono+0.5.
  // dirty_air_deg_mult=1.05, temp_headroom=10°C, temp_penalty=0.01 (from hRow defaults).
  const history: HistoryEnvelopeRow[] = [
    hRow(1, 0.2),
    hRow(2, 0.5),
    hRow(3, 0.8),
  ]
  const preds = [
    pred(0.1, 0.2, 0.4, 20, PROBS, 'none_in_stint'),
    pred(0.1, 0.2, 0.4, 15, PROBS, 'none_in_stint'),
    pred(0.1, 0.2, 0.4, 10, PROBS, 'none_in_stint'),
  ]
  const baseOpts: RecomposeOptions = {
    refGreenPaceS: 90,
    fuelStartKg: 50,
    fuelConsumptionRateKgPerLap: 2,
    weightPenaltyFactor: 0.03,
    history,
  }

  it('tyre(k) = mono_p50(k) × M at neutral inputs (M = 1)', () => {
    // No dirty air, no temp → M = 1.0 → tyre = raw mono values
    const { laptimeCurve } = recomposeLapTimes(preds, { ...baseOpts, dirtyAirShare: 0, ambientTempDelta: 0 })
    expect(laptimeCurve.map(p => +p.tyre.toFixed(4))).toEqual([0.2, 0.5, 0.8])
  })

  it('net = ref + fuel + tyre at every lap', () => {
    const { laptimeCurve } = recomposeLapTimes(preds, { ...baseOpts, dirtyAirShare: 0, ambientTempDelta: 0 })
    // fuel(k) = 0.03 × (50 - 2(k-1)) → lap 1: 1.5, lap 2: 1.44, lap 3: 1.38
    expect(laptimeCurve[0].net).toBeCloseTo(90 + 1.5  + 0.2, 6)
    expect(laptimeCurve[1].net).toBeCloseTo(90 + 1.44 + 0.5, 6)
    expect(laptimeCurve[2].net).toBeCloseTo(90 + 1.38 + 0.8, 6)
  })

  it('band edges = ref + fuel + mono_{p10,p90} × M (neutral)', () => {
    const { laptimeCurve } = recomposeLapTimes(preds, { ...baseOpts, dirtyAirShare: 0, ambientTempDelta: 0 })
    // At lap 1: mono_p10 = 0.2−0.3 = −0.1, mono_p90 = 0.2+0.5 = 0.7
    const ref = 90, fuel1 = 0.03 * 50
    expect(laptimeCurve[0].p10).toBeCloseTo(ref + fuel1 + (-0.1), 4)
    expect(laptimeCurve[0].p90).toBeCloseTo(ref + fuel1 + 0.7,    4)
  })

  it('tyre term is monotone non-decreasing (the physics gate)', () => {
    const { laptimeCurve } = recomposeLapTimes(preds, baseOpts)
    const tyres = laptimeCurve.map(p => p.tyre)
    for (let i = 1; i < tyres.length; i++) {
      expect(tyres[i]).toBeGreaterThanOrEqual(tyres[i - 1])
    }
  })

  it('dirty air → M > 1 → tyre and net increase (bounded ≤ 1.5×)', () => {
    const clean = recomposeLapTimes(preds, { ...baseOpts, dirtyAirShare: 0 }).laptimeCurve
    const dirty = recomposeLapTimes(preds, { ...baseOpts, dirtyAirShare: 0.8 }).laptimeCurve
    for (let i = 0; i < clean.length; i++) {
      expect(dirty[i].tyre).toBeGreaterThan(clean[i].tyre)
      expect(dirty[i].net).toBeGreaterThan(clean[i].net)
      // M = 1 + (1.05-1) = 1.05 → tyre = mono × 1.05 (bounded ≤ 1.5)
      expect(dirty[i].tyre).toBeLessThanOrEqual(clean[i].tyre * 1.5 + 1e-9)
    }
  })

  it('temp past headroom → M > 1 → tyre and net increase', () => {
    // headroom = 10°C; temp_delta = 20°C → penalty = 0.01 × (20−10) = 0.10 → M = 1.10
    const cool = recomposeLapTimes(preds, { ...baseOpts, ambientTempDelta: 5 }).laptimeCurve
    const hot  = recomposeLapTimes(preds, { ...baseOpts, ambientTempDelta: 20 }).laptimeCurve
    for (let i = 0; i < cool.length; i++) {
      expect(hot[i].tyre).toBeGreaterThan(cool[i].tyre)
    }
  })

  it('temp within headroom has no penalty', () => {
    const base  = recomposeLapTimes(preds, { ...baseOpts, dirtyAirShare: 0, ambientTempDelta: 0 }).laptimeCurve
    const inWin = recomposeLapTimes(preds, { ...baseOpts, dirtyAirShare: 0, ambientTempDelta: 5 }).laptimeCurve
    for (let i = 0; i < base.length; i++) {
      expect(inWin[i].tyre).toBeCloseTo(base[i].tyre, 6)
    }
  })

  it('↑ fuel ⇒ ↑ projected lap time at every lap', () => {
    const lo = recomposeLapTimes(preds, { ...baseOpts, fuelStartKg: 30 }).laptimeCurve
    const hi = recomposeLapTimes(preds, { ...baseOpts, fuelStartKg: 90 }).laptimeCurve
    for (let i = 0; i < lo.length; i++) expect(hi[i].net).toBeGreaterThan(lo[i].net)
  })

  it('historyBand lifts obs fuel-removed p50 onto the absolute axis (fuel re-added)', () => {
    // hRow(lap, mono): obs_fuel_removed_pace_p50_s = ref + mono = 90 + monoP50
    const { historyBand } = recomposeLapTimes(preds, baseOpts)
    expect(historyBand).toHaveLength(3)
    // fuel(lap 1) = 0.03*50 = 1.5; obs p50 = 90 + 0.2 = 90.2; + fuel = 91.7
    expect(historyBand[0].p50).toBeCloseTo(90 + 0.2 + 1.5, 4)
    // fuel(lap 3) = 0.03*46 = 1.38; obs p50 = 90 + 0.8 = 90.8; + fuel = 92.18
    expect(historyBand[2].p50).toBeCloseTo(90 + 0.8 + 1.38, 4)
  })

  it('empty-history guard: falls back to analytical ramp × M', () => {
    const { laptimeCurve } = recomposeLapTimes(preds, {
      ...baseOpts,
      history: [],
      analyticalDegRatePerLap: 0.06,
      dirtyAirShare: 0,
      ambientTempDelta: 0,
    })
    // lap 1: max(0, 0.06 × 0) = 0; lap 2: 0.06; lap 3: 0.12
    expect(laptimeCurve[0].tyre).toBeCloseTo(0, 6)
    expect(laptimeCurve[1].tyre).toBeCloseTo(0.06, 6)
    expect(laptimeCurve[2].tyre).toBeCloseTo(0.12, 6)
  })
})

describe('toCsvRows', () => {
  it('emits one row per fan point with blank actual in slider mode', () => {
    const r = transform([pred(0.1, 0.2, 0.4, 20, PROBS, 'none_in_stint')], 1)
    const csv = toCsvRows(r)
    expect(csv).toHaveLength(1)
    expect(csv[0]).toMatchObject({ lap_in_stint: 1, observed_jump_s: '' })
  })
})

describe('buildStintRows', () => {
  it('produces one FeatureRow per lap with derived cliff state', () => {
    const rows = buildStintRows({ ...DEFAULT_INPUTS, stint_length: 25 })
    expect(rows).toHaveLength(25)
    expect(rows[0].lap_in_stint).toBe(1)
    expect(rows[24].lap_in_stint).toBe(25)
    // MEDIUM cliff onset default is 20 -> lap 25 is past the cliff
    expect(rows[24].cliff_onset_passed).toBe(true)
    expect(rows[24].laps_past_cliff).toBe(5)
    // early lap not past cliff
    expect(rows[0].cliff_onset_passed).toBe(false)
    expect(rows[0].laps_past_cliff).toBe(0)
  })

  it('burns fuel monotonically and never below 1 kg', () => {
    const rows = buildStintRows({ ...DEFAULT_INPUTS, stint_length: 50, fuel_mass_kg: 60 })
    const fuels = rows.map(r => r.fuel_mass_kg as number)
    for (let i = 1; i < fuels.length; i++) expect(fuels[i]).toBeLessThanOrEqual(fuels[i - 1])
    expect(Math.min(...fuels)).toBeGreaterThanOrEqual(1)
  })

  it('omits telemetry/air-density columns so they encode as NaN (native-missing)', () => {
    const row = buildStintRows(DEFAULT_INPUTS)[0]
    expect('mean_rpm' in row).toBe(false)
    expect('air_density_kgm3' in row).toBe(false)
  })
})

describe('inputsFromStint', () => {
  const stintRow = (lap: number, jump: number | null): StintFeatureRow => ({
    lap_in_stint: lap, age_in_stint: lap, lap_number: 14 + lap, fuel_mass_kg: 80,
    compound: 'SOFT', compound_grip_peak: 1.01, compound_wear_gradient: 0.11,
    compound_optimal_temp_low: 0.85, compound_optimal_temp_high: 1.10,
    compound_cliff_onset_laps: 14, compound_cliff_severity: 0.95,
    expected_compound_pace_s: 2.0, expected_degradation_rate_s_per_lap: 0.85,
    cliff_onset_passed: false, laps_past_cliff: 0, cliff_candidate_flag: false,
    push_residual: 0, cumulative_push_load_surface: 0.1, cumulative_push_load_bulk: 0.2,
    dirty_air_share_lap: 0.2, dirty_air_thermal_load_surface: 0.1, dirty_air_thermal_load_bulk: 0.1,
    air_state_dominant: 'free_air', ambient_temp_delta: 5, is_rain_lap: false,
    track_energy_index: 90, circuit_abrasiveness_index: 3, constructor_id: 'Ferrari',
    event_flag_any: false, anomaly_class: 'normal', next_lap_degradation_jump_s: jump,
    n_gear_changes: null, mean_rpm: null, max_rpm: null, pct_full_throttle: null,
    pct_drs_active: null, short_shift_index: null, mid_corner_speed_loss_kph: null,
    traction_wheelspin_proxy: null, throttle_trace_decay: null,
    braking_point_drift_m: null, lift_coast_share: null,
  })

  it('derives inputs and constants from the first lap, length from the row count', () => {
    const rows = [stintRow(1, 0.3), stintRow(2, 0.4), stintRow(3, null)]
    const inputs = inputsFromStint(rows)!
    expect(inputs.stint_length).toBe(3)
    expect(inputs.constants.compound).toBe('SOFT')
    expect(inputs.constants.compound_cliff_onset_laps).toBe(14)
    expect(inputs.constructor_id).toBe('Ferrari')
    expect(inputs.fuel_mass_kg).toBe(80)
  })

  it('falls back to compound defaults for NULL constants', () => {
    const r = stintRow(1, 0.3)
    r.compound_wear_gradient = null
    const inputs = inputsFromStint([r])!
    expect(inputs.constants.compound_wear_gradient).toBeGreaterThan(0) // default filled
  })

  it('returns null for an empty stint', () => {
    expect(inputsFromStint([])).toBeNull()
  })

  it('observedJumps lines up with lap order including trailing null', () => {
    const rows = [stintRow(1, 0.3), stintRow(2, null)]
    expect(observedJumps(rows)).toEqual([0.3, null])
  })
})


// ---------------------------------------------------------------------------
// P0.3 Accuracy metric unit tests
// These pass immediately and define what "perfect" means for the P3 gates.
// ---------------------------------------------------------------------------
describe('accuracy metrics (P0.3)', () => {
  it('projectedDegMAE returns 0 when curve exactly matches basket', () => {
    const cell = (accuracyBasket as typeof accuracyBasket).basket[0] // Red Bull Ring HARD
    const curve: TyrePoint[] = cell.samples.map(s => ({
      x: s.lap_in_stint,
      tyre: s.obs_deg_from_fresh_p50_s,
    }))
    expect(projectedDegMAE(curve, cell.samples)).toBe(0)
  })

  it('projectedDegMAE measures mean absolute deviation correctly', () => {
    const samples = [
      { lap_in_stint: 5,  obs_deg_from_fresh_p50_s: 1.0 },
      { lap_in_stint: 10, obs_deg_from_fresh_p50_s: 2.0 },
    ]
    const curve: TyrePoint[] = [
      { x: 5,  tyre: 1.5 }, // +0.5 error
      { x: 10, tyre: 2.4 }, // +0.4 error
    ]
    expect(projectedDegMAE(curve, samples)).toBeCloseTo(0.45, 6)
  })

  it('projectedDegMAE returns Infinity when no laps overlap', () => {
    const samples = [{ lap_in_stint: 99, obs_deg_from_fresh_p50_s: 1.0 }]
    const curve: TyrePoint[] = [{ x: 1, tyre: 0.5 }]
    expect(projectedDegMAE(curve, samples)).toBe(Infinity)
  })

  it('monotoneViolations returns 0 for a non-decreasing series', () => {
    expect(monotoneViolations([0, 0.3, 0.7, 0.7, 1.0])).toBe(0)
  })

  it('monotoneViolations counts each strict decrease as one violation', () => {
    // Plateau then drop then rise then drop
    expect(monotoneViolations([0, 1, 0.8, 1.2, 0.9])).toBe(2)
  })

  it('monotoneViolations returns 0 on an empty or single-element series', () => {
    expect(monotoneViolations([])).toBe(0)
    expect(monotoneViolations([5])).toBe(0)
  })

  it('all 5 basket cells have raw-median violations (confirming v2 bug is real)', () => {
    const basket = (accuracyBasket as typeof accuracyBasket).basket
    for (const cell of basket.slice(0, 4)) { // dry compounds expected to show survivorship
      const p50Series = cell.samples.map(s => s.obs_deg_from_fresh_p50_s)
      expect(monotoneViolations(p50Series)).toBeGreaterThan(0)
    }
  })
})
