import type { QualityAuditRow } from './queries'

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
