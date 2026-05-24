// The simulator's adjustable input model and the stint-sweep that turns one set of slider
// values into a FeatureRow per lap (the input the ONNX layer scores). The slider ranges and
// defaults below are grounded in the real distribution of fct_cliff_prediction_features
// (2018-2024, p5/p95 used for slider bounds, median for defaults) so the cold-start state is a
// plausible mid-field stint rather than zeros.
//
// Only the features a strategist actually reasons about are exposed as controls. Every other
// model feature is either derived from a control (the cliff-state booleans, age) or left as the
// compound/circuit constant captured in the preset. Features absent from the exported parquet
// (telemetry + air-density columns) were NULL in training too, so they stay NaN here-the model
// was trained to handle them as native-missing.

import type { FeatureRow } from '../../ml'

/** A compound's static physical constants-filled from a preset, or these per-compound defaults. */
export interface CompoundConstants {
  compound: string
  compound_grip_peak: number
  compound_wear_gradient: number
  compound_optimal_temp_low: number
  compound_optimal_temp_high: number
  compound_cliff_onset_laps: number
  compound_cliff_severity: number
  expected_compound_pace_s: number
  expected_degradation_rate_s_per_lap: number
}

/** Everything the user can dial. Compound + the constants travel together (a real tyre, not a knob). */
export interface SimulatorInputs {
  stint_length: number          // laps to sweep (lap_in_stint = 1..stint_length)
  current_lap: number           // the marker lap the gauge/cliff bars read; clamped to stint_length
  lap_number: number            // race lap at stint start (for fuel/track-evo context)
  fuel_mass_kg: number
  dirty_air_share_lap: number    // 0..1
  air_state_dominant: string     // categorical
  ambient_temp_delta: number
  is_rain_lap: boolean
  track_energy_index: number
  circuit_abrasiveness_index: number
  constructor_id: string
  constants: CompoundConstants
}

export interface SliderSpec {
  key: keyof SimulatorInputs
  label: string
  min: number
  max: number
  step: number
  unit?: string
}

// Slider bounds: p5/p95 of the real data, rounded to sensible strategist units.
export const SLIDERS: SliderSpec[] = [
  { key: 'stint_length', label: 'Stint length', min: 5, max: 50, step: 1, unit: 'laps' },
  { key: 'current_lap', label: 'Current lap in stint', min: 1, max: 50, step: 1, unit: 'laps' },
  { key: 'lap_number', label: 'Race lap at stint start', min: 1, max: 70, step: 1, unit: 'laps' },
  { key: 'fuel_mass_kg', label: 'Fuel load', min: 5, max: 115, step: 1, unit: 'kg' },
  { key: 'dirty_air_share_lap', label: 'Dirty-air share', min: 0, max: 1, step: 0.05 },
  { key: 'ambient_temp_delta', label: 'Ambient temp delta', min: 0, max: 30, step: 1, unit: '°C' },
  { key: 'track_energy_index', label: 'Track energy index', min: 40, max: 135, step: 1 },
  { key: 'circuit_abrasiveness_index', label: 'Circuit abrasiveness', min: 2, max: 4, step: 1 },
]

export const COMPOUND_OPTIONS = ['HARD', 'MEDIUM', 'SOFT', 'SUPERSOFT', 'ULTRASOFT', 'HYPERSOFT', 'INTERMEDIATE', 'WET']
export const AIR_STATE_OPTIONS = ['free_air', 'dirty_air', 'drs_train', 'tow_zone']
export const CONSTRUCTOR_OPTIONS = [
  'Red Bull Racing', 'Ferrari', 'Mercedes', 'McLaren', 'Aston Martin', 'Alpine',
  'Williams', 'AlphaTauri', 'RB', 'Alfa Romeo', 'Kick Sauber', 'Haas F1 Team',
]

// Per-compound physical defaults (medians from the real data for the common compounds; the soft
// end scaled from MEDIUM). Used when the user picks a compound without loading a real stint.
const COMPOUND_DEFAULTS: Record<string, CompoundConstants> = {
  HARD: cc('HARD', 1.00, 0.045, 0.70, 0.95, 28, 0.70, 1.4, 0.40),
  MEDIUM: cc('MEDIUM', 1.00, 0.066, 0.80, 1.05, 20, 0.78, 1.6, 0.56),
  SOFT: cc('SOFT', 1.01, 0.110, 0.85, 1.10, 14, 0.95, 2.0, 0.85),
  SUPERSOFT: cc('SUPERSOFT', 1.02, 0.150, 0.88, 1.12, 11, 1.10, 2.4, 1.05),
  ULTRASOFT: cc('ULTRASOFT', 1.02, 0.190, 0.90, 1.14, 9, 1.30, 2.8, 1.25),
  HYPERSOFT: cc('HYPERSOFT', 1.03, 0.230, 0.92, 1.16, 7, 1.50, 3.2, 1.45),
  INTERMEDIATE: cc('INTERMEDIATE', 0.97, 0.080, 0.55, 0.85, 22, 0.80, 6.0, 0.70),
  WET: cc('WET', 0.95, 0.070, 0.45, 0.75, 25, 0.75, 9.0, 0.65),
}

