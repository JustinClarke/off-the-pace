// AX-04 card kind for How the Race Was Lost: component totals per driver-race.
// Registered so the registry knows the kind, but EVERY row is refused (AX-04 finding 6):
//  - queryRaceLost selects only sums and n_laps, no interval, and a modelled card needs one.
//    Whether an interval source exists is for AX-07 / AX-15a / AX-15b (in v1 a held stub, AX-15a).
//  - Class DA: dirty_air_tax_s is inside total_explained_s and the skill bar (AX-07a lineage.md
//    sections 1 and 4); owner question Q1 asks whether the tax-free components are held too.
// compute() still runs the page's own query + transform so the parity test exercises it.
import { defineKind } from '../../assistant/cards/kinds'
import { transform } from './transform'
import type { RaceLostResult } from './transform'
import type { RaceLostRow } from './queries'
import './queries'

export interface RaceLostCardParams {
  season: number
  race_id: string
  driver_id: string
}

export interface RaceLostComputed {
  row: RaceLostRow | null
  result: RaceLostResult | null
}

/** Component variants, in the page's bar order (transform.ts COMPONENTS). */
export const RACE_LOST_COMPONENTS = ['fuel', 'compound', 'constructor', 'dirty_air', 'skill', 'track'] as const

export const RACE_LOST_REFUSAL =
  'no interval: race-lost.driver returns component sums and n_laps only, and a modelled card needs an interval ' +
  '(AX-04 finding 6; AX-07/AX-15a decide the interval source). Class DA: the dirty-air tax is inside ' +
  'total_explained_s and the skill bar.'

export const raceLostComponent = defineKind<RaceLostCardParams, RaceLostComputed>({
  kind: 'race_lost.component',
  class: 'DA',
  metric: 'race_lost_component_total_s',
  label: 'modelled',
  unit: 's',
  intervalKind: 'lap_noise_band',
  intervalLevel: null,
  nUnit: 'laps',
  source: {
    mart: 'fct_lap_residuals',
    columns: ['fuel_component_s', 'compound_component_s', 'constructor_component_s', 'dirty_air_tax_s', 'driver_skill_residual_s', 'track_unexplained_s'],
    feature: 'race-lost',
    query: 'race-lost.driver',
    transform: 'race-lost/transform.ts#transform',
  },
  route: '/lap-decomposition/race-lost',
  docsSlug: 'race-lost',
  rev: 1,
  async enumerate(index, q) {
    const out: RaceLostCardParams[] = []
    for (const { season, race_id } of index.races) {
      const drivers = await q.run<{ driver_id: string }[]>('race-lost.drivers', { season, raceId: race_id })
      for (const d of drivers) out.push({ season, race_id, driver_id: d.driver_id })
    }
    return out
  },
  async compute({ season, race_id, driver_id }, q) {
    const rows = await q.run<RaceLostRow[]>('race-lost.driver', { season, raceId: race_id, driverId: driver_id })
    const row = rows[0] ?? null
    return { row, result: row ? transform(row) : null }
  },
  refusal: () => RACE_LOST_REFUSAL,
  ids: ({ race_id, driver_id }) => RACE_LOST_COMPONENTS.map((c) => `race_lost.component:${race_id}:${driver_id}:${c}`),
  build: () => [],
  pageParams: ({ race_id, driver_id }) => ({ race: race_id, driver: driver_id }),
  caveatRules: [],
  onScreen: ({ race_id, driver_id }) => RACE_LOST_COMPONENTS.map((c) => `race_lost.component:${race_id}:${driver_id}:${c}`),
})

export const cardKinds = [raceLostComponent]
