// AX-04 registry guards: no chance-line source, no publishable kind whose class is not live,
// registryHash stable and sensitive, buildCards never emits a card validateCard rejects.
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

vi.mock('../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../data/manifest')>()),
  loadManifest: async () => ({ version: 'test-version', generatedAt: '', tables: [], stats: { seasons_list: [] } }),
}))

const { registry, registryHash, computeRegistryHash, classesLive, forbiddenSourceOf, assertSpecs, heldReasonFor } = await import('./registry')
const { buildCards, assembleCard } = await import('./build')
const { stubKinds } = await import('./sql/heldStubs')
const { validateCard } = await import('./validate')
const { defineKind } = await import('./kinds')
const { intervalKindValues, nUnitValues } = await import('./card.types')
import type { AnySpec, QueryRunner, ValueOutcome } from './kinds'

const FEATURES = join(import.meta.dirname, '..', '..', 'features')

const versions = { data_version: 'v', label_version: null, model_version: null, card_schema: '1' as const, registry: registryHash }

function fakeSpec(over: Partial<AnySpec> = {}, outcomes: ValueOutcome[] = []): AnySpec {
  return defineKind<{ k: string }, null>({
    kind: 'test.kind',
    class: 'T',
    metric: 'm',
    label: 'modelled',
    unit: 's',
    intervalKind: 'ci_normal_95',
    intervalLevel: 0.95,
    nUnit: 'races',
    source: { mart: 'some_mart', columns: ['c'], feature: null, query: null, transform: null },
    route: null,
    docsSlug: null,
    rev: 1,
    enumerate: async () => [{ k: 'a' }],
    compute: async () => null,
    refusal: () => null,
    ids: () => [],
    build: () => outcomes,
    pageParams: () => ({}),
    caveatRules: [],
    onScreen: () => [],
    ...over,
  } as AnySpec)
}

const goodOutcome: ValueOutcome = {
  key: [2024, 'LEC'],
  scope: { season: 2024, driver_id: 'LEC' },
  value: -0.1,
  display: '-0.10s',
  n: 24,
  interval: { low: -0.3, high: 0.1, level: 0.95, source_columns: ['lo', 'hi'] },
  pageParams: {},
}

describe('AX-04 registry', () => {
  it('registers the v1 kinds (AX-04 three + AX-07 race kinds and held pit kinds)', () => {
    const stubs = new Set(stubKinds.map((s) => s.kind)) // AX-15a held stubs: registry.held.test.ts
    expect(registry.map((s) => s.kind).filter((k) => !stubs.has(k)).sort()).toEqual([
      'corner_phase.season', 'driver_race.pit_stops', 'era_rating.season', 'pit_strategy.opportunity_cost', 'pit_strategy.optimal_lap',
      'pit_strategy.verdict', 'race.cautions', 'race.coverage', 'race.result', 'race.teammate_gap', 'race_control.pooled_rate', 'race_lost.component', 'season.results', 'season.teammate_gap',
    ])
  })

  it('declares valid interval kinds and n units; era uses ci_normal_95, never ci_bayes', () => {
    for (const s of registry) {
      expect(intervalKindValues).toContain(s.intervalKind)
      expect(nUnitValues).toContain(s.nUnit)
    }
    expect(registry.find((s) => s.kind === 'era_rating.season')?.intervalKind).toBe('ci_normal_95')
  })

  it('no kind reads flag_chance_lookup.json (spec fields or feature sources)', () => {
    for (const s of registry) {
      expect(forbiddenSourceOf(s), s.kind).toBeNull()
      const feature = s.source.feature
      if (!feature) continue
      for (const f of ['queries.ts', 'cards.ts', 'transform.ts']) {
        const p = join(FEATURES, feature, f)
        if (existsSync(p)) expect(readFileSync(p, 'utf8'), `${feature}/${f}`).not.toMatch(/flag_chance_lookup/i)
      }
    }
    expect(() => assertSpecs([fakeSpec({ source: { mart: 'flag_chance_lookup.json', columns: [], feature: null, query: null, transform: null } })])).toThrow(/forbidden source/)
    expect(() => assertSpecs([fakeSpec(), fakeSpec()])).toThrow(/duplicate/)
  })

  it('classesLive is exactly [T] (AX-07)', () => {
    expect(classesLive).toEqual(['T'])
  })

  it('a kind whose class is not live, or that is marked held, only ever yields held cards', () => {
    for (const s of registry) {
      const r = assembleCard(s, {}, goodOutcome, versions, [])
      expect('card' in r && r.card.status, s.kind).toBe('held')
      if ('card' in r) {
        expect(r.card.value).toBeNull()
        expect(r.card.held_reason).toBeTruthy()
        expect(validateCard(r.card, { expectedIntervalKind: s.intervalKind }).ok).toBe(true)
      }
    }
    // With its class live, the era kind publishes a value; the pit kind stays held (spec.held).
    const era = registry.find((s) => s.kind === 'era_rating.season') as AnySpec
    const pit = registry.find((s) => s.kind === 'pit_strategy.optimal_lap') as AnySpec
    expect(heldReasonFor(era, ['T'])).toBeNull()
    expect(heldReasonFor(pit, ['T'])).toMatch(/^PIT_CALL_REPRODUCTION_RATE/)
  })

  it('registryHash is a stable sha256 and changes when a spec changes', () => {
    expect(registryHash).toMatch(/^[0-9a-f]{64}$/)
    expect(computeRegistryHash(registry)).toBe(registryHash)
    expect(computeRegistryHash([...registry].reverse())).toBe(registryHash)
    const era = registry.find((s) => s.kind === 'era_rating.season') as AnySpec
    const others = registry.filter((s) => s !== era)
    expect(computeRegistryHash([...others, { ...era, rev: era.rev + 1 }])).not.toBe(registryHash)
    expect(computeRegistryHash([...others, { ...era, intervalKind: 'ci_bayes' }])).not.toBe(registryHash)
    expect(computeRegistryHash(registry, [])).not.toBe(registryHash)
  })
})

