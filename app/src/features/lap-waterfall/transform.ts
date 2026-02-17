import type { WaterfallBar } from '../../ui/charts/Waterfall'
import type { LapResidualRow } from './queries'

export type ComponentBar = WaterfallBar

export interface WaterfallResult {
  driverId: string
  raceId: string
  bars: ComponentBar[]
  /** sum(components)-total_explained_s; should be ~0 if the identity holds */
  closureGap: number
  nLaps: number
}

// Component display order and labels. These eight terms satisfy the documented identity
//   pace_delta_s = fuel + compound + rubber + ambient + constructor + dirty_air
//                  + driver_skill_residual + track_unexplained
// (the first six sum to total_explained_s; see int_lap_residual_decomposed.sql).
const COMPONENT_KEYS: Array<{ key: keyof LapResidualRow; label: string; color?: string }> = [
  { key: 'fuel_component_s',          label: 'Fuel',         color: 'rgb(96,165,250)'   }, // blue-400
  { key: 'compound_component_s',      label: 'Compound',     color: 'rgb(251,191,36)'   }, // amber-400
  { key: 'rubber_component_s',        label: 'Rubber',       color: 'rgb(234,179,8)'    }, // yellow-500
  { key: 'ambient_component_s',       label: 'Ambient',      color: 'rgb(167,243,208)'  }, // emerald-200
  { key: 'constructor_component_s',   label: 'Constructor',  color: 'rgb(192,132,252)'  }, // violet-400
  { key: 'dirty_air_tax_s',           label: 'Dirty Air',    color: 'rgb(244,114,182)'  }, // pink-400
  { key: 'driver_skill_residual_s',   label: 'Driver Skill', color: 'rgb(249,115,22)'   }, // orange-500
  { key: 'track_unexplained_s',       label: 'Track noise',  color: 'rgb(148,163,184)'  }, // slate-400
]

export function transform(row: LapResidualRow): WaterfallResult {
  let cumsum = 0
  const bars: ComponentBar[] = COMPONENT_KEYS.map(({ key, label, color }) => {
    const value = row[key] as number
    const start = cumsum
    cumsum += value
    return {
      label,
      value,
      start: value < 0 ? start + value : start,
      sign: value >= 0 ? 'positive' : 'negative',
      color,
    }
  })

  const componentSum = COMPONENT_KEYS.reduce((acc, { key }) => acc + (row[key] as number), 0)
  const closureGap = componentSum-row.pace_delta_s

  return {
    driverId: row.driver_id,
    raceId: row.race_id,
    bars,
    closureGap,
    nLaps: row.n_laps,
  }
}

export function toCsvRows(results: WaterfallResult[]): Record<string, unknown>[] {
  return results.flatMap(r =>
    r.bars.map(b => ({
      driver_id: r.driverId,
      race_id: r.raceId,
      component: b.label,
      value_s: b.value.toFixed(6),
      n_laps: r.nLaps,
      closure_gap_s: r.closureGap.toFixed(6),
    }))
  )
}
