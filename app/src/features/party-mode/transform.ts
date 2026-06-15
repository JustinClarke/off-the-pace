import type { PartyModeRow } from './queries'

export type ModeLabel = 'party' | 'balanced' | 'race'

export interface PartyModeEntry {
  constructor: string
  race_pace_s: number
  quali_pace_s: number
  delta_s: number
  mode: ModeLabel
  race_obs: number
  quali_obs: number
}

function classify(delta: number): ModeLabel {
  if (delta < -0.15) return 'party'
  if (delta > 0.15) return 'race'
  return 'balanced'
}

export function transform(rows: PartyModeRow[]): PartyModeEntry[] {
  return rows.map(r => ({
    constructor: r.constructor_id,
    race_pace_s: r.race_pace_s,
    quali_pace_s: r.quali_pace_s,
    delta_s: r.delta_s,
    mode: classify(r.delta_s),
    race_obs: r.race_obs,
    quali_obs: r.quali_obs,
  }))
}

export function toCsvRows(entries: PartyModeEntry[]): Record<string, unknown>[] {
  return entries.map(e => ({
    constructor: e.constructor,
    quali_pace_vs_field_s: e.quali_pace_s.toFixed(3),
    race_pace_vs_field_s: e.race_pace_s.toFixed(3),
    delta_quali_minus_race_s: e.delta_s.toFixed(3),
    mode: e.mode,
    race_observations: e.race_obs,
    quali_observations: e.quali_obs,
  }))
}