function cc(
  compound: string, grip: number, wear: number, tLow: number, tHigh: number,
  cliffOnset: number, cliffSev: number, pace: number, degRate: number,
): CompoundConstants {
  return {
    compound,
    compound_grip_peak: grip,
    compound_wear_gradient: wear,
    compound_optimal_temp_low: tLow,
    compound_optimal_temp_high: tHigh,
    compound_cliff_onset_laps: cliffOnset,
    compound_cliff_severity: cliffSev,
    expected_compound_pace_s: pace,
    expected_degradation_rate_s_per_lap: degRate,
  }
}

export function compoundConstants(compound: string): CompoundConstants {
  return COMPOUND_DEFAULTS[compound] ?? COMPOUND_DEFAULTS.MEDIUM
}

/** The cold-start state: a plausible mid-field 25-lap medium stint. */
export const DEFAULT_INPUTS: SimulatorInputs = {
  stint_length: 25,
  current_lap: 12,
  lap_number: 15,
  fuel_mass_kg: 60,
  dirty_air_share_lap: 0,
  air_state_dominant: 'free_air',
  ambient_temp_delta: 0,
  is_rain_lap: false,
  track_energy_index: 80,
  circuit_abrasiveness_index: 3,
  constructor_id: 'Mercedes',
  constants: compoundConstants('MEDIUM'),
}

/**
 * Build one FeatureRow per lap of the stint (lap_in_stint = 1..stint_length), keyed by the
 * warehouse column names the manifest's feature_order expects. The cliff-state features
 * (cliff_onset_passed, laps_past_cliff, cliff_candidate_flag, age_in_stint, lap_number) are
 * derived from the lap position and the compound's cliff-onset constant-exactly how the
 * warehouse computes them-so the swept rows are faithful model inputs, not hand-waved.
 *
 * Pure and deterministic: the unit tests pin its output. Columns absent from the input model
 * (telemetry/air-density) are simply not set, so buildFeatureVector encodes them as NaN.
 */
export function buildStintRows(inputs: SimulatorInputs): FeatureRow[] {
  const { constants } = inputs
  const cliffOnset = constants.compound_cliff_onset_laps
  const rows: FeatureRow[] = []

  for (let lap = 1; lap <= inputs.stint_length; lap++) {
    const lapsPastCliff = Math.max(0, lap - cliffOnset)
    const cliffPassed = lap > cliffOnset
    // A lap is a cliff candidate once it is within two laps of the modelled onset.
    const cliffCandidate = lap >= cliffOnset - 2

    rows.push({
      lap_number: inputs.lap_number + (lap - 1),
      lap_in_stint: lap,
      age_in_stint: lap, // fresh-fitted stint: tyre age tracks laps run
      fuel_mass_kg: Math.max(1, inputs.fuel_mass_kg - (lap - 1) * 1.6), // ~1.6 kg/lap burn
      compound: constants.compound,
      compound_grip_peak: constants.compound_grip_peak,
      compound_wear_gradient: constants.compound_wear_gradient,
      compound_optimal_temp_low: constants.compound_optimal_temp_low,
      compound_optimal_temp_high: constants.compound_optimal_temp_high,
      compound_cliff_onset_laps: constants.compound_cliff_onset_laps,
      compound_cliff_severity: constants.compound_cliff_severity,
      expected_compound_pace_s: constants.expected_compound_pace_s,
      expected_degradation_rate_s_per_lap: constants.expected_degradation_rate_s_per_lap,
      cliff_onset_passed: cliffPassed,
      laps_past_cliff: lapsPastCliff,
      cliff_candidate_flag: cliffCandidate,
      // push/thermal loads accumulate with lap; modest linear proxies in the real data's range.
      push_residual: 0,
      cumulative_push_load_surface: lap * 0.12,
      cumulative_push_load_bulk: lap * 0.18,
      dirty_air_share_lap: inputs.dirty_air_share_lap,
      dirty_air_thermal_load_surface: inputs.dirty_air_share_lap * 1.2,
      dirty_air_thermal_load_bulk: inputs.dirty_air_share_lap * 0.9,
      air_state_dominant: inputs.air_state_dominant,
      ambient_temp_delta: inputs.ambient_temp_delta,
      is_rain_lap: inputs.is_rain_lap,
      track_energy_index: inputs.track_energy_index,
      circuit_abrasiveness_index: inputs.circuit_abrasiveness_index,
      constructor_id: inputs.constructor_id,
      event_flag_any: false,
      anomaly_class: 'normal',
      // n_gear_changes, mean_rpm, max_rpm, pct_full_throttle, pct_drs_active, short_shift_index,
      // air_density_kgm3, density_ratio_to_ref are intentionally omitted -> NaN (native-missing).
    })
  }
  return rows
}
