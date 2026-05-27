import type { CircuitInteractionRow } from './queries'
import type { HeatmapCell } from '../../ui/charts'

export interface CircuitInteractionHeatmap {
  xLabels: string[]
  yLabels: string[]
  cells: HeatmapCell[]
  minValue: number
  maxValue: number
}

export function transform(rows: CircuitInteractionRow[]): CircuitInteractionHeatmap {
  if (!rows.length) {
    return { xLabels: [], yLabels: [], cells: [], minValue: 0, maxValue: 0 }
  }

  const circuitNameByKey = new Map<string, string>()
  const constructorInteractions = new Map<string, number[]>()

  for (const r of rows) {
    circuitNameByKey.set(r.circuit_key, r.circuit_name)
    if (!constructorInteractions.has(r.constructor_id)) {
      constructorInteractions.set(r.constructor_id, [])
    }
    constructorInteractions.get(r.constructor_id)!.push(r.avg_interaction_s)
  }

  // Sort circuits alphabetically
  const circuits = [...circuitNameByKey.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  const xLabels = circuits.map(c => c[1])
  const circuitIndexByKey = new Map(circuits.map(([key], i) => [key, i]))

  // Sort constructors by their overall average interaction (strongest positive last)
  const constructors = [...constructorInteractions.entries()].sort((a, b) => {
    const avgA = a[1].reduce((s, v) => s + v, 0) / a[1].length
    const avgB = b[1].reduce((s, v) => s + v, 0) / b[1].length
    return avgA - avgB
  })
  const yLabels = constructors.map(c => c[0])
  const constructorIndexById = new Map(constructors.map(([id], i) => [id, i]))

  const cells: HeatmapCell[] = []
  let minValue = Infinity
  let maxValue = -Infinity

  for (const r of rows) {
    const x = circuitIndexByKey.get(r.circuit_key)
    const y = constructorIndexById.get(r.constructor_id)
    if (x === undefined || y === undefined) continue
    cells.push({ x, y, value: r.avg_interaction_s })
    if (r.avg_interaction_s < minValue) minValue = r.avg_interaction_s
    if (r.avg_interaction_s > maxValue) maxValue = r.avg_interaction_s
  }

  if (!cells.length) return { xLabels, yLabels, cells, minValue: 0, maxValue: 0 }
  return { xLabels, yLabels, cells, minValue, maxValue }
}

export function toCsvRows(rows: CircuitInteractionRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    constructor_id: r.constructor_id,
    circuit_name: r.circuit_name,
    avg_interaction_s: r.avg_interaction_s.toFixed(3),
    n_races: r.n_races,
  }))
}
