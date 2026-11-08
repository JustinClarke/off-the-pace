import type { WaterfallBar } from '../../ui/charts/Waterfall'
import type { LapResidualRow } from './queries'
import { buildBar } from '../../ui/charts/waterfallBars'

export type ComponentBar = WaterfallBar

export interface WaterfallResult {
  driverId: string
  raceId: string
  bars: ComponentBar[]
  /** sum(five identity terms) - pace_delta_s over the same closed lap set; ~0 if the identity holds. NULL (n/a) when that set is empty. */
  closureGap: number | null
  nLaps: number
  /** Laps the five bars and the pace delta are all averaged over (0 = closure n/a) */
  nClosedLaps: number
  /** Mean pace delta over the closed set; NULL when the set is empty */
  paceDeltaS: number | null
}

// Identity bars. These five terms satisfy the CI-enforced five-term identity
//   pace_delta_s = fuel + compound + constructor + dirty_air + driver_skill_residual
// (the first four sum to total_explained_s; see int_lap_residual_decomposed.sql).
// Rubber and ambient are already inside base_track_pace_s and are not bars.
//
// AP-06: every identity term and the closure check use ONE lap set, the closed set
// (n_closed_laps: all five terms and pace_delta_s non-NULL), so the bars add up to the
// pace delta. If that set is empty, each bar falls back to its own coverage and the
// closure is n/a (NULL).
const COMPONENT_KEYS: Array<{ key: keyof LapResidualRow; closedKey: keyof LapResidualRow; nKey: keyof LapResidualRow; label: string; color?: string }> = [
  { key: 'fuel_component_s', closedKey: 'closed_fuel_component_s', nKey: 'n_fuel_component_s',          label: 'Fuel',         color: 'rgb(96,165,250)'   }, // blue-400
  { key: 'compound_component_s', closedKey: 'closed_compound_component_s', nKey: 'n_compound_component_s',      label: 'Compound',     color: 'rgb(251,191,36)'   }, // amber-400
  { key: 'constructor_component_s', closedKey: 'closed_constructor_component_s', nKey: 'n_constructor_component_s',   label: 'Constructor',  color: 'rgb(192,132,252)'  }, // violet-400
  { key: 'dirty_air_tax_s', closedKey: 'closed_dirty_air_tax_s', nKey: 'n_dirty_air_tax_s',           label: 'Dirty Air',    color: 'rgb(244,114,182)'  }, // pink-400
  { key: 'driver_skill_residual_s', closedKey: 'closed_driver_skill_residual_s', nKey: 'n_driver_skill_residual_s',   label: 'Driver Skill', color: 'rgb(249,115,22)'   }, // orange-500
]

// Informational diagnostic: shown as a standalone bar, never summed into the identity.
const DIAGNOSTIC = {
  key: 'track_unexplained_s' as const,
  nKey: 'n_track_unexplained_s' as const,
  label: 'Track noise',
  color: 'rgb(148,163,184)',
}

export function transform(row: LapResidualRow): WaterfallResult {
  let cumsum = 0
  const closed = row.n_closed_laps > 0
  const bars: ComponentBar[] = COMPONENT_KEYS.map(({ key, closedKey, nKey, label, color }) => {
    const { bar, nextStart } = buildBar(
      label,
      (closed ? row[closedKey] : row[key]) as number | null,
      closed ? row.n_closed_laps : (row[nKey] as number),
      row.n_laps, color, cumsum,
    )
    cumsum = nextStart
    return bar
  })

  bars.push(
    buildBar(
      DIAGNOSTIC.label,
      row[DIAGNOSTIC.key],
      row[DIAGNOSTIC.nKey],
      row.n_laps,
      DIAGNOSTIC.color,
      0,
      false,
    ).bar,
  )

  const terms = COMPONENT_KEYS.map(({ closedKey }) => row[closedKey] as number | null)
  const closureGap =
    !closed || row.pace_delta_s === null || terms.some(t => t === null)
      ? null
      : (terms as number[]).reduce((acc, t) => acc + t, 0) - row.pace_delta_s

  return {
    driverId: row.driver_id,
    raceId: row.race_id,
    bars,
    closureGap,
    nLaps: row.n_laps,
    nClosedLaps: row.n_closed_laps,
    paceDeltaS: row.pace_delta_s,
  }
}

export function toCsvRows(results: WaterfallResult[]): Record<string, unknown>[] {
  return results.flatMap(r =>
    r.bars.map(b => ({
      driver_id: r.driverId,
      race_id: r.raceId,
      component: b.label,
      value_s: b.value === null ? '' : b.value.toFixed(6),
      n_laps: r.nLaps,
      closure_gap_s: r.closureGap === null ? '' : r.closureGap.toFixed(6),
    }))
  )
}
