// AX-15a: HELD stubs for the dirty-air-dependent (T*) card kinds (HD2 ruled C, 2026-11-07).
//
// A stub is one card per kind and scope: status held, value null, interval null, n.count 0, a held
// reason in plain words and a page link. The builder reads scope keys only (cards.stub-scopes over
// stg_results / mart_race_coverage), never a value column; source.columns is therefore always empty,
// so the lineage guard and the deny-list test can prove no price or residual column is declared.
// Classes: DA (value contains the taxed residual or the tax) or TRAFFIC (a price). Neither is live,
// so heldReasonFor() holds every card; spec.held also makes the reason survive a class going live
// (AX-15b flips specific kinds, AX-16 the price kinds).
import { defineKind } from '../kinds'
import type { AnySpec, CardClass } from '../kinds'
import type { NUnit } from '../card.types'
import type { StubGrain, StubScopeRow } from './queries'
import './queries'

const R_BREAKDOWN =
  'The time-loss breakdown includes the dirty-air term, a flat 0.331 s per lap estimate that has not been validated; held until wake calibration reports.'
const R_SECTOR = `${R_BREAKDOWN} Sector attribution also waits on CO-16.`
const R_GHOST = 'Built on ghost-car pace, which includes the unvalidated dirty-air term; held until wake calibration reports.'
const R_NET = 'Measured net of the unvalidated dirty-air term; held until wake calibration reports.'
const R_ISOLATION = 'Isolation prices thin-cell traffic with the flat dirty-air rule; held until wake calibration reports.'
const R_RESIDUAL = 'Built on the lap residual, which is net of the unvalidated dirty-air term; held until wake calibration reports.'
const R_CAR = 'The car term shares the dirty-air-adjusted residual; held until wake calibration reports.'
export const R_PRICE = 'Traffic cost is being re-measured; no number is available yet (dirty-air calibration).'
export const R_KM =
  'The tyre-life survival curve is a lower bound (pit stops end most stints before the cliff), and the stints it uses are chosen by a filter built on the unvalidated dirty-air residual; held until wake calibration reports.'
export const R_DQ =
  'Usable-lap and anomaly counts depend on the dirty-air air-state filter, so they are held until wake calibration reports.'

export interface StubDef {
  kind: string
  metric: string
  grain: StubGrain
  class: CardClass
  mart: string
  reason: string
  route: string
  docsSlug: string | null
  /** URL keys the route reads (nav/routeParams.ts) mapped from the scope. */
  params: ('season' | 'race' | 'race_id' | 'driver' | 'constructor' | 'compound')[]
  nUnit: NUnit
  priceKind?: boolean
  skillMeasure?: string
  /** policy_fields.shared_input_group, so NOT_INDEPENDENT_EVIDENCE can fire on cards of this kind (AX-07c / AX-21). */
  sharedInputGroup?: 'race_rating' | 'constructor_pace'
  /** Where the lineage verdict comes from. */
  why: string
}

