// AX-07b live kinds (class T, transform-only; lineage in _evidence/ax-07-lineage/lineage.json):
//   season.teammate_gap     mart_driver_season_summary: teammate_gap_s (= the season rating) with its 95% CI
//                           (rating_s -/+ 1.96 x rating_se_s, ci_normal_95) and n_races. rank_separated_from_next
//                           travels in policy_fields, so a rank is never quoted without the CI test.
//   season.results          stg_results wins / podiums / classified / starts / DNFs per driver-season (AX-07 ruling 5).
//   corner_phase.season     mart_corner_skill_driver braking / mid-corner / exit skill with *_se_s (se_1 band).
//   race_control.pooled_rate pooled safety-car / VSC / red-flag / any-caution rate per season and all seasons.
//                           Pooled only: no per-circuit rate (the audit's forbidden chain).
// Held: data_quality.race and tyre_cliff_survival.profile live in heldStubs.ts (lineage verdict DA).
import { defineKind } from '../kinds'
import type { CardIndex, QueryRunner, ValueOutcome } from '../kinds'
import { summarisePooled, wilson } from '../../../features/race-control/transform'
import type { PooledRateRow } from '../../../features/race-control/queries'
import '../../../features/race-control/queries'
import type { CornerSeasonRow, SeasonRatingRow, SeasonResultsRow } from './queries'
import './queries'

const seasonsOf = async (index: CardIndex) => index.seasons.map((season) => ({ season }))

// ---------------------------------------------------------------- season.teammate_gap
export const seasonTeammateGap = defineKind<{ season: number }, SeasonRatingRow[]>({
  kind: 'season.teammate_gap',
  class: 'T',
  metric: 'teammate_gap_s',
  label: 'computed',
  unit: 's',
  intervalKind: 'ci_normal_95',
  intervalLevel: 0.95,
  nUnit: 'races',
  source: {
    mart: 'mart_driver_season_summary',
    columns: ['teammate_gap_s', 'ci_low', 'ci_high', 'n_races', 'teammate_id', 'rank_separated_from_next'],
    feature: null,
    query: 'cards.season-ratings',
    transform: null,
  },
  route: null,
  docsSlug: null,
  rev: 1,
  enumerate: async (index) => seasonsOf(index),
  compute: ({ season }, q) => q.run<SeasonRatingRow[]>('cards.season-ratings', { season }),
  refusal: (rows) => (rows.length ? null : 'no rows for this season in mart_driver_season_summary'),
  ids: ({ season }) => [`season.teammate_gap:${season}:*`],
  build({ season }, rows) {
    return rows.map((r) => {
      const base = {
        key: [season, r.driver_id],
        scope: { season, driver_id: r.driver_id },
        pageParams: {},
        policy_fields: {
          skill_measure: 'era_rating',
          shared_input_group: 'race_rating',
          rank_separated_from_next: r.rank_separated_from_next ?? null,
        },
      }
      if (r.teammate_gap_s === null || r.teammate_gap_s === undefined || !r.teammate_id) {
        return { ...base, value: null, display: null, n: 0, interval: null, unavailable_reason: 'not rated: no teammate pairing this season' }
      }
      if (r.ci_low === null || r.ci_high === null) {
        return { ...base, value: null, display: null, n: 0, interval: null, unavailable_reason: 'no interval: the season CI is missing, so no value is published' }
      }
      const v = r.teammate_gap_s
      return {
        ...base,
        value: v,
        display: `${v > 0 ? '+' : ''}${v.toFixed(3)} s/lap vs ${r.teammate_id} (${r.n_races} races)`,
        n: r.n_races,
        interval: { low: r.ci_low, high: r.ci_high, level: 0.95, source_columns: ['ci_low', 'ci_high'] },
      }
    })
  },
  pageParams: () => ({}),
  caveatRules: [{ code: 'AIR_STATE_FILTER', when: (o) => o.value !== null }],
  onScreen: () => [],
})

