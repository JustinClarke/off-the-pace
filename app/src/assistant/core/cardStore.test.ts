import { describe, it, expect } from 'vitest'
import { cardFromParquetRow, createCardStore } from './cardStore'
import { preloadPageCards, scopeFromRoute } from './preload'
import { demoCards, demoStore } from './testKit'
import { registry } from '../cards/registry'
import { toModelProjection } from '../cards/project'
import { validateCard } from '../cards/validate'

describe('card store', () => {
  const store = demoStore()

  it('byId, has, expand (sorted prefix) and find (live before held)', () => {
    expect(store.byId('race.cautions:2024_1')?.kind).toBe('race.cautions')
    expect(store.has('nope')).toBe(false)
    const ids = store.expand('race.result:2024_1:')
    expect(ids).toEqual([...ids].sort())
    expect(ids).toContain('race.result:2024_1:VER')
    const found = store.find({ race_id: '2024_1' }, ['race.result', 'race.cautions'])
    expect(found.length).toBeGreaterThan(2)
    expect(found.every((c) => c.scope.race_id === '2024_1')).toBe(true)
  })

  it('teammateOf: from the gap card display first, from the shared constructor otherwise, null when ambiguous or unknown', () => {
    expect(store.teammateOf('2024_1', 'VER')).toBe('PER')
    expect(store.teammateOf('2024_1', 'PER')).toBe('VER')
    expect(store.teammateOf('2024_1', 'NOBODY')).toBeNull()
    // no gap card: constructor pairing from race.result
    const res = (driver: string, team: string) => ({ ...demoCards.find((c) => c.id === 'race.result:2024_1:VER')!, id: `race.result:2030_1:${driver}`, scope: { ...demoCards[0].scope, season: 2030, race_id: '2030_1', driver_id: driver, constructor_id: team } })
    const s = createCardStore([res('AAA', 'T1'), res('BBB', 'T1'), res('CCC', 'T2')])
    expect(s.teammateOf('2030_1', 'AAA')).toBe('BBB')
    expect(s.teammateOf('2030_1', 'CCC')).toBeNull()
    const three = createCardStore([res('AAA', 'T1'), res('BBB', 'T1'), res('DDD', 'T1')])
    expect(three.teammateOf('2030_1', 'AAA')).toBeNull()
  })

  it('AX-10b: the teammate_id policy field is preferred; the five demo races resolve the same teammate by field and by fallback', () => {
    const demos: [string, string][] = [['2024_1', 'VER'], ['2020_14', 'HAM'], ['2018_1', 'RIC'], ['2021_16', 'HAM'], ['2024_5', 'NOR']]
    const before = demos.map(([r, d]) => store.teammateOf(r, d))
    // add the field (set to what the fallback found) and garble the display text so only the field can answer
    const withField = demoCards.map((c) => {
      if (c.kind !== 'race.teammate_gap' || !c.scope.race_id || !c.scope.driver_id) return c
      const mate = store.teammateOf(c.scope.race_id, c.scope.driver_id)
      return { ...c, display: c.display ? 'gap shown without naming anyone' : c.display, policy_fields: { ...c.policy_fields, teammate_id: mate } }
    })
    const s = createCardStore(withField)
    expect(demos.map(([r, d]) => s.teammateOf(r, d))).toEqual(before)
    expect(before.every((m) => typeof m === 'string' && m.length > 0)).toBe(true)
    // a card whose display text changed still resolves via the field, even against a wrong constructor pairing
    const odd = withField.map((c) => (c.id === 'race.teammate_gap:2024_1:VER' ? { ...c, policy_fields: { ...c.policy_fields, teammate_id: 'ZZZ' } } : c))
    expect(createCardStore(odd).teammateOf('2024_1', 'VER')).toBe('ZZZ')
    // an unavailable gap card keeps a teammate_id when it has one
    const un = withField.find((c) => c.kind === 'race.teammate_gap' && c.label === 'unavailable')
    if (un) expect(createCardStore([un]).teammateOf(un.scope.race_id!, un.scope.driver_id!)).toBe(un.policy_fields.teammate_id ?? null)
  })

  it('onPage prefers cards tied to the params over page-wide ones', () => {
    const tied = store.onPage('/race-craft/race-control', { season: 2024, race_id: '2024_1' })
    expect(tied.map((c) => c.id)).toEqual(['race.cautions:2024_1'])
    const wide = store.onPage('/race-craft/race-control', {})
    expect(wide.some((c) => c.kind === 'race_control.pooled_rate')).toBe(true)
  })
})