export const STUBS: StubDef[] = [
  { kind: 'lap_waterfall.component', metric: 'lap_waterfall_components', grain: 'race_driver', class: 'DA', mart: 'fct_lap_residuals', reason: R_BREAKDOWN, route: '/lap-decomposition/waterfall', docsSlug: 'lap-waterfall', params: ['season', 'race', 'driver'], nUnit: 'laps', why: 'total_explained_s contains dirty_air_tax_s; skill is the remainder' },
  { kind: 'sector_decomposition.component', metric: 'sector_components', grain: 'race_driver', class: 'DA', mart: 'fct_lap_residuals', reason: R_SECTOR, route: '/lap-decomposition/sectors', docsSlug: 'sector-decomposition', params: ['season', 'race'], nUnit: 'laps', why: 'sector dirty air (WC)' },
  { kind: 'ghost_race.standings', metric: 'ghost_race_finish', grain: 'race_driver', class: 'DA', mart: 'fct_ghost_race_finish', reason: R_GHOST, route: '/ghost-car/standings', docsSlug: 'ghost-race-standings', params: [], nUnit: 'races', sharedInputGroup: 'race_rating', why: 'fct_ghost_car_pace / fct_ghost_race_finish carry dirty_air_tax_s' },
  { kind: 'counterfactual_championship.season', metric: 'counterfactual_points', grain: 'season_constructor', class: 'DA', mart: 'fct_ghost_race_finish', reason: R_GHOST, route: '/ghost-car/championship', docsSlug: 'counterfactual-championship', params: ['season', 'constructor'], nUnit: 'races', why: 'ghost-car pace includes the tax' },
  { kind: 'hidden_performance.season', metric: 'hidden_performance', grain: 'season_constructor', class: 'DA', mart: 'fct_ghost_race_finish', reason: R_GHOST, route: '/ghost-car/hidden', docsSlug: 'hidden-performance', params: ['season', 'constructor'], nUnit: 'races', why: 'ghost-car pace includes the tax' },
  { kind: 'race_driver.skill_components', metric: 'mean_component_s', grain: 'race_driver', class: 'DA', mart: 'mart_race_driver_summary', reason: R_NET, route: '/lap-decomposition/race-lost', docsSlug: 'race-lost', params: ['season', 'race', 'driver'], nUnit: 'laps', skillMeasure: 'lap_residual', why: 'race mart mean_*_component_s are net of the tax' },
  { kind: 'season_driver.skill_benchmark', metric: 'driver_skill_benchmark', grain: 'season_driver', class: 'DA', mart: 'mart_metric_benchmark', reason: R_NET, route: '/drivers/consistency', docsSlug: 'driver-consistency', params: ['season'], nUnit: 'rows', why: 'benchmark driver_skill and dirty_air rows are net of the tax' },
  { kind: 'driver_isolation.race', metric: 'isolated_pace', grain: 'race_driver', class: 'TRAFFIC', mart: 'fct_driver_isolation_race', reason: R_ISOLATION, route: '/aero/dirty-air', docsSlug: 'dirty-air-cost', params: ['season', 'race'], nUnit: 'laps', why: 'CO-30: thin cells priced with the flat rule (int_driver_isolation_lap_panel.sql:119-153)' },
  { kind: 'driver_isolation.stint', metric: 'isolated_pace_stint', grain: 'race_driver', class: 'TRAFFIC', mart: 'fct_driver_isolation_stint', reason: R_ISOLATION, route: '/aero/dirty-air', docsSlug: 'dirty-air-cost', params: ['season', 'race'], nUnit: 'stints', why: 'CO-30; stub is per (driver, race) because a stint id is a value-table key' },
  { kind: 'driver_consistency.season', metric: 'consistency', grain: 'season_driver', class: 'DA', mart: 'fct_driver_skill_features', reason: R_RESIDUAL, route: '/drivers/consistency', docsSlug: 'driver-consistency', params: ['season'], nUnit: 'laps', skillMeasure: 'consistency_residual', why: 'fct_driver_skill_features is built on the residual' },
  { kind: 'wet_race.specialist', metric: 'wet_race_skill', grain: 'season_driver', class: 'DA', mart: 'fct_driver_skill_features', reason: R_RESIDUAL, route: '/drivers/wet-race', docsSlug: 'wet-race-specialist', params: [], nUnit: 'races', skillMeasure: 'wet_proxy', why: 'built on the residual' },
  { kind: 'constructor_structural_pace.season', metric: 'constructor_component_s', grain: 'season_constructor', class: 'DA', mart: 'fct_constructor_structural_pace', reason: R_CAR, route: '/constructors/structural', docsSlug: 'constructor-structural-pace', params: ['season'], nUnit: 'races', sharedInputGroup: 'constructor_pace', why: 'constructor_component_s, CO-30' },
  { kind: 'party_mode.season', metric: 'party_mode_pace', grain: 'season_constructor', class: 'DA', mart: 'fct_constructor_structural_pace', reason: R_CAR, route: '/tyre-strategy/party-mode', docsSlug: 'party-mode', params: ['season'], nUnit: 'races', why: 'shares the car term' },
  { kind: 'constructor_circuit_interaction.season', metric: 'circuit_interaction', grain: 'season_constructor', class: 'DA', mart: 'fct_constructor_structural_pace', reason: R_CAR, route: '/constructors/circuits', docsSlug: 'constructor-circuit-interaction', params: [], nUnit: 'races', sharedInputGroup: 'constructor_pace', why: 'shares the car term' },
  { kind: 'constructor_team_averages.season', metric: 'team_average', grain: 'season_constructor', class: 'DA', mart: 'fct_constructor_structural_pace', reason: R_CAR, route: '/constructors/team-averages', docsSlug: 'constructor-team-averages', params: ['season'], nUnit: 'races', sharedInputGroup: 'constructor_pace', why: 'shares the car term' },
  { kind: 'dirty_air.price', metric: 'dirty_air_price', grain: 'race_driver', class: 'TRAFFIC', mart: 'int_dirty_air_tax_component', reason: R_PRICE, route: '/aero/dirty-air', docsSlug: 'dirty-air-cost', params: ['season', 'race'], nUnit: 'laps', priceKind: true, why: 'price_kind: the tax and cumulative tax stay held until AX-16 (rule 9)' },
  { kind: 'tyre_cliff_survival.profile', metric: 'km_cliff_survival_lower_bound', grain: 'race_compound', class: 'DA', mart: 'fct_cliff_prediction_features', reason: R_KM, route: '/tyre-strategy/survival', docsSlug: 'tyre-cliff-survival', params: ['season', 'race_id', 'compound'], nUnit: 'stints', why: 'stint filter anomaly_class IN (normal, clean_cliff) is built on the taxed residual (Q3: DA filter); the Kaplan-Meier curve is also a lower bound' },
  { kind: 'data_quality.race', metric: 'usable_laps', grain: 'race', class: 'DA', mart: 'mart_race_coverage', reason: R_DQ, route: '/data-quality', docsSlug: 'data-quality-audit', params: ['season'], nUnit: 'laps', why: 'lineage: usable_laps, pct_usable and anomaly_laps are dirty-air-dependent' },
]

