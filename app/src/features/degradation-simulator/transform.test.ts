import { describe, it, expect } from 'vitest'
import { transform, toCsvRows, inputsFromStint, observedJumps } from './transform'
import { buildStintRows, DEFAULT_INPUTS } from './inputs'
import type { LapPrediction } from '../../ml'
import type { StintFeatureRow } from './queries'

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