// ---------------------------------------------------------------- season.results
// AX-07 ruling 5: "how many races did X win" has a card. stg_results only (same source as race.result),
// never qv_driver_race.actual_finish_position. value = wins; the other counts travel in display.
export const seasonResults = defineKind<{ season: number }, SeasonResultsRow[]>({
  kind: 'season.results',
  class: 'T',
  metric: 'wins',
  label: 'measured',
  unit: 'races',
  intervalKind: 'none',
  intervalLevel: null,
  nUnit: 'races',
  source: {
    mart: 'stg_results',
    columns: ['finish_position', 'is_classified', 'status'],
    feature: null,
    query: 'cards.season-results',
    transform: null,
  },
  route: null,
  docsSlug: null,
  rev: 1,
  enumerate: async (index) => seasonsOf(index),
  compute: ({ season }, q) => q.run<SeasonResultsRow[]>('cards.season-results', { season }),
  refusal: (rows) => (rows.length ? null : 'no result rows for this season in stg_results'),
  ids: ({ season }) => [`season.results:${season}:*`],
  build({ season }, rows) {
    const pl = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`
    return rows.map((r) => ({
      key: [season, r.driver_id],
      scope: { season, driver_id: r.driver_id },
      value: r.wins,
      display: `${pl(r.wins, 'win')}, ${pl(r.podiums, 'podium')}, ${r.classified} classified finishes, ${pl(r.dnfs, 'DNF')} in ${pl(r.starts, 'start')} (${season})`,
      n: r.starts,
      interval: null,
      pageParams: {},
    }))
  },
  pageParams: () => ({}),
  caveatRules: [],
  onScreen: () => [],
})

// ---------------------------------------------------------------- corner_phase.season
const PHASES = [
  { phase: 'braking', v: 'braking_skill_s', se: 'braking_skill_se_s', n: 'braking_cells_n', label: 'braking' },
  { phase: 'mid_corner', v: 'mid_corner_skill_s', se: 'mid_corner_skill_se_s', n: 'mid_cells_n', label: 'mid-corner' },
  { phase: 'exit', v: 'exit_skill_s', se: 'exit_skill_se_s', n: 'exit_cells_n', label: 'exit' },
] as const

export const cornerPhaseSeason = defineKind<{ season: number }, CornerSeasonRow[]>({
  kind: 'corner_phase.season',
  class: 'T',
  metric: 'corner_phase_skill_s',
  label: 'computed',
  unit: 's',
  intervalKind: 'se_1',
  intervalLevel: null,
  nUnit: 'cells',
  source: {
    mart: 'mart_corner_skill_driver',
    columns: ['braking_skill_s', 'mid_corner_skill_s', 'exit_skill_s', 'braking_skill_se_s', 'mid_corner_skill_se_s', 'exit_skill_se_s', 'braking_cells_n', 'mid_cells_n', 'exit_cells_n'],
    feature: 'corner-phase-skill',
    query: 'cards.corner-skill',
    transform: null,
  },
  route: '/drivers/corner-skill',
  docsSlug: 'corner-phase-skill',
  rev: 1,
  enumerate: async (index) => seasonsOf(index),
  compute: ({ season }, q) => q.run<CornerSeasonRow[]>('cards.corner-skill', { season }),
  refusal: (rows) => (rows.length ? null : 'no rows for this season in mart_corner_skill_driver'),
  ids: ({ season }) => PHASES.map((p) => `corner_phase.season:${season}:*:${p.phase}`),
  build({ season }, rows) {
    return rows.flatMap((r) =>
      PHASES.map((p) => {
        const v = r[p.v]
        const se = r[p.se]
        const n = r[p.n]
        const base = {
          key: [season, r.driver_id, p.phase],
          scope: { season, driver_id: r.driver_id, constructor_id: r.constructor_id },
          pageParams: { season },
          policy_fields: { skill_measure: 'proxy_family' },
        }
        if (v === null || se === null || n === null || n === undefined) {
          return { ...base, value: null, display: null, n: 0, interval: null, unavailable_reason: `${p.label} skill or its SE is missing for this driver-season` }
        }
        return {
          ...base,
          value: v,
          display: `${p.label} ${v.toFixed(4)} s (SE ${se.toFixed(4)}, ${n} cells)`,
          n,
          interval: { low: v - se, high: v + se, level: null, source_columns: [p.v, p.se] },
        }
      }),
    )
  },
  pageParams: ({ season }) => ({ season }),
  caveatRules: [{ code: 'AIR_STATE_FILTER', when: (o) => o.value !== null }],
  onScreen: () => [],
})

// ---------------------------------------------------------------- race_control.pooled_rate
const RATES = [
  { variant: 'any_caution', name: 'any caution', r: 'races_with_caution' },
  { variant: 'safety_car', name: 'safety car', r: 'races_with_sc' },
  { variant: 'vsc', name: 'virtual safety car', r: 'races_with_vsc' },
  { variant: 'red_flag', name: 'red flag', r: 'races_with_red' },
] as const

export const racePooledRate = defineKind<Record<string, never>, PooledRateRow[]>({
  kind: 'race_control.pooled_rate',
  class: 'T',
  metric: 'pooled_caution_rate_per_race',
  label: 'measured',
  unit: 'share of races',
  intervalKind: 'wilson_95',
  intervalLevel: 0.95,
  nUnit: 'races',
  source: {
    mart: 'race_caution_timeline',
    columns: ['lap_number', 'caution_status', 'race_laps'],
    feature: 'race-control',
    query: 'race-control.pooled-rates',
    transform: 'race-control/transform.ts#summarisePooled',
  },
  route: '/race-craft/race-control',
  docsSlug: 'race-control',
  rev: 1,
  enumerate: async () => [{}],
  compute: (_p, q: QueryRunner) => q.run<PooledRateRow[]>('race-control.pooled-rates', {}),
  refusal: (rows) => (summarisePooled(rows) ? null : 'no pooled row in race_caution_timeline'),
  ids: () => RATES.map((r) => `race_control.pooled_rate:all:${r.variant}`),
  build(_p, rows) {
    const out: ValueOutcome[] = []
    for (const r of rows) {
      const scopeSeason = r.race_year
      const tag = scopeSeason === null ? 'all' : String(scopeSeason)
      for (const x of RATES) {
        const k = r[x.r]
        // The page's own Wilson function (race-control/transform.ts#wilson); [0, 0] when there are no races.
        const [low, high] = wilson(k, r.races)
        out.push({
          key: [tag, x.variant],
          scope: { season: scopeSeason },
          value: r.races ? k / r.races : 0,
          display: `${k} of ${r.races} races had a ${x.name} (${scopeSeason === null ? 'all seasons' : scopeSeason}, pooled over every circuit)`,
          n: r.races,
          interval: { low, high, level: 0.95, source_columns: [x.r, 'races'] },
          pageParams: (scopeSeason === null ? {} : { season: scopeSeason }) as Record<string, string | number>,
        })
      }
    }
    return out
  },
  pageParams: () => ({}),
  caveatRules: [],
  onScreen: () => [],
})

export const cardKinds = [seasonTeammateGap, seasonResults, cornerPhaseSeason, racePooledRate]
