import type { TeamAverageRow } from './queries'

export interface TeamAverageEntry {
  rank: number
  constructor: string
  drivers: number
  laps: number
  car_s: number | null
  dirty_air_s: number | null
  driver_skill_s: number | null
}

export function transform(rows: TeamAverageRow[]): TeamAverageEntry[] {
  return rows.map((r, i) => ({
    rank: i + 1,
    constructor: r.constructor_id,
    drivers: r.drivers_n,
    laps: r.laps_n,
    car_s: r.avg_car_component_s,
    dirty_air_s: r.avg_dirty_air_tax_s,
    driver_skill_s: r.avg_driver_skill_residual_s,
  }))
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
    rank: e.rank,
    constructor: e.constructor,
    drivers: e.drivers,
    laps: e.laps,
    car_component_avg_s: fmtOrBlank(e.car_s),
    dirty_air_tax_avg_s: fmtOrBlank(e.dirty_air_s),
    driver_skill_residual_avg_s: fmtOrBlank(e.driver_skill_s),
  }))
}
