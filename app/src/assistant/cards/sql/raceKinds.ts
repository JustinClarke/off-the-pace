// AX-07 race-grain card kinds: the demo question "how did driver D do against their teammate in
// race R, and what explains it?" answered from transform-only (class T) sources.
//
//   race.result            stg_results (finish, grid, status, points). Not laps_completed.
//   race.teammate_gap      mart_race_driver_summary teammate_gap_s, n = paired_lap_count, TX-01 CI
//                          (ci_order_stat_median), rating_trust_label. A suppressed rating (fewer than
//                          6 paired laps) is NEVER a value: the card is unavailable, "rated on k paired laps".
//   race.coverage          mart_race_coverage.coverage_reason (TX-02): why a race is or is not rated.
//   race.cautions          the race-control page's own query + transform (caution laps, runs).
//   driver_race.pit_stops  observed stops (actual_pit_lap, from stg_pits via int_pit_strategy_value).
//
// Lineage: _roadmap/_ai-integration/_evidence/ax-07-lineage/lineage.json. teammate_gap_s, its CI and
// paired n use int_lap_air_state only to choose laps (the rain filter through int_track_evolution),
// so they are T with the AIR_STATE_FILTER caveat (HD13). Nothing here reads a dirty-air column,
// a decomposition component or the taxed residual.
import { defineKind } from '../kinds'
import type { CardIndex, QueryRunner } from '../kinds'
import { transform as cautionTransform } from '../../../features/race-control/transform'
import type { CautionLapRow } from '../../../features/race-control/queries'
import '../../../features/race-control/queries'
import type { CoverageRow, PitStopRow, RatingRow, ResultRow } from './queries'
import './queries'

export interface RaceParams {
  season: number
  race_id: string
}

/** TX-01: below this many paired laps the CI is NULL and the rating is suppressed. */
export const MIN_PAIRED_LAPS = 6
/** Display precision for the gap and its CI (the mart is at millisecond precision). */
export const GAP_DECIMALS = 3

export const COVERAGE_TEXT: Record<string, string> = {
  OK: 'rated: telemetry, dry pairs and tyre data present',
  NO_RACING_LAPS: 'no valid racing laps, so nothing is rated',
  ALL_WET_NO_DRY_PAIRS: 'wet race: no dry paired laps, so no driver is rated',
  NO_TELEMETRY: 'no position telemetry: lap times rate, but the air-state lap filters could not run',
  TYRE_QA_QUARANTINED: 'tyre data quarantined: tyre-based numbers are withheld',
  TYRE_LIFE_PARTIAL: 'tyre life partly missing: tyre-based numbers are thin',
}

async function coverageRaces(_index: CardIndex, q: QueryRunner): Promise<RaceParams[]> {
  const rows = await q.run<{ race_year: number; race_id: string }[]>('cards.coverage-races', {})
  return rows.map((r) => ({ season: r.race_year, race_id: r.race_id }))
}

const raceScope = ({ season, race_id }: RaceParams) => ({ season, race_id })
const fmtGap = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(GAP_DECIMALS)}`
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`

// ---------------------------------------------------------------- race.result
export const raceResult = defineKind<RaceParams, ResultRow[]>({
  kind: 'race.result',
  class: 'T',
  metric: 'finish_position',
  label: 'measured',
  unit: 'position',
  intervalKind: 'none',
  intervalLevel: null,
  nUnit: 'races',
  source: {
    mart: 'stg_results',
    columns: ['finish_position', 'classified_position', 'grid_position', 'status', 'is_classified', 'points'],
    feature: null,
    query: 'cards.race-results',
    transform: null,
  },
  route: null,
  docsSlug: null,
  rev: 1,
  enumerate: coverageRaces,
  compute: ({ race_id }, q) => q.run<ResultRow[]>('cards.race-results', { race_id }),
  refusal: (rows) => (rows.length ? null : 'no result rows for this race in stg_results'),
  ids: ({ race_id }) => [`race.result:${race_id}:*`],
  build(p, rows) {
    return rows.map((r) => {
      const grid = r.grid_position === null ? 'grid unknown' : r.grid_position === 0 ? 'pit lane start' : `grid P${r.grid_position}`
      const classified = r.is_classified === true && r.finish_position !== null
      const value = classified ? r.finish_position : (r.status ?? 'not classified')
      const display = classified
        ? `P${r.finish_position} from ${grid} (${r.status ?? 'finished'}, ${r.points ?? 0} pts)`
        : `not classified: ${r.status ?? 'unknown'}${r.dnf_cause ? ` (${r.dnf_cause})` : ''}, from ${grid}`
      return {
        key: [p.race_id, r.driver_id],
        scope: { ...raceScope(p), driver_id: r.driver_id, constructor_id: r.constructor_id },
        value,
        display,
        n: 1,
        interval: null,
        pageParams: {},
      }
    })
  },
  pageParams: () => ({}),
  caveatRules: [],
  onScreen: () => [],
})

// ---------------------------------------------------------------- race.teammate_gap
export interface GapComputed {
  results: ResultRow[]
  ratings: RatingRow[]
  coverage: CoverageRow | null
}