describe('parquet row decoding', () => {
  it('turns an assistant_cards row back into a valid Card', () => {
    const c = demoCards.find((x) => x.id === 'race.teammate_gap:2024_1:VER')!
    const row = {
      id: c.id, kind: c.kind, metric: c.metric, label: c.label, value: JSON.stringify(c.value), unit: c.unit, display: c.display,
      unavailable_reason: null, n_count: c.n.count, n_unit: c.n.unit, interval_low: c.interval!.low, interval_high: c.interval!.high,
      interval_level: c.interval!.level, interval_kind: c.interval!.kind, interval_source_columns: JSON.stringify(c.interval!.source_columns),
      sample: c.sample, grade: c.grade, status: c.status, held_reason: null, scope: JSON.stringify(c.scope), source: JSON.stringify(c.source),
      versions: JSON.stringify(c.versions), page: JSON.stringify(c.page), caveats: JSON.stringify(c.caveats), policy_fields: JSON.stringify(c.policy_fields),
    }
    const back = cardFromParquetRow(row)
    expect(back).toEqual(c)
    expect(validateCard(back, { expectedIntervalKind: c.interval!.kind }).ok).toBe(true)
  })

  it('NULL interval_kind is a null interval; a NULL value is null', () => {
    const c = demoCards.find((x) => x.id === 'race.cautions:2024_1')!
    const back = cardFromParquetRow({ ...c, value: JSON.stringify(c.value), n_count: c.n.count, n_unit: c.n.unit, interval_kind: null, scope: JSON.stringify(c.scope), source: '{}', versions: '{}', page: 'null', caveats: '[]', policy_fields: '{}' })
    expect(back.interval).toBeNull()
    expect(back.page).toBeNull()
    expect(cardFromParquetRow({ id: 'x:1', kind: 'x', metric: 'm', label: 'unavailable', value: null, n_count: 0, n_unit: 'laps' }).value).toBeNull()
  })
})

describe('page-card pre-load', () => {
  const store = demoStore()
  it('maps route params to card scope keys', () => {
    expect(scopeFromRoute({ season: '2024', race: '5', driver: 'NOR' })).toMatchObject({ season: 2024, race_id: '2024_5', driver_id: 'NOR' })
    expect(scopeFromRoute({ race_id: '2024_8' })).toMatchObject({ race_id: '2024_8' })
  })

  it('no page: nothing; page with no card: says so', () => {
    expect(preloadPageCards(store, null)).toEqual({ cards: [], text: '', ids: [] })
    expect(preloadPageCards(store, { route: '/ml/metrics', params: {} }).text).toContain('No fact card is tied')
  })

  it('uses registry onScreen (the real registry) and the card page links, at most 6, only ids the store holds', () => {
    const pre = preloadPageCards(store, { route: '/race-craft/race-control', params: { season: 2024, race_id: '2024_1' } }, registry)
    expect(pre.ids).toEqual(['race.cautions:2024_1'])
    expect(pre.text).toContain(JSON.stringify(toModelProjection(pre.cards[0])))
  })

  it('caps at 6 and fits the 600-token page-context slot', () => {
    const many = Array.from({ length: 12 }, (_, i) => ({ ...demoCards.find((c) => c.id === 'race.cautions:2024_1')!, id: `race.cautions:2024_${i + 1}`, scope: { ...demoCards[0].scope, race_id: `2024_${i + 1}` } }))
    const s = createCardStore(many)
    const specs = [{ route: '/race-craft/race-control', onScreen: () => many.map((c) => c.id) }]
    const pre = preloadPageCards(s, { route: '/race-craft/race-control', params: {} }, specs)
    expect(pre.ids).toHaveLength(6)
    expect(Math.ceil(pre.text.length / 4)).toBeLessThanOrEqual(600)
  })

  it('a spec that throws (page without the param) yields nothing from that spec', () => {
    const specs = [{ route: '/x', onScreen: () => { throw new Error('needs driver') } }]
    expect(preloadPageCards(store, { route: '/x', params: {} }, specs).ids).toEqual([])
  })
})
