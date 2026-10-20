// Browser side of CO-08 (draft): the laps-to-flag cap and the calibrated chance that a
// final stint's tyres reach the flag. The mirror of ml/src/flag_chance.py; the two are
// held together by __fixtures__/flag_chance_parity.json (flagChance.test.ts here,
// ml/tests/test_flag_chance.py on the Python side).
//
// Why a cap: the stint-life model predicts how long the TYRE can last. On a final stint
// that can run past the chequered flag, but a stint cannot outlast the race, so the
// realised ending is min(tyre life, laps to the flag). The gate already scores exactly
// that, so capping what is shown changes no score.
//
// laps to the flag = laps still to run after this one. The fuel model is built from the
// scheduled distance (fuel = initial - rate * (lap - 1), rate = initial / scheduled), so
// it is fuel / burn rate - 1, exactly.

import { MODELS_BASE } from './manifest'

/**
 * The 2025 scorecard of the shipped lookup (rule `last3`, chosen on 2024 only, fitted on
 * 2018-2024 out-of-fold). It FAILED the acceptance bar, so the chance is shown as
 * experimental and stays provisional until 2026 races are scored. Source: CO-08 drift-fix
 * result; reproduced with `python -m ml.src.flag_chance fit --weighting last3`.
 */
export const FLAG_CHANCE_CALIBRATION = {
  evalSeason: 2025,
  rule: 'last3',
  binsWithinTolerance: 5,
  binsTotal: 10,
  tolerancePp: 5,
  worstGapPp: 19.9,
  brier: 0.0803,
  brierBaseRate: 0.2454,
} as const

/** The recalibration table written by `python -m ml.src.flag_chance fit`. */
export interface FlagChanceLookup {
  schema_version: number
  model_version: string
  booster_sha256: string | null
  aft_scale: number
  label_shift: number
  method: string
  x: number[]
  y: number[]
}

/**
 * Complementary error function, Numerical Recipes' Chebyshev fit (erfcc): fractional
 * error below 1.2e-7 everywhere, far inside the 1e-5 parity tolerance this feeds.
 */
export function erfc(x: number): number {
  const z = Math.abs(x)
  const t = 1 / (1 + 0.5 * z)
  const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 +
    t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 +
    t * (-0.82215223 + t * 0.17087277)))))))))
  return x >= 0 ? r : 2 - r
}

/** Standard normal survival function, P(Z > z). */
export function normalSf(z: number): number {
  return 0.5 * erfc(z / Math.SQRT2)
}

/** Laps still to run after this one, from the fuel model. Never negative. */
export function lapsToFlagFromFuel(fuelKg: number, burnRateKgPerLap: number): number {
  return Math.max(fuelKg / burnRateKgPerLap - 1, 0)
}

/** min(laps, lapsToFlag). A null lapsToFlag means the race length is unknown: no cap. */
export function capToFlag(laps: number, lapsToFlag: number | null): number {
  return lapsToFlag === null || Number.isNaN(lapsToFlag) ? laps : Math.min(laps, lapsToFlag)
}

/** P(remaining tyre life >= lapsToFlag) under the fitted log-normal AFT, from the
 *  reported (clipped) median -- the same number predict.py starts from. */
export function rawFlagChance(medianLaps: number, lapsToFlag: number, aftScale: number,
  labelShift = 1): number {
  const mu = Math.log(medianLaps + labelShift)
  return normalSf((Math.log(lapsToFlag + labelShift) - mu) / aftScale)
}

/** Piecewise-linear map through the lookup, clamped at both ends (numpy.interp). */
export function applyFlagLookup(raw: number, lookup: Pick<FlagChanceLookup, 'x' | 'y'>): number {
  const { x, y } = lookup
  const n = x.length
  if (n === 0) return raw
  if (raw <= x[0]) return y[0]
  if (raw >= x[n - 1]) return y[n - 1]
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {               // x is strictly increasing (asserted Python-side)
    const mid = (lo + hi) >> 1
    if (x[mid] <= raw) lo = mid
    else hi = mid
  }
  const w = (raw - x[lo]) / (x[hi] - x[lo])
  return y[lo] + w * (y[hi] - y[lo])
}

export interface FlagChance {
  raw: number
  calibrated: number
}

/** The chance, or null when it must not be shown: no lookup, or the lookup was fitted
 *  for a different model than the one that produced the median. */
export function flagChance(medianLaps: number, lapsToFlag: number, lookup: FlagChanceLookup | null,
  modelVersion?: string): FlagChance | null {
  if (!lookup) return null
  if (modelVersion !== undefined && lookup.model_version !== modelVersion) return null
  const raw = rawFlagChance(medianLaps, lapsToFlag, lookup.aft_scale, lookup.label_shift)
  return { raw, calibrated: applyFlagLookup(raw, lookup) }
}

/**
 * Fetch the lookup published beside the manifest. Absent (404), unreadable, or fitted for
 * another model version → null, and the gauge simply does not show the line.
 */
export async function loadFlagChanceLookup(modelVersion: string): Promise<FlagChanceLookup | null> {
  try {
    const res = await fetch(`${MODELS_BASE}/flag_chance_lookup.json`)
    if (!res.ok) return null
    const lk = (await res.json()) as FlagChanceLookup
    return lk.model_version === modelVersion ? lk : null
  } catch {
    return null
  }
}
