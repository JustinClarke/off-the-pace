import type { PartyModeRow } from './queries'
import { t975 } from '../constructor-structural-pace/transform'

export type ModeLabel = 'party' | 'race' | 'no_clear_gap'

export interface PartyModeEntry {
  constructor: string
  race_pace_s: number | null
  quali_pace_s: number
  delta_s: number | null
  /** SE of the quali − race delta; null when it cannot be computed (season k < 3, missing side) */
  delta_se_s: number | null
  delta_ci_low_s: number | null
  delta_ci_high_s: number | null
  /** The 95% CI of the delta includes 0 (null when there is no CI) */
  delta_ci_covers_zero: boolean | null
  /** null when there is no delta or no CI (rendered as a dash) */
  mode: ModeLabel | null
  race_obs: number
  quali_obs: number
  /** Season grain: k, the races with both estimates */
  races_n: number | null
}

/**
 * party: delta < -0.15 and the CI is wholly below 0. race: delta > 0.15 and the
 * CI is wholly above 0. Anything else with a delta and a CI is "no clear gap".
 * No delta or no CI: no label.
 */
export function classify(delta: number | null, lo: number | null, hi: number | null): ModeLabel | null {
  if (delta == null || lo == null || hi == null) return null
  if (!Number.isFinite(delta) || !Number.isFinite(lo) || !Number.isFinite(hi)) return null
  if (delta < -0.15 && hi < 0) return 'party'
  if (delta > 0.15 && lo > 0) return 'race'
  return 'no_clear_gap'
}

/**
 * SE of quali − race from the two sides' SEs: sqrt(se_q² + se_r²). Assumes the
 * two estimates' errors are independent (they come from different sessions'
 * laps). Both inputs come from the same Structural Pace model, so the delta is
 * not independent evidence of a team trait, only of a quali/race gap.
 */
export function deltaSe(seQuali: number | null, seRace: number | null): number | null {
  if (seQuali == null || seRace == null) return null
  if (!Number.isFinite(seQuali) || !Number.isFinite(seRace)) return null
  return Math.sqrt(seQuali * seQuali + seRace * seRace)
}

/** 95% CI as delta ± mult · SE (mult = 1.96 race grain, t(k-1) season grain), and whether it includes 0. */
export function deltaInterval(delta: number | null, se: number | null, mult = 1.96): {
  low: number | null
  high: number | null
  coversZero: boolean | null
} {
  if (delta == null || se == null || !Number.isFinite(delta) || !Number.isFinite(se)) {
    return { low: null, high: null, coversZero: null }
  }
  const low = delta - mult * se
  const high = delta + mult * se
  return { low, high, coversZero: low <= 0 && high >= 0 }
}

export function transform(rows: PartyModeRow[]): PartyModeEntry[] {
  return rows.map(r => {
    const season = r.races_n != null
    const se = season ? (r.delta_se_s ?? null) : deltaSe(r.quali_se_s, r.race_se_s)
    const mult = season ? t975(r.races_n! - 1) : 1.96
    const ci = mult == null ? deltaInterval(null, null) : deltaInterval(r.delta_s, se, mult)
    return {
      constructor: r.constructor_id,
      race_pace_s: r.race_pace_s,
      quali_pace_s: r.quali_pace_s,
      delta_s: r.delta_s,
      delta_se_s: ci.low == null ? null : se,
      delta_ci_low_s: ci.low,
      delta_ci_high_s: ci.high,
      delta_ci_covers_zero: ci.coversZero,
      mode: classify(r.delta_s, ci.low, ci.high),
      race_obs: r.race_obs,
      quali_obs: r.quali_obs,
      races_n: r.races_n ?? null,
    }
  })
}

const fix3 = (v: number | null) => (v != null && Number.isFinite(v) ? v.toFixed(3) : null)

export function toCsvRows(entries: PartyModeEntry[]): Record<string, unknown>[] {
  return entries.map(e => ({
    constructor: e.constructor,
    quali_pace_vs_field_s: fix3(e.quali_pace_s),
    race_pace_vs_field_s: fix3(e.race_pace_s),
    delta_quali_minus_race_s: fix3(e.delta_s),
    delta_se_s: fix3(e.delta_se_s),
    delta_ci_low_s: fix3(e.delta_ci_low_s),
    delta_ci_high_s: fix3(e.delta_ci_high_s),
    mode: e.mode,
    delta_ci_covers_zero: e.delta_ci_covers_zero,
    races_n: e.races_n,
    race_observations: e.race_obs,
    quali_observations: e.quali_obs,
  }))
}
