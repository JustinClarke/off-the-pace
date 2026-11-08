import { describe, it, expect, beforeEach } from 'vitest'
import entities from './entities/__fixtures__/assistant_entities.json'
import coverage from './entities/__fixtures__/coverage_ids.json'
import { estimateTokens } from '../nav/pageSummaries.mjs'
import {
  listValues, listValuesFromRows, registerListProvider, clearListValuesCache, MAX_ROWS, MAX_TOKENS,
  type EntityRow, type ListDomain,
} from './listValues'

const rows = entities as EntityRow[]
const top = (domain: ListDomain, query: string, season?: number) => {
  const r = listValuesFromRows(rows, { domain, query, season })
  return r.status === 'ok' ? r.rows[0]?.code : undefined
}

// 30 alias fixtures: [domain, query, expected code]
const FIXTURES: Array<[ListDomain, string, string]> = [
  ['driver', 'Checo', 'PER'],
  ['driver', 'checo', 'PER'],
  ['driver', 'Sergio Perez', 'PER'],
  ['driver', 'Pérez', 'PER'],
  ['driver', 'Mad Max', 'VER'],
  ['driver', 'Verstappen', 'VER'],
  ['driver', 'Lewis Hamilton', 'HAM'],
  ['driver', 'hamilton', 'HAM'],
  ['driver', 'Charles', 'LEC'],
  ['driver', 'Nando', 'ALO'],
  ['driver', 'Iceman', 'RAI'],
  ['driver', 'Raikkonen', 'RAI'],
  ['driver', 'Hulkenberg', 'HUL'],
  ['driver', 'Lando', 'NOR'],
  ['driver', 'LEC', 'LEC'],
  ['constructor', 'Alfa Romeo', 'sauber'],
  ['constructor', 'Sauber', 'sauber'],
  ['constructor', 'Kick Sauber', 'sauber'],
  ['constructor', 'AlphaTauri', 'toro_rosso'],
  ['constructor', 'Racing Bulls', 'toro_rosso'],
  ['constructor', 'Racing Point', 'force_india'],
  ['constructor', 'Alpine', 'renault'],
  ['constructor', 'Red Bull', 'red_bull_racing'],
  ['race', 'Interlagos 2021', '2021_19'],
  ['race', 'Monza 2023', '2023_14'],
  ['race', '2021_19', '2021_19'],
  ['circuit', 'Spa', 'belgian_grand_prix'],
  ['circuit', 'Suzuka', 'japanese_grand_prix'],
  ['compound', 'reds', 'SOFT'],
  ['stint_end_cause', 'DNF', 'retirement'],
]

describe('list_values alias fixtures', () => {
  it.each(FIXTURES)('%s "%s" -> %s', (domain, query, code) => {
    expect(top(domain, query)).toBe(code)
  })

  it('has 30 fixtures', () => expect(FIXTURES.length).toBe(30))

  it('Monza 2023 fixture matches the exported round', () => {
    const r = rows.find(e => e.domain === 'race' && e.code === '2023_14')
    expect(r?.parent_code).toBe('italian_grand_prix')
  })
})

describe('ambiguity and no_data', () => {
  it('an ambiguous query returns several rows and says not to pick', () => {
    const r = listValuesFromRows(rows, { domain: 'circuit', query: 'Silverstone' })
    expect(r.status).toBe('ok')
    if (r.status === 'ok') {
      expect(r.rows.length).toBeGreaterThan(1)
      expect(r.note).toMatch(/do not pick/)
    }
  })
  it('"Kimi" returns both Antonelli and Raikkonen', () => {
    const r = listValuesFromRows(rows, { domain: 'driver', query: 'Kimi' })
    const codes = r.status === 'ok' ? r.rows.map(x => x.code) : []
    expect(codes).toEqual(expect.arrayContaining(['ANT', 'RAI']))
  })
  it('an unknown value returns no_data', () => {
    expect(listValuesFromRows(rows, { domain: 'driver', query: 'zzzqqq' })).toMatchObject({ status: 'no_data', rows: [] })
  })
  it('a season filter removes drivers who did not race that year', () => {
    expect(listValuesFromRows(rows, { domain: 'driver', query: 'Kubica', season: 2024 }).status).toBe('no_data')
  })
})

describe('size', () => {
  it.each(['driver', 'race', 'circuit', 'constructor'] as ListDomain[])('%s: empty query stays within 20 rows and 400 tokens', (domain) => {
    const r = listValuesFromRows(rows, { domain, limit: 999 })
    expect(r.status).toBe('ok')
    expect(r.rows.length).toBeLessThanOrEqual(MAX_ROWS)
    expect(estimateTokens(JSON.stringify(r))).toBeLessThanOrEqual(MAX_TOKENS)
  })
  it('broad token queries stay within the caps', () => {
    for (const q of ['grand prix', 'a', 'red']) {
      const r = listValuesFromRows(rows, { domain: 'race', query: q })
      expect(r.rows.length).toBeLessThanOrEqual(MAX_ROWS)
      expect(estimateTokens(JSON.stringify(r))).toBeLessThanOrEqual(MAX_TOKENS)
    }
  })
})

describe('coverage: every id in the exported tables resolves', () => {
  const byCode = (d: string, c: string) => rows.some(e => e.domain === d && e.code === c)
  it('driver_id', () => {
    for (const id of coverage.driver_id) expect(byCode('driver', id), id).toBe(true)
  })
  it('race_id', () => {
    for (const id of coverage.race_id) expect(byCode('race', id), id).toBe(true)
  })
  it('constructor_id resolves to its lineage row', () => {
    for (const id of coverage.constructor_id) {
      const hit = rows.find(e => e.domain === 'constructor' && (e.extra.constructor_ids as string[]).includes(id))
      expect(hit, id).toBeTruthy()
      expect(top('constructor', id)).toBe(hit!.code)
    }
  })
})

describe('providers, pages and the session cache', () => {
  beforeEach(() => clearListValuesCache())
  it('columns and card_kind say so until a provider registers', async () => {
    const r = await listValues({ domain: 'columns', query: 'x' })
    expect(r).toMatchObject({ status: 'no_data' })
    expect(r.note).toMatch(/AX-05/)
    expect((await listValues({ domain: 'card_kind' })).note).toMatch(/AX-04/)
  })
  it('a registered provider is served and cached', async () => {
    let calls = 0
    registerListProvider('card_kind', () => { calls++; return [{ code: 'era_rating.season', display: 'Era rating' }] })
    const a = await listValues({ domain: 'card_kind', query: 'era' })
    const b = await listValues({ domain: 'card_kind', query: 'ERA' })
    expect(a).toBe(b)
    expect(calls).toBe(1)
  })
  it('page comes from routeToPageId', async () => {
    const r = await listValues({ domain: 'page', query: 'race lost' })
    expect(r.status).toBe('ok')
    if (r.status === 'ok') expect(r.rows[0].code).toBe('/lap-decomposition/race-lost')
  })
})
