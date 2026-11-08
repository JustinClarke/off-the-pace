import type { WaterfallBar } from '../../ui/charts'
import type { RaceLostRow } from './queries'
import { buildBar } from '../../ui/charts/waterfallBars'

export interface RaceLostResult {
  bars: WaterfallBar[]
  totalPaceDelta: number | null
  /** sum(five identity terms) - pace delta, both over the closed lap set. NULL (n/a) when that set is empty. */
  closureGap: number | null
  nLaps: number
  /** Laps the five identity bars and the pace delta are all summed over (0 = closure n/a) */
  nClosedLaps: number
}

// AP-06: the five identity terms (everything but Track Noise) and the pace delta are summed over ONE lap
// set, the closed set (n_closed_laps), so the bars add up to the pace delta. If it is empty, each bar falls
// back to its own coverage and the closure is n/a. Track Noise is informational and not in the identity.
const COMPONENTS: Array<{
  key: keyof RaceLostRow
  closedKey?: keyof RaceLostRow
  nKey: keyof RaceLostRow
  label: string
  color: string
}> = [
  { key: 'total_fuel_s', closedKey: 'closed_fuel_s', nKey: 'n_fuel_component_s',        label: 'Fuel',         color: 'rgb(96,165,250)'   },
  { key: 'total_compound_s', closedKey: 'closed_compound_s', nKey: 'n_compound_component_s',    label: 'Compound',     color: 'rgb(251,191,36)'   },
  { key: 'total_constructor_s', closedKey: 'closed_constructor_s', nKey: 'n_constructor_component_s', label: 'Constructor',  color: 'rgb(192,132,252)'  },
  { key: 'total_dirty_air_s', closedKey: 'closed_dirty_air_s', nKey: 'n_dirty_air_tax_s',   label: 'Dirty Air',    color: 'rgb(244,114,182)'  },
  { key: 'total_skill_s', closedKey: 'closed_skill_s', nKey: 'n_driver_skill_residual_s',       label: 'Driver Skill', color: 'rgb(249,115,22)'   },
  { key: 'total_track_s', nKey: 'n_track_unexplained_s',       label: 'Track Noise',  color: 'rgb(148,163,184)'  },
]

export function transform(row: RaceLostRow): RaceLostResult {
  let cumsum = 0
  const closed = row.n_closed_laps > 0
  const bars: WaterfallBar[] = COMPONENTS.map(({ key, closedKey, nKey, label, color }) => {
    const useClosed = closed && closedKey !== undefined
    const { bar, nextStart } = buildBar(
      label,
      (useClosed ? row[closedKey!] : row[key]) as number | null,
      useClosed ? row.n_closed_laps : (row[nKey] as number),
      row.n_laps, color, cumsum,
    )
    cumsum = nextStart
    return bar
  })

  const terms = COMPONENTS.filter(c => c.closedKey).map(({ closedKey }) => row[closedKey!] as number | null)
  const closureGap =
    !closed || row.total_pace_delta_s === null || terms.some(t => t === null)
      ? null
      : (terms as number[]).reduce((acc, t) => acc + t, 0) - row.total_pace_delta_s

  return {
    bars,
    totalPaceDelta: row.total_pace_delta_s,
    closureGap,
    nLaps: row.n_laps,
    nClosedLaps: row.n_closed_laps,
  }
}

export function toCsvRows(driverId: string, row: RaceLostRow): Record<string, unknown>[] {
  // The CSV carries exactly the values the bars display (closed lap set, AP-06).
  return transform(row).bars.map(b => ({
    driver_id: driverId,
    component: b.label,
    total_s: b.value === null ? '' : b.value.toFixed(4),
  }))
}
