import type { WaterfallBar } from '../../ui/charts'
import type { RaceLostRow } from './queries'

export interface RaceLostResult {
  bars: WaterfallBar[]
  totalPaceDelta: number
  closureGap: number
  nLaps: number
}

const COMPONENTS: Array<{
  key: keyof RaceLostRow
  label: string
  color: string
}> = [
  { key: 'total_fuel_s',        label: 'Fuel',         color: 'rgb(96,165,250)'   },
  { key: 'total_compound_s',    label: 'Compound',     color: 'rgb(251,191,36)'   },
  { key: 'total_rubber_s',      label: 'Rubber',       color: 'rgb(234,179,8)'    },
  { key: 'total_ambient_s',     label: 'Ambient',      color: 'rgb(167,243,208)'  },
  { key: 'total_constructor_s', label: 'Constructor',  color: 'rgb(192,132,252)'  },
  { key: 'total_dirty_air_s',   label: 'Dirty Air',    color: 'rgb(244,114,182)'  },
  { key: 'total_skill_s',       label: 'Driver Skill', color: 'rgb(249,115,22)'   },
  { key: 'total_track_s',       label: 'Track Noise',  color: 'rgb(148,163,184)'  },
]

export function transform(row: RaceLostRow): RaceLostResult {
  let cumsum = 0
  const bars: WaterfallBar[] = COMPONENTS.map(({ key, label, color }) => {
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

  const componentSum = COMPONENTS.reduce((acc, { key }) => acc + (row[key] as number), 0)
  const closureGap = componentSum - row.total_pace_delta_s

  return {
    bars,
    totalPaceDelta: row.total_pace_delta_s,
    closureGap,
    nLaps: row.n_laps,
  }
}

export function toCsvRows(driverId: string, row: RaceLostRow): Record<string, unknown>[] {
  return COMPONENTS.map(({ key, label }) => ({
    driver_id: driverId,
    component: label,
    total_s: (row[key] as number).toFixed(4),
  }))
}
