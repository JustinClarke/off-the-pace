import type { CircuitAffinityRow } from './queries'
import type { HeatmapCell } from '../../ui/charts'

export interface CircuitAffinityHeatmap {
  xLabels: string[]     // circuit display names (columns)
  yLabels: string[]     // driver IDs (rows)
  cells: HeatmapCell[]
  minValue: number
  maxValue: number
}

/**
 * Cells are the driver's affinity: how much better (negative) or worse (positive)
 * he does against his teammate at the circuit than he does on average
 * (`affinity_vs_driver_mean_s`). Never the level `shrunk_affinity_s`: that is a
 * gap to the teammate, so a driver who beats his teammate everywhere would paint
 * an all-green row on a zero-centred scale (F44).
 */
export function transform(rows: CircuitAffinityRow[]): CircuitAffinityHeatmap {
  if (!rows.length) {
    return { xLabels: [], yLabels: [], cells: [], minValue: 0, maxValue: 0 }
  }

  // Collect unique circuits and drivers
  const circuitNameByKey = new Map<string, string>()
  const driverMean = new Map<string, number>()

  for (const r of rows) {
    circuitNameByKey.set(r.circuit_id, r.circuit_name)
    driverMean.set(r.driver_id, r.global_driver_mean_s)
  }

  // Sort circuits by name
  const circuits = [...circuitNameByKey.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  const xLabels = circuits.map(c => c[1])
  const circuitIndexByKey = new Map(circuits.map(([key], i) => [key, i]))

  // Sort drivers by their overall gap to their teammates (most negative = biggest
  // margin over teammates first), driver id as tie-break.
  const drivers = [...driverMean.entries()].sort(
    (a, b) => a[1] - b[1] || a[0].localeCompare(b[0]),
  )
  const yLabels = drivers.map(d => d[0])
  const driverIndexById = new Map(drivers.map(([id], i) => [id, i]))

  const cells: HeatmapCell[] = []
  let minValue = Infinity
  let maxValue = -Infinity

  for (const r of rows) {
    const x = circuitIndexByKey.get(r.circuit_id)
    const y = driverIndexById.get(r.driver_id)
    if (x === undefined || y === undefined) continue
    const value = r.affinity_vs_driver_mean_s
    cells.push({ x, y, value })
    if (value < minValue) minValue = value
    if (value > maxValue) maxValue = value
  }

  if (!cells.length) return { xLabels, yLabels, cells, minValue: 0, maxValue: 0 }
  return { xLabels, yLabels, cells, minValue, maxValue }
}

export function toCsvRows(rows: CircuitAffinityRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    driver_id: r.driver_id,
    circuit_name: r.circuit_name,
    affinity_vs_driver_mean_s: r.affinity_vs_driver_mean_s.toFixed(3),
    driver_mean_gap_to_teammate_s: r.global_driver_mean_s.toFixed(3),
    n_obs: r.n_obs,
    seasons_observed_n: r.seasons_observed_n,
    affinity_confidence: r.affinity_confidence.toFixed(3),
  }))
}
