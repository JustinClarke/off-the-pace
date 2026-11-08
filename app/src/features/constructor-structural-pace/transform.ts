import type { ConstructorPaceRow, PaceMode } from './queries'

export interface ConstructorPaceEntry {
  rank: number
  constructor: string
  pace_s: number
  /** null: season view with fewer than 3 races (AP-07) */
  se_s: number | null
  ci_low_s: number | null
  ci_high_s: number | null
  observations: number
  /** Season view: k, the races with an estimate. Race view: 1. */
  races: number
  /** true when the CI is the season t interval, false for a race +/-1.96 interval */
  season: boolean
}

// Two-sided 97.5% Student-t quantiles, df 2..60, 4 dp (scipy.stats.t.ppf(0.975, df)).
const T975: Record<number, number> = {
  2: 4.3027, 3: 3.1824, 4: 2.7764, 5: 2.5706, 6: 2.4469, 7: 2.3646, 8: 2.3060, 9: 2.2622,
  10: 2.2281, 11: 2.2010, 12: 2.1788, 13: 2.1604, 14: 2.1448, 15: 2.1314, 16: 2.1199,
  17: 2.1098, 18: 2.1009, 19: 2.0930, 20: 2.0860, 21: 2.0796, 22: 2.0739, 23: 2.0687,
  24: 2.0639, 25: 2.0595, 26: 2.0555, 27: 2.0518, 28: 2.0484, 29: 2.0452, 30: 2.0423,
  31: 2.0395, 32: 2.0369, 33: 2.0345, 34: 2.0322, 35: 2.0301, 36: 2.0281, 37: 2.0262,
  38: 2.0244, 39: 2.0227, 40: 2.0211, 41: 2.0195, 42: 2.0181, 43: 2.0167, 44: 2.0154,
  45: 2.0141, 46: 2.0129, 47: 2.0117, 48: 2.0106, 49: 2.0096, 50: 2.0086, 51: 2.0076,
  52: 2.0066, 53: 2.0057, 54: 2.0049, 55: 2.0040, 56: 2.0032, 57: 2.0025, 58: 2.0017,
  59: 2.0010, 60: 2.0003,
}

/**
 * 97.5% Student-t quantile for df degrees of freedom (DuckDB has no t quantile).
 * Exact to 4 dp for df 2..60, 1.96 beyond 60. Below df 2 there is no interval
 * (the season rule needs k >= 3), so it returns null.
 */
export function t975(df: number): number | null {
  if (!Number.isFinite(df) || df < 2) return null
  const d = Math.floor(df)
  return d > 60 ? 1.96 : T975[d]
}

const finite = (v: number | null | undefined): v is number => v != null && Number.isFinite(v)

/**
 * SE of a season's plain mean of per-race structural-pace estimates (AP-07).
 *
 *   SE = sqrt(max(VAR_SAMP(p), mean(se^2)) / k)
 *
 * Races are a sample of circuits and weekends: the SE is the larger of the
 * race-to-race spread and the per-race estimation error. Identity:
 * Var(mean) = tau^2/k + sum(se^2)/k^2 with tau^2 = max(0, s^2 - mean se^2).
 * Pairs where either value is null or non-finite are dropped; k < 3 gives
 * null. The season query in queries.ts computes the same thing in SQL.
 */
export function seasonMeanSe(paces: (number | null)[], ses: (number | null)[]): number | null {
  const p: number[] = []
  const s: number[] = []
  for (let i = 0; i < Math.min(paces.length, ses.length); i++) {
    const a = paces[i]
    const b = ses[i]
    if (finite(a) && finite(b)) { p.push(a); s.push(b) }
  }
  const k = p.length
  if (k < 3) return null
  const mean = p.reduce((x, y) => x + y, 0) / k
  const varSamp = p.reduce((x, y) => x + (y - mean) ** 2, 0) / (k - 1)
  const msq = s.reduce((x, y) => x + y * y, 0) / k
  return Math.sqrt(Math.max(varSamp, msq) / k)
}

export type PaceGrain = 'race' | 'season'

/**
 * grain defaults to 'season' when any row aggregates more than one race.
 * Race rows keep the stored +/-1.96 CI; season rows get mean -/+ t(k-1) * SE.
 */
export function transform(rows: ConstructorPaceRow[], grain?: PaceGrain): ConstructorPaceEntry[] {
  const g: PaceGrain = grain ?? (rows.some(r => (r.races_n ?? 1) > 1) ? 'season' : 'race')
  return rows.map((r, i) => {
    const k = r.races_n ?? 1
    const se = r.constructor_structural_pace_se_s
    let lo = r.constructor_structural_pace_ci_low_s
    let hi = r.constructor_structural_pace_ci_high_s
    if (g === 'season') {
      const t = se != null ? t975(k - 1) : null
      lo = se != null && t != null ? r.constructor_structural_pace_s - t * se : null
      hi = se != null && t != null ? r.constructor_structural_pace_s + t * se : null
    }
    return {
      rank: i + 1,
      constructor: r.constructor_id,
      pace_s: r.constructor_structural_pace_s,
      se_s: se,
      ci_low_s: lo ?? null,
      ci_high_s: hi ?? null,
      observations: r.panel_observations_n,
      races: k,
      season: g === 'season',
    }
  })
}

const fix3 = (v: number | null) => (v != null && Number.isFinite(v) ? v.toFixed(3) : null)

export function toCsvRows(entries: ConstructorPaceEntry[], mode: PaceMode): Record<string, unknown>[] {
  return entries.map(e => ({
    rank: e.rank,
    constructor: e.constructor,
    [`${mode}_pace_vs_field_s`]: e.pace_s.toFixed(3),
    se_s: fix3(e.se_s),
    ci_low_s: fix3(e.ci_low_s),
    ci_high_s: fix3(e.ci_high_s),
    interval_method: e.season
      ? 'season: +/-t(k-1)*sqrt(max(var_samp(p), mean(se^2))/k)'
      : 'race: +/-1.96*se',
    observations: e.observations,
    races: e.races,
  }))
}
