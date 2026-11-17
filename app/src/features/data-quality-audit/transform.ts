import type { QualityAuditRow, UnavailableRaceRow } from './queries'

export interface QualityResult extends QualityAuditRow {
  round: number
  circuit_name: string
}

export function transform(
  rows: QualityAuditRow[],
  nameMap: Record<string, string> = {}
): QualityResult[] {
  return rows
    .map(r => ({
      ...r,
      round: parseInt(r.race_id.split('_')[1] ?? '0', 10),
      circuit_name: nameMap[r.race_id] ?? r.race_id,
    }))
    .sort((a, b) => a.round - b.round)
}

export function toCsvRows(rows: QualityAuditRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    race_id: r.race_id,
    total_laps: r.total_laps,
    usable_laps: r.usable_laps,
    pct_usable: r.pct_usable,
    neutralised_laps: r.neutralised_laps,
    rain_laps: r.rain_laps,
    out_in_laps: r.out_in_laps,
    major_outlier_laps: r.major_outlier_laps,
    anomaly_laps: r.anomaly_laps,
  }))
}

/** TX-16: plain-language reason per coverage_reason the page lists as unavailable. */
export const UNAVAILABLE_TEXT: Record<string, string> = {
  SOURCE_UNAVAILABLE: 'Not available: the timing source could not deliver this race, so no laps are counted. This is a recorded gap, not zero laps.',
}

export interface UnavailableRace {
  race_id: string
  round: number
  circuit_name: string
  reason: string
}

export function unavailableRaces(
  rows: UnavailableRaceRow[],
  nameMap: Record<string, string> = {}
): UnavailableRace[] {
  return rows
    .map(r => ({
      race_id: r.race_id,
      round: parseInt(r.race_id.split('_')[1] ?? '0', 10),
      circuit_name: nameMap[r.race_id] ?? r.race_id,
      reason: UNAVAILABLE_TEXT[r.coverage_reason] ?? `Not available (${r.coverage_reason})`,
    }))
    .sort((a, b) => a.round - b.round)
}
