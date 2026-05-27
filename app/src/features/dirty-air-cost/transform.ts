import type { DirtyAirCostRow } from './queries'

export interface DirtyAirResult {
  rank: number
  driver_id: string
  total_dirty_air_cost_s: number
  avg_tax_s: number
  taxed_laps: number
  total_laps: number
}

export function transform(rows: DirtyAirCostRow[]): DirtyAirResult[] {
  return rows
    .slice()
    .sort((a, b) => b.total_dirty_air_cost_s - a.total_dirty_air_cost_s)
    .map((r, i) => ({
      rank: i + 1,
      driver_id: r.driver_id,
      total_dirty_air_cost_s: r.total_dirty_air_cost_s,
      avg_tax_s: r.avg_tax_s,
      taxed_laps: r.taxed_laps,
      total_laps: r.total_laps,
    }))
}

export function toCsvRows(rows: DirtyAirCostRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    driver_id: r.driver_id,
    total_dirty_air_cost_s: r.total_dirty_air_cost_s.toFixed(3),
    avg_tax_s: r.avg_tax_s.toFixed(3),
    taxed_laps: r.taxed_laps,
    total_laps: r.total_laps,
  }))
}
