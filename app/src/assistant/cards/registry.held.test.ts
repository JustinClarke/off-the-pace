// AX-15a: every dirty-air-dependent (T*) kind is published as a HELD stub: no value, n.count 0, a held
// reason, a page link that the AX-03 route table accepts.
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'

vi.mock('../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../data/manifest')>()),
  loadManifest: async () => ({ version: 'test-version', generatedAt: '', tables: [], stats: { seasons_list: [] } }),
}))

const { registry, classesLive, heldReasonFor, registryHash } = await import('./registry')
const { buildCards } = await import('./build')
const { validateCard } = await import('./validate')
const { stubDefs, stubKinds } = await import('./sql/heldStubs')
const { routeParams } = await import('../../nav/routeParams')
import type { QueryRunner } from './kinds'

export const SCOPES = {
  race: [{ race_year: 2024, race_id: '2024_1', driver_id: null, constructor_id: null }],
  race_driver: [{ race_year: 2024, race_id: '2024_1', driver_id: 'VER', constructor_id: 'Red Bull' }],
  race_compound: [{ race_year: 2024, race_id: '2024_1', driver_id: null, constructor_id: null, compound: 'SOFT' }],
  season_driver: [{ race_year: 2024, race_id: null, driver_id: 'VER', constructor_id: null }],
  season_constructor: [{ race_year: 2024, race_id: null, driver_id: null, constructor_id: 'Red Bull' }],
}
export const fakeQ: QueryRunner = {
  run: async (_n, p) => SCOPES[(p as { grain: keyof typeof SCOPES }).grain] as never,
}

describe('AX-15a held stubs', () => {
  it('covers the whole table (18 kinds), all registered', () => {
    expect(stubDefs).toHaveLength(18)
    for (const d of stubDefs) expect(registry.some((s) => s.kind === d.kind), d.kind).toBe(true)
  })

  it.each(stubDefs.map((d) => [d.kind, d] as const))('%s: held in every class setting, no value, valid, page link', async (_k, d) => {
    const spec = stubKinds.find((s) => s.kind === d.kind)!
    expect(spec.class === 'T').toBe(false)
    expect(heldReasonFor(spec, ['T', 'T-F', 'DA', 'TRAFFIC', 'ML'])).toBe(d.reason)
    expect(d.reason.length).toBeGreaterThan(20)
    expect(Object.keys(routeParams)).toContain(d.route)
    for (const k of d.params) expect(Object.keys(routeParams[d.route]), `${d.route} reads ${k}`).toContain(k)
    const r = await buildCards({ specs: [spec], q: fakeQ, index: { dataVersion: 'v', seasons: [], races: [] }, classesLive: ['T', 'DA', 'TRAFFIC', 'ML'] })
    expect(r.cards.length).toBe(1)
    expect(r.ungrounded).toEqual([])
    const c = r.cards[0]
    expect(c).toMatchObject({ status: 'held', value: null, display: null, interval: null, n: { count: 0 }, held_reason: d.reason })
    expect(c.page?.route).toBe(d.route)
    expect(c.source.columns).toEqual([])
    expect(validateCard(c, { expectedIntervalKind: 'none' }).ok).toBe(true)
    expect(c.versions.registry).toBe(registryHash)
  })

  it('classesLive is still [T]: nothing dirty-air-dependent can go live in v1', () => {
    expect(classesLive).toEqual(['T'])
  })

  it('data_quality.race is HELD with the dirty-air reason (lineage)', () => {
    const d = stubDefs.find((x) => x.kind === 'data_quality.race')!
    expect(d.reason).toMatch(/dirty-air/)
  })
})

describe('AX-15a HELD_CARD_WORDING on a stub fixture', () => {
  it('fires on a stub, fails a draft that quotes a number, passes the held wording', async () => {
    const { checkAnswer } = await import('../honesty/checker')
    const { toCheckerCard } = await import('./project')
    const r = await buildCards({ specs: [stubKinds[0]], q: fakeQ, index: { dataVersion: 'v', seasons: [], races: [] } })
    const fc = toCheckerCard(r.cards[0])
    const bad = checkAnswer({ answer: 'VER lost roughly 0.3 s per lap to traffic.', cards: [fc] })
    expect(bad.results.find((x) => x.code === 'HELD_CARD_WORDING')?.verdict).toBe('fail')
    const good = checkAnswer({
      answer: 'That figure is held and not available yet: it waits on wake calibration, so I will not quote a number.',
      cards: [fc],
    })
    expect(good.results.find((x) => x.code === 'HELD_CARD_WORDING')?.verdict).toBe('pass')
  })
})

describe('AX-07c shared_input_group on held stubs (NOT_INDEPENDENT_EVIDENCE)', () => {
  it('pairing two constructor_pace stubs fires it; one stub, or a stub from another group, does not', async () => {
    const { toCheckerCard } = await import('./project')
    const { checkRule, policy } = await import('../honesty/checker')
    const rule = policy.rules.find((r) => r.code === 'NOT_INDEPENDENT_EVIDENCE')!
    const card = async (kind: string) => {
      const spec = stubKinds.find((s) => s.kind === kind)!
      const r = await buildCards({ specs: [spec], q: fakeQ, index: { dataVersion: 'v', seasons: [], races: [] }, classesLive: ['T'] })
      return r.cards[0]
    }
    const group = async (kind: string) => (await card(kind)).policy_fields.shared_input_group
    expect(await group('constructor_structural_pace.season')).toBe('constructor_pace')
    expect(await group('constructor_circuit_interaction.season')).toBe('constructor_pace')
    expect(await group('constructor_team_averages.season')).toBe('constructor_pace')
    expect(await group('ghost_race.standings')).toBe('race_rating')
    const fire = async (...kinds: string[]) =>
      checkRule(rule, { answer: 'x', cards: await Promise.all(kinds.map(async (k) => toCheckerCard(await card(k)))) }).verdict
    expect(await fire('constructor_structural_pace.season', 'constructor_team_averages.season')).not.toBe('not_fired')
    expect(await fire('constructor_structural_pace.season', 'constructor_circuit_interaction.season')).not.toBe('not_fired')
    expect(await fire('constructor_structural_pace.season')).toBe('not_fired')
    expect(await fire('constructor_structural_pace.season', 'ghost_race.standings')).toBe('not_fired')
  })
})