/** Why a driver-race has no gap value, or null when it may carry one. Exported for the tests. */
export function gapUnavailableReason(r: RatingRow | undefined, coverage: CoverageRow | null): string | null {
  if (!r) {
    // Race-level reason only when the race has no rating at all; otherwise this driver had no pairs.
    if (coverage && coverage.coverage_reason !== 'OK' && !coverage.has_rating) {
      return `not rated: race coverage ${coverage.coverage_reason} (${COVERAGE_TEXT[coverage.coverage_reason] ?? 'see race.coverage'})`
    }
    const note = coverage && coverage.coverage_reason !== 'OK' ? ` (race coverage ${coverage.coverage_reason})` : ''
    return `not rated: no paired clean laps with a teammate in this race${note}`
  }
  const k = r.paired_lap_count
  if (k === null || k === undefined) return 'not rated: paired lap count missing'
  // Suppressed by label OR by count: the card never trusts one without the other.
  if (r.rating_trust_label === 'suppressed' || k < MIN_PAIRED_LAPS) {
    return `rated on ${plural(k, 'paired lap')} (fewer than ${MIN_PAIRED_LAPS}): suppressed, no value`
  }
  if (!r.teammate_id) return 'no teammate pairing in this race'
  if (r.teammate_gap_s === null || r.teammate_gap_s === undefined) return 'not rated: teammate_gap_s is null'
  return null
}

export const raceTeammateGap = defineKind<RaceParams, GapComputed>({
  kind: 'race.teammate_gap',
  class: 'T',
  metric: 'teammate_gap_s',
  label: 'computed',
  unit: 's',
  intervalKind: 'ci_order_stat_median',
  intervalLevel: 0.95,
  nUnit: 'laps',
  source: {
    mart: 'mart_race_driver_summary',
    columns: ['teammate_gap_s', 'teammate_id', 'ci_low', 'ci_high', 'paired_lap_count', 'rating_trust_label'],
    feature: null,
    query: 'cards.race-ratings',
    transform: null,
  },
  route: null,
  docsSlug: null,
  rev: 1,
  enumerate: coverageRaces,
  async compute({ race_id }, q) {
    const [results, ratings, cov] = await Promise.all([
      q.run<ResultRow[]>('cards.race-results', { race_id }),
      q.run<RatingRow[]>('cards.race-ratings', { race_id }),
      q.run<CoverageRow[]>('cards.race-coverage', { race_id }),
    ])
    return { results, ratings, coverage: cov[0] ?? null }
  },
  refusal: ({ results }) => (results.length ? null : 'no result rows for this race in stg_results'),
  ids: ({ race_id }) => [`race.teammate_gap:${race_id}:*`],
  build(p, { results, ratings, coverage }) {
    const byDriver = new Map(ratings.map((r) => [r.driver_id, r]))
    return results.map((res) => {
      const r = byDriver.get(res.driver_id)
      const why = gapUnavailableReason(r, coverage)
      const base = {
        key: [p.race_id, res.driver_id],
        scope: { ...raceScope(p), driver_id: res.driver_id, constructor_id: res.constructor_id },
        pageParams: {},
        policy_fields: {
          rating_trust_label: r?.rating_trust_label ?? null,
          skill_measure: 'teammate_paired_median',
          shared_input_group: 'race_rating',
          coverage_reason: coverage?.coverage_reason ?? null,
          teammate_id: r?.teammate_id ?? null,
        },
      }
      if (why || !r) return { ...base, value: null, display: null, n: 0, interval: null, unavailable_reason: why ?? 'not rated' }
      // Raw mart values (no pre-rounding: rounding to 4 dp then displaying at 3 dp would double-round
      // a half-millisecond median). The model projection trims float noise (6 significant digits).
      const v = r.teammate_gap_s as number
      const interval =
        r.ci_low === null || r.ci_high === null ? null : { low: r.ci_low, high: r.ci_high, level: 0.95, source_columns: ['ci_low', 'ci_high'] }
      const notes = [`median of ${r.paired_lap_count} paired laps`]
      if (r.rating_trust_label === 'thin') notes.push('thin')
      if (coverage?.coverage_reason === 'NO_TELEMETRY') notes.push('no telemetry: rain filter did not run')
      return {
        ...base,
        value: v,
        display: `${fmtGap(v)} s/lap vs ${r.teammate_id} (${notes.join('; ')})`,
        n: r.paired_lap_count,
        interval,
      }
    })
  },
  pageParams: () => ({}),
  caveatRules: [{ code: 'AIR_STATE_FILTER', when: (o) => o.value !== null }],
  onScreen: () => [],
})