function mk(d: StubDef) {
  return defineKind<{ grain: StubGrain }, StubScopeRow[]>({
    kind: d.kind,
    class: d.class,
    metric: d.metric,
    label: 'modelled',
    unit: null,
    intervalKind: 'none',
    intervalLevel: null,
    nUnit: d.nUnit,
    // columns stay empty on purpose: a stub declares no value column (AX-15a acceptance).
    source: { mart: d.mart, columns: [], feature: null, query: 'cards.stub-scopes', transform: null },
    route: d.route,
    docsSlug: d.docsSlug,
    held: d.reason,
    rev: 1,
    enumerate: async () => [{ grain: d.grain }],
    compute: ({ grain }, q) => q.run<StubScopeRow[]>('cards.stub-scopes', { grain }),
    refusal: (rows) => (rows.length ? null : `no scope rows for ${d.kind}`),
    ids: () => [`${d.kind}:*`],
    build(_p, rows) {
      return rows.map((r) => {
        // constructor_id is a display name in the published tables ('Toro Rosso'); ids may not contain spaces.
        const slug = r.constructor_id ? r.constructor_id.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') : null
        const key = [r.race_id ?? r.race_year, r.driver_id, slug, r.compound].filter((x): x is string | number => x !== null && x !== undefined)
        const entries: [string, string | number][] = []
        for (const k of d.params) {
          if (k === 'season') entries.push(['season', r.race_year])
          else if ((k === 'race' || k === 'race_id') && r.race_id) entries.push([k, r.race_id])
          else if (k === 'compound' && r.compound) entries.push(['compound', r.compound])
          else if (k === 'driver' && r.driver_id) entries.push(['driver', r.driver_id])
          else if (k === 'constructor' && r.constructor_id && /^[a-z][a-z0-9_]*$/.test(r.constructor_id)) entries.push(['constructor', r.constructor_id])
        }
        const pageParams: Record<string, string | number> = Object.fromEntries(entries)
        return {
          key,
          scope: { season: r.race_year, race_id: r.race_id, driver_id: r.driver_id, constructor_id: r.constructor_id, compound: r.compound ?? null },
          value: null,
          display: null,
          n: 0,
          interval: null,
          pageParams,
          policy_fields: {
            ...(d.skillMeasure ? { skill_measure: d.skillMeasure } : {}),
            ...(d.sharedInputGroup ? { shared_input_group: d.sharedInputGroup } : {}),
          },
        }
      })
    },
    pageParams: () => ({}),
    caveatRules: [],
    onScreen: () => [],
  })
}

export const stubKinds: AnySpec[] = STUBS.map(mk)
export const stubDefs = STUBS
