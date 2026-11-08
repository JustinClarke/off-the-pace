// AX-07 race kinds on fixtures: a suppressed rating never becomes a value, an unrated race says
// why, thin and clean differ in n and interval, a relabelled interval kind fails validation.
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'

vi.mock('../../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../../data/manifest')>()),
  loadManifest: async () => ({ version: 'fx', generatedAt: '', tables: [], stats: { seasons_list: [] }, provenance: { label_version: 'v16' } }),
}))

const { buildCards } = await import('../build')
const { validateCard } = await import('../validate')
const { raceTeammateGap, raceResult, raceCoverage, driverRacePitStops, gapUnavailableReason } = await import('./raceKinds')
import type { QueryRunner } from '../kinds'
import type { CoverageRow, RatingRow, ResultRow } from './queries'

const res = (driver_id: string, o: Partial<ResultRow> = {}): ResultRow => ({
  race_id: '2099_1', race_year: 2099, driver_id, constructor_id: 'team', finish_position: 1, classified_position: '1',
  grid_position: 2, points: 25, status: 'Finished', is_classified: true, is_dnf: false, dnf_cause: null, ...o,
})
const rating = (driver_id: string, o: Partial<RatingRow>): RatingRow => ({
  race_id: '2099_1', driver_id, constructor_id: 'team', teammate_id: 'BBB', teammate_gap_s: -0.25, rating_s: -0.25,
  ci_low: -0.4, ci_high: -0.1, paired_lap_count: 40, rating_trust_label: 'ok', ci_unavailable_reason: null, ...o,
})
const cov = (coverage_reason = 'OK'): CoverageRow => ({
  race_id: '2099_1', race_year: 2099, n_lap_rows: 1000, n_rated_drivers: 20, has_rating: coverage_reason === 'OK',
  has_telemetry: true, rain_lap_share: 0, tyre_qa_status: 'ok', coverage_reason,
})

function runner(data: Record<string, unknown>): QueryRunner {
  return { run: async <T,>(name: string) => (data[name] ?? []) as T }
}
const P = { '2099_1': [{ season: 2099, race_id: '2099_1' }] }

async function build(spec: Parameters<typeof buildCards>[0] extends infer O ? O : never, data: Record<string, unknown>) {
  return buildCards({ ...spec, q: runner(data), index: { dataVersion: 'fx', seasons: [], races: [] } })
}

