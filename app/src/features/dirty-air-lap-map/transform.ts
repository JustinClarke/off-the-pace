import type { LapAirStateRow } from './queries'
import type { HeatmapCell } from '../../ui/charts'

export interface LapAirHeatmap {
  xLabels: string[]
  yLabels: string[]
  cells: HeatmapCell[]
}

const AIR_STATE_COLOR: Record<string, string> = {
  free_air:  'rgba(255,255,255,0.04)',
  dirty_air: 'rgb(194,65,12)',
  tow_zone:  'rgb(21,128,61)',
  drs_train: 'rgb(180,83,9)',
}

export function transform(rows: LapAirStateRow[]): LapAirHeatmap {
  if (!rows.length) return { xLabels: [], yLabels: [], cells: [] }

  const lapNums = new Set<number>()
  const driverDirtyCount = new Map<string, number>()

  for (const r of rows) {
    lapNums.add(r.lap_number)
    if (!driverDirtyCount.has(r.driver_id)) driverDirtyCount.set(r.driver_id, 0)
    if (r.air_state_dominant === 'dirty_air') {
      driverDirtyCount.set(r.driver_id, driverDirtyCount.get(r.driver_id)! + 1)
    }
  }

  const sortedLaps = [...lapNums].sort((a, b) => a - b)
  const xLabels = sortedLaps.map(String)
  const lapIndex = new Map(sortedLaps.map((l, i) => [l, i]))

  // Sort drivers most-dirty-air first
  const drivers = [...driverDirtyCount.entries()].sort((a, b) => b[1] - a[1])
  const yLabels = drivers.map(d => d[0])
  const driverIndex = new Map(drivers.map(([id], i) => [id, i]))

  const cells: HeatmapCell[] = []
  for (const r of rows) {
    const x = lapIndex.get(r.lap_number)
    const y = driverIndex.get(r.driver_id)
    if (x === undefined || y === undefined) continue
    cells.push({
      x,
      y,
      value: r.dirty_air_thermal_load_surface,
      color: AIR_STATE_COLOR[r.air_state_dominant] ?? AIR_STATE_COLOR.free_air,
    })
  }

  return { xLabels, yLabels, cells }
}

export function toCsvRows(rows: LapAirStateRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    driver_id: r.driver_id,
    lap_number: r.lap_number,
    air_state_dominant: r.air_state_dominant,
    dirty_air_thermal_load_surface: r.dirty_air_thermal_load_surface.toFixed(4),
    min_gap_s: r.min_gap_s != null ? r.min_gap_s.toFixed(2) : '',
  }))
}
