import type { ConstructorPaceRow, PaceMode } from './queries'

export interface ConstructorPaceEntry {
  rank: number
  constructor: string
  pace_s: number
  se_s: number
  ci_low_s: number
  ci_high_s: number
  observations: number
  races: number
}

export function transform(rows: ConstructorPaceRow[]): ConstructorPaceEntry[] {
  return rows.map((r, i) => ({
    rank: i + 1,
    constructor: r.constructor_id,
    pace_s: r.constructor_structural_pace_s,
    se_s: r.constructor_structural_pace_se_s,
    ci_low_s: r.constructor_structural_pace_ci_low_s,
    ci_high_s: r.constructor_structural_pace_ci_high_s,
    observations: r.panel_observations_n,
    races: r.races_n ?? 1,
  }))
}

export function toCsvRows(entries: ConstructorPaceEntry[], mode: PaceMode): Record<string, unknown>[] {
  return entries.map(e => ({
    rank: e.rank,
    constructor: e.constructor,
    [`${mode}_pace_vs_field_s`]: e.pace_s.toFixed(3),
    se_s: e.se_s.toFixed(3),
    ci_low_s: e.ci_low_s.toFixed(3),
    ci_high_s: e.ci_high_s.toFixed(3),
    observations: e.observations,
    races: e.races,
  }))
}