describe('AX-07 race.teammate_gap', () => {
  const data = {
    'cards.race-results': [res('OKK'), res('THN'), res('SUP'), res('NOR'), res('ALN')],
    'cards.race-ratings': [
      rating('OKK', {}),
      rating('THN', { paired_lap_count: 8, rating_trust_label: 'thin', ci_low: -0.9, ci_high: 0.3 }),
      rating('SUP', { paired_lap_count: 1, rating_trust_label: 'suppressed', ci_low: null, ci_high: null, teammate_gap_s: -6.617, rating_s: -6.617 }),
      rating('ALN', { teammate_id: null, teammate_gap_s: null }),
    ],
    'cards.race-coverage': [cov()],
  }

  it('ok and thin carry a value; suppressed and unrated are unavailable with a reason; all validate', async () => {
    const r = await build({ specs: [raceTeammateGap], params: { 'race.teammate_gap': P['2099_1'] } }, data)
    const by = Object.fromEntries(r.cards.map((c) => [c.scope.driver_id, c]))
    for (const c of r.cards) expect(validateCard(c, { expectedIntervalKind: 'ci_order_stat_median' }).errors).toEqual([])
    expect(by.OKK.value).toBe(-0.25)
    expect(by.OKK.n).toEqual({ count: 40, unit: 'laps' })
    expect(by.OKK.caveats).toEqual(['AIR_STATE_FILTER'])
    expect(by.OKK.versions.label_version).toBe('v16')
    expect(by.THN.n.count).toBeLessThan(by.OKK.n.count)
    expect(by.THN.interval!.high - by.THN.interval!.low).toBeGreaterThan(by.OKK.interval!.high - by.OKK.interval!.low)
    expect(by.THN.policy_fields.rating_trust_label).toBe('thin')
    expect(by.SUP).toMatchObject({ label: 'unavailable', value: null, display: null, interval: null, n: { count: 0, unit: 'laps' } })
    expect(by.SUP.unavailable_reason).toMatch(/^rated on 1 paired lap \(fewer than 6\)/)
    expect(JSON.stringify(by.SUP)).not.toContain('6.617')
    expect(by.NOR.unavailable_reason).toMatch(/no paired clean laps/)
    expect(by.ALN.unavailable_reason).toMatch(/no teammate pairing/)
    // AX-10b: teammate_id comes from the mart column, kept on unavailable cards that have one
    expect(by.OKK.policy_fields.teammate_id).toBe('BBB')
    expect(by.SUP.policy_fields.teammate_id).toBe('BBB')
    expect(by.NOR.policy_fields.teammate_id).toBeNull()
    expect(by.ALN.policy_fields.teammate_id).toBeNull()
    expect(r.ungrounded).toEqual([])
  })

  it('a count below 6 is suppressed even if the label says ok', () => {
    expect(gapUnavailableReason(rating('X', { paired_lap_count: 5, rating_trust_label: 'ok' }), cov())).toMatch(/^rated on 5 paired laps/)
  })

  it('an unrated race gives its coverage reason', () => {
    expect(gapUnavailableReason(undefined, cov('ALL_WET_NO_DRY_PAIRS'))).toMatch(/ALL_WET_NO_DRY_PAIRS.*wet race/)
  })

  it('an ok or thin rating with no CI is refused, never published without its interval', async () => {
    const r = await build(
      { specs: [raceTeammateGap], params: { 'race.teammate_gap': P['2099_1'] } },
      { ...data, 'cards.race-results': [res('OKK')], 'cards.race-ratings': [rating('OKK', { ci_low: null, ci_high: null })] },
    )
    expect(r.cards).toEqual([])
    expect(r.ungrounded[0].reason).toMatch(/invalid card: interval: null, but the registry declares "ci_order_stat_median"/)
  })

  it('relabelling the interval kind fails validation', async () => {
    const r = await build({ specs: [raceTeammateGap], params: { 'race.teammate_gap': P['2099_1'] } }, data)
    const ok = r.cards.find((c) => c.scope.driver_id === 'OKK')!
    const relabelled = { ...ok, interval: { ...ok.interval!, kind: 'ci_normal_95' as const } }
    expect(validateCard(relabelled, { expectedIntervalKind: raceTeammateGap.intervalKind }).ok).toBe(false)
  })
})

describe('AX-07 race.result, race.coverage, driver_race.pit_stops', () => {
  it('result: classified gives the position, a retirement gives the status; n is 1 race', async () => {
    const r = await build(
      { specs: [raceResult], params: { 'race.result': P['2099_1'] } },
      { 'cards.race-results': [res('AAA'), res('BBB', { is_classified: false, status: 'Engine', finish_position: 18, dnf_cause: 'mechanical', grid_position: 0 })] },
    )
    const by = Object.fromEntries(r.cards.map((c) => [c.scope.driver_id, c]))
    expect(by.AAA).toMatchObject({ value: 1, display: 'P1 from grid P2 (Finished, 25 pts)', label: 'measured', n: { count: 1, unit: 'races' } })
    expect(by.BBB).toMatchObject({ value: 'Engine', display: 'not classified: Engine (mechanical), from pit lane start' })
  })

  it('coverage: value is the reason code, n the lap rows', async () => {
    const r = await build({ specs: [raceCoverage], params: { 'race.coverage': P['2099_1'] } }, { 'cards.race-coverage': [cov('NO_TELEMETRY')] })
    expect(r.cards[0]).toMatchObject({ id: 'race.coverage:2099_1', value: 'NO_TELEMETRY', n: { count: 1000, unit: 'laps' } })
  })

  it('pit stops: count of observed stops, laps listed, n the stint laps; a race with no stints is refused', async () => {
    const r = await build(
      { specs: [driverRacePitStops], params: { 'driver_race.pit_stops': P['2099_1'] } },
      { 'cards.pit-stops': [{ driver_id: 'AAA', stints: 3, stint_laps: 51, stops: 2, stop_laps: '17,37', compounds: 'SOFT,HARD,SOFT' }] },
    )
    expect(r.cards[0]).toMatchObject({ value: 2, display: '2 stops (laps 17, 37); SOFT-HARD-SOFT', n: { count: 51, unit: 'laps' } })
    const empty = await build({ specs: [driverRacePitStops], params: { 'driver_race.pit_stops': P['2099_1'] } }, {})
    expect(empty.ungrounded.map((u) => u.reason)).toEqual(['no stints for this race in int_pit_strategy_value'])
  })
})