// ---------------------------------------------------------------- race.coverage
export const raceCoverage = defineKind<RaceParams, CoverageRow | null>({
  kind: 'race.coverage',
  class: 'T',
  metric: 'coverage_reason',
  label: 'measured',
  unit: null,
  intervalKind: 'none',
  intervalLevel: null,
  nUnit: 'laps',
  source: {
    mart: 'mart_race_coverage',
    columns: ['coverage_reason', 'n_lap_rows', 'n_rated_drivers', 'has_rating', 'has_telemetry'],
    feature: null,
    query: 'cards.race-coverage',
    transform: null,
  },
  route: null,
  docsSlug: null,
  rev: 1,
  enumerate: coverageRaces,
  compute: async ({ race_id }, q) => (await q.run<CoverageRow[]>('cards.race-coverage', { race_id }))[0] ?? null,
  refusal: (c) => (c ? null : 'no row for this race in mart_race_coverage'),
  ids: ({ race_id }) => [`race.coverage:${race_id}`],
  build(p, c) {
    if (!c) return []
    return [
      {
        key: [p.race_id],
        scope: raceScope(p),
        value: c.coverage_reason,
        display: `${c.coverage_reason}: ${COVERAGE_TEXT[c.coverage_reason] ?? c.coverage_reason} (${plural(c.n_rated_drivers, 'rated driver')})`,
        n: c.n_lap_rows,
        interval: null,
        pageParams: {},
        policy_fields: { coverage_reason: c.coverage_reason },
      },
    ]
  },
  pageParams: () => ({}),
  caveatRules: [],
  onScreen: () => [],
})

// ---------------------------------------------------------------- race.cautions
const CAUTION_QUERY = 'race-control.timeline'
const KIND_SHORT = { safety_car: 'SC', vsc: 'VSC', red_flag: 'red flag' } as const

export const raceCautions = defineKind<RaceParams, ReturnType<typeof cautionTransform>>({
  kind: 'race.cautions',
  class: 'T',
  metric: 'caution_laps',
  label: 'measured',
  unit: 'laps',
  intervalKind: 'none',
  intervalLevel: null,
  nUnit: 'laps',
  source: {
    mart: 'race_caution_timeline',
    columns: ['lap_number', 'caution_status', 'race_laps'],
    feature: 'race-control',
    query: CAUTION_QUERY,
    transform: 'race-control/transform.ts#transform',
  },
  route: '/race-craft/race-control',
  docsSlug: 'race-control',
  rev: 1,
  enumerate: coverageRaces,
  async compute({ season, race_id }, q) {
    return cautionTransform(await q.run<CautionLapRow[]>(CAUTION_QUERY, { season, raceId: race_id }))
  },
  refusal: (t) => (t.raceLaps > 0 ? null : 'no lap rows for this race in race_caution_timeline'),
  ids: ({ race_id }) => [`race.cautions:${race_id}`],
  build(p, t) {
    const runs = t.segments.map((s) => `${KIND_SHORT[s.kind]} ${s.startLap === s.endLap ? `lap ${s.startLap}` : `laps ${s.startLap}-${s.endLap}`}`)
    return [
      {
        key: [p.race_id],
        scope: raceScope(p),
        value: t.cautionLaps,
        display: `${t.cautionLaps} of ${t.raceLaps} laps under caution${runs.length ? `: ${runs.join(', ')}` : ''}`,
        n: t.raceLaps,
        interval: null,
        pageParams: { season: p.season, race_id: p.race_id },
      },
    ]
  },
  pageParams: (p) => ({ season: p.season, race_id: p.race_id }),
  caveatRules: [],
  onScreen: ({ race_id }) => [`race.cautions:${race_id}`],
})

// ---------------------------------------------------------------- driver_race.pit_stops
export const driverRacePitStops = defineKind<RaceParams, PitStopRow[]>({
  kind: 'driver_race.pit_stops',
  class: 'T',
  metric: 'pit_stops',
  label: 'measured',
  unit: 'stops',
  intervalKind: 'none',
  intervalLevel: null,
  nUnit: 'laps',
  source: {
    mart: 'int_pit_strategy_value',
    columns: ['actual_pit_lap', 'compound', 'stint_length_laps', 'end_lap_number'],
    feature: 'pit-strategy',
    query: 'cards.pit-stops',
    transform: null,
  },
  route: '/tyre-strategy/pit-gantt',
  docsSlug: 'pit-strategy',
  rev: 1,
  enumerate: coverageRaces,
  compute: ({ race_id }, q) => q.run<PitStopRow[]>('cards.pit-stops', { race_id }),
  refusal: (rows) => (rows.length ? null : 'no stints for this race in int_pit_strategy_value'),
  ids: ({ race_id }) => [`driver_race.pit_stops:${race_id}:*`],
  build(p, rows) {
    return rows.map((r) => ({
      key: [p.race_id, r.driver_id],
      scope: { ...raceScope(p), driver_id: r.driver_id },
      value: r.stops,
      display: `${plural(r.stops, 'stop')}${r.stop_laps ? ` (lap${r.stops === 1 ? '' : 's'} ${r.stop_laps.split(',').join(', ')})` : ''}; ${(r.compounds ?? '').split(',').join('-')}`,
      n: r.stint_laps,
      interval: null,
      pageParams: { season: p.season, race_id: p.race_id },
    }))
  },
  pageParams: (p) => ({ season: p.season, race_id: p.race_id }),
  caveatRules: [],
  onScreen: () => [],
})

export const cardKinds = [raceResult, raceTeammateGap, raceCoverage, raceCautions, driverRacePitStops]
