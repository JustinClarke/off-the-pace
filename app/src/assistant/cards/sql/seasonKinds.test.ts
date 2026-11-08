// AX-07b: live case, unavailable case and relabel guard for season.teammate_gap, corner_phase.season and
// race_control.pooled_rate (fixtures; the parity case is ../parity.07b.test.ts).
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'

vi.mock('../../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../../data/manifest')>()),
  loadManifest: async () => ({ version: 'test-version', generatedAt: '', tables: [], stats: { seasons_list: [2024] } }),
}))

const { buildCards } = await import('../build')
const { seasonTeammateGap, cornerPhaseSeason, racePooledRate } = await import('./seasonKinds')
import type { QueryRunner } from '../kinds'

const { summarisePooled } = await import('../../../features/race-control/transform')
const idx = { dataVersion: 'v', seasons: [2024], races: [] }

const qOf = (data: Record<string, unknown>): QueryRunner => ({ run: async (n) => data[n] as never })

describe('season.teammate_gap', () => {
  const rows = [
    { driver_id: 'VER', teammate_id: 'PER', teammate_gap_s: -0.356787, ci_low: -0.567976, ci_high: -0.145598, n_races: 22, rank_separated_from_next: false },
    { driver_id: 'NEW', teammate_id: null, teammate_gap_s: null, ci_low: null, ci_high: null, n_races: 1, rank_separated_from_next: null },
    { driver_id: 'ODD', teammate_id: 'XXX', teammate_gap_s: 0.1, ci_low: null, ci_high: null, n_races: 5, rank_separated_from_next: true },
  ]
  it('live card carries n, CI, caveat and rank_separated_from_next; the others are unavailable with a reason', async () => {
    const r = await buildCards({ specs: [seasonTeammateGap], q: qOf({ 'cards.season-ratings': rows }), index: idx })
    const by = Object.fromEntries(r.cards.map((c) => [c.id, c]))
    const v = by['season.teammate_gap:2024:VER']
    expect(v).toMatchObject({ status: 'active', value: -0.356787, n: { count: 22, unit: 'races' }, caveats: ['AIR_STATE_FILTER'] })
    expect(v.interval).toMatchObject({ kind: 'ci_normal_95', low: -0.567976, high: -0.145598 })
    expect(v.policy_fields).toMatchObject({ skill_measure: 'era_rating', rank_separated_from_next: false })
    expect(by['season.teammate_gap:2024:NEW']).toMatchObject({ label: 'unavailable', value: null, n: { count: 0 } })
    expect(by['season.teammate_gap:2024:NEW'].unavailable_reason).toMatch(/no teammate/)
    expect(by['season.teammate_gap:2024:ODD'].unavailable_reason).toMatch(/no interval/)
    expect(r.ungrounded).toEqual([])
  })
})

describe('corner_phase.season', () => {
  const rows = [
    { driver_id: 'GAS', constructor_id: 'Alpine', braking_skill_s: -0.1682, mid_corner_skill_s: -0.0412, exit_skill_s: -0.077, braking_skill_se_s: 0.021, mid_corner_skill_se_s: 0.0056, exit_skill_se_s: null, braking_cells_n: 280, mid_cells_n: 318, exit_cells_n: 237 },
  ]
  it('three phases per driver, se_1 band, n in cells; a missing SE is unavailable', async () => {
    const r = await buildCards({ specs: [cornerPhaseSeason], q: qOf({ 'cards.corner-skill': rows }), index: idx })
    const by = Object.fromEntries(r.cards.map((c) => [c.id, c]))
    const b = by['corner_phase.season:2024:GAS:braking']
    expect(b).toMatchObject({ value: -0.1682, n: { count: 280, unit: 'cells' }, page: { route: '/drivers/corner-skill', params: { season: 2024 } } })
    expect(b.interval).toMatchObject({ kind: 'se_1', source_columns: ['braking_skill_s', 'braking_skill_se_s'] })
    expect((b.interval?.high ?? 0) - (b.interval?.low ?? 0)).toBeCloseTo(0.042, 9)
    expect(b.caveats).toContain('AIR_STATE_FILTER')
    expect(by['corner_phase.season:2024:GAS:exit']).toMatchObject({ label: 'unavailable', value: null, n: { count: 0 } })
  })
})

describe('race_control.pooled_rate', () => {
  const pooled = [
    { race_year: 2024, races: 24, races_with_caution: 12, races_with_sc: 6, races_with_vsc: 5, races_with_red: 1, caution_laps: 100, total_laps: 1400 },
    { race_year: null, races: 24, races_with_caution: 12, races_with_sc: 6, races_with_vsc: 5, races_with_red: 1, caution_laps: 100, total_laps: 1400 },
  ]
  it('pooled per season and total, denominator in n, Wilson interval, no circuit scope', async () => {
    const r = await buildCards({ specs: [racePooledRate], q: qOf({ 'race-control.pooled-rates': pooled }), index: idx })
    expect(r.cards).toHaveLength(8)
    const sc = r.cards.find((c) => c.id === 'race_control.pooled_rate:all:safety_car')!
    expect(sc).toMatchObject({ value: 0.25, n: { count: 24, unit: 'races' }, label: 'measured' })
    expect(sc.scope.season).toBeNull()
    expect(sc.scope.circuit_id).toBeNull()
    // AX-07c: the interval is the page's own wilson(), carried with kind wilson_95 at level 0.95.
    const summary = summarisePooled(pooled as never)!
    expect(sc.interval).toMatchObject({ kind: 'wilson_95', level: 0.95, source_columns: ['races_with_sc', 'races'] })
    expect(sc.interval!.low).toBe(summary.safetyCar.lo)
    expect(sc.interval!.high).toBe(summary.safetyCar.hi)
    expect(sc.interval!.low).toBeLessThan(sc.value as number)
    expect(sc.interval!.high).toBeGreaterThan(sc.value as number)
    for (const [id, s] of [['any_caution', summary.anyCaution], ['vsc', summary.vsc], ['red_flag', summary.redFlag]] as const) {
      const c = r.cards.find((x) => x.id === `race_control.pooled_rate:all:${id}`)!
      expect([c.interval!.low, c.interval!.high]).toEqual([s.lo, s.hi])
    }
    expect(sc.display).toMatch(/pooled over every circuit/)
  })
  it('refuses when there is no total row', async () => {
    const r = await buildCards({ specs: [racePooledRate], q: qOf({ 'race-control.pooled-rates': [] }), index: idx })
    expect(r.cards).toEqual([])
    expect(r.ungrounded.length).toBeGreaterThan(0)
  })
})
