import type { TeamAverageRow } from './queries'

export interface TeamAverageEntry {
  /** Position among teams with a measured car term; null when the team has none. */
  rank: number | null
  constructor: string
  drivers: number
  laps: number
  car_s: number | null
  constructor_measured_laps_n: number
  constructor_filled_share: number
  /** NULL (unavailable) when no lap of the team-season has a measured dirty-air value. Never 0 for unmeasured. */
  dirty_air_s: number | null
  n_dirty_air_laps: number
  driver_skill_s: number | null
}

export function transform(rows: TeamAverageRow[]): TeamAverageEntry[] {
  // Rank counts only teams with a measured car term; rows arrive sorted, NULL last.
  let nextRank = 1
  return rows.map(r => {
    const car = Number(r.constructor_measured_laps_n ?? 0) > 0 ? r.avg_car_component_s : null
    return {
    rank: car === null ? null : nextRank++,
    constructor: r.constructor_id,
    drivers: r.drivers_n,
    laps: r.laps_n,
    car_s: car,
    constructor_measured_laps_n: Number(r.constructor_measured_laps_n ?? 0),
    constructor_filled_share: Number(r.constructor_filled_share ?? 1),
    dirty_air_s: (r.n_dirty_air_laps ?? 0) > 0 ? r.avg_dirty_air_tax_s : null,
    n_dirty_air_laps: Number(r.n_dirty_air_laps ?? 0),
    driver_skill_s: r.avg_driver_skill_residual_s,
    }
  })
}

export interface RaceValue {
  race: string
  value: number
}

/** Mean of per-race values: each race counts once, however many laps or drivers it has. */
export function meanOfRaces(values: RaceValue[]): number | null {
  const byRace = new Map<string, number[]>()
  for (const v of values) byRace.set(v.race, [...(byRace.get(v.race) ?? []), v.value])
  if (byRace.size === 0) return null
  const raceMeans = [...byRace.values()].map(xs => xs.reduce((a, b) => a + b, 0) / xs.length)
  return raceMeans.reduce((a, b) => a + b, 0) / raceMeans.length
}

const fmtOrBlank = (v: number | null) => (v === null ? '' : v.toFixed(3))

export function toCsvRows(entries: TeamAverageEntry[]): Record<string, unknown>[] {
  return entries.map(e => ({
    rank: e.rank === null ? '' : e.rank,
    constructor: e.constructor,
    drivers: e.drivers,
    laps: e.laps,
    car_component_avg_s: fmtOrBlank(e.car_s),
    constructor_measured_laps_n: e.constructor_measured_laps_n,
    constructor_filled_share: e.constructor_filled_share.toFixed(3),
    dirty_air_tax_avg_s: fmtOrBlank(e.dirty_air_s),
    driver_skill_residual_avg_s: fmtOrBlank(e.driver_skill_s),
  }))
}
