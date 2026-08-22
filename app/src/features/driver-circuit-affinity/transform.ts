import type { CircuitAffinityRow } from './queries'
import type { HeatmapCell } from '../../ui/charts'

export interface CircuitAffinityHeatmap {
  xLabels: string[]     // circuit display names (columns)
  yLabels: string[]     // driver IDs (rows)
  cells: HeatmapCell[]
  minValue: number
  maxValue: number
}

export function transform(rows: CircuitAffinityRow[]): CircuitAffinityHeatmap {
  if (!rows.length) {
    return { xLabels: [], yLabels: [], cells: [], minValue: 0, maxValue: 0 }
  }

  // Collect unique circuits and drivers; sort circuits by name, drivers by median affinity asc
  const circuitNameByKey = new Map<string, string>()
  const driverAffinities = new Map<string, number[]>()

  for (const r of rows) {
    circuitNameByKey.set(r.circuit_id, r.circuit_name)
    if (!driverAffinities.has(r.driver_id)) driverAffinities.set(r.driver_id, [])
    driverAffinities.get(r.driver_id)!.push(r.shrunk_affinity_s)
  }

  // Sort circuits by name
  const circuits = [...circuitNameByKey.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  const xLabels = circuits.map(c => c[1])
  const circuitIndexByKey = new Map(circuits.map(([key], i) => [key, i]))

  // Sort drivers by their median affinity (ascending = fastest first)
  const drivers = [...driverAffinities.entries()].sort((a, b) => {
    const medA = median(a[1])
    const medB = median(b[1])
    return medA - medB
  })
  const yLabels = drivers.map(d => d[0])
  const driverIndexById = new Map(drivers.map(([id], i) => [id, i]))

  const cells: HeatmapCell[] = []
  let minValue = Infinity
  let maxValue = -Infinity

  for (const r of rows) {
    const x = circuitIndexByKey.get(r.circuit_id)
    const y = driverIndexById.get(r.driver_id)
    if (x === undefined || y === undefined) continue
    cells.push({ x, y, value: r.shrunk_affinity_s })
    if (r.shrunk_affinity_s < minValue) minValue = r.shrunk_affinity_s
    if (r.shrunk_affinity_s > maxValue) maxValue = r.shrunk_affinity_s
  }

  if (!cells.length) return { xLabels, yLabels, cells, minValue: 0, maxValue: 0 }
  return { xLabels, yLabels, cells, minValue, maxValue }
}

function median(vals: number[]): number {
  const sorted = [...vals].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

export function toCsvRows(rows: CircuitAffinityRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    driver_id: r.driver_id,
    circuit_name: r.circuit_name,
    shrunk_affinity_s: r.shrunk_affinity_s.toFixed(3),
    n_obs: r.n_obs,
    seasons_observed_n: r.seasons_observed_n,
    affinity_confidence: r.affinity_confidence.toFixed(3),
  }))
}