describe('AX-04 buildCards gate', () => {
  const q: QueryRunner = { run: async () => [] as never }

  it('never emits a card validateCard rejects; every refused row is listed with a reason', async () => {
    const bad = [
      { ...goodOutcome, key: ['no-n'], n: undefined },
      { ...goodOutcome, key: ['low-high'], interval: { low: 1, high: -1, level: 0.95, source_columns: [] } },
      { ...goodOutcome, key: ['no-interval'], interval: null },
      { ...goodOutcome, key: ['ok'] },
      { ...goodOutcome, key: ['ok'] },
    ]
    const spec = fakeSpec({}, bad)
    const r = await buildCards({ specs: [spec], params: { 'test.kind': [{ k: 'a' }] }, q, classesLive: ['T'] })
    for (const c of r.cards) expect(validateCard(c, { expectedIntervalKind: 'ci_normal_95' }).ok).toBe(true)
    expect(r.cards.map((c) => c.id)).toEqual(['test.kind:ok'])
    const reasons = Object.fromEntries(r.ungrounded.map((u) => [u.id, u.reason]))
    expect(reasons['test.kind:no-n']).toMatch(/no n/)
    expect(reasons['test.kind:low-high']).toMatch(/invalid card: .*low 1 is above high -1/)
    expect(reasons['test.kind:no-interval']).toMatch(/invalid card/)
    expect(r.ungrounded.filter((u) => u.reason === 'duplicate card id')).toHaveLength(1)
    expect(r.counts['test.kind']).toEqual({ params: 1, active: 1, held: 0, refused: 4 })
    expect(r.cards[0].versions).toMatchObject({ data_version: 'test-version', card_schema: '1', registry: registryHash })
  })

  it('a refusal lists every id it covers', async () => {
    const spec = fakeSpec({ refusal: () => 'nope', ids: () => ['test.kind:a:1', 'test.kind:a:2'] }, [goodOutcome])
    const r = await buildCards({ specs: [spec], params: { 'test.kind': [{ k: 'a' }] }, q, classesLive: ['T'] })
    expect(r.cards).toEqual([])
    expect(r.ungrounded.map((u) => [u.id, u.reason])).toEqual([['test.kind:a:1', 'nope'], ['test.kind:a:2', 'nope']])
  })

  it('a compute failure is a refused row, not a crash', async () => {
    const spec = fakeSpec({ compute: async () => { throw new Error('boom') } })
    const r = await buildCards({ specs: [spec], params: { 'test.kind': [{ k: 'a' }] }, q, classesLive: ['T'] })
    expect(r.ungrounded[0].reason).toMatch(/compute failed: Error: boom/)
  })
})
