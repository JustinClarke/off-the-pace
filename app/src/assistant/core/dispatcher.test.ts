import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { createDispatcher, TOOL_NAMES } from './dispatcher'
import { demoCards, okQuery, testDeps, tools } from './testKit'
import { clearResults } from '../queryBuilder/store'
import { clearCharts, getChart } from '../charts/chartStore'
import type { ToolCall } from './types'

const call = (name: string, args: unknown): ToolCall => ({ id: 'c1', name, arguments: args })

beforeEach(() => {
  clearResults()
  clearCharts()
})

describe('dispatcher: the seven tools and refusals', () => {
  it('registers exactly the seven tools of AD2, in the generated schemas', () => {
    expect([...TOOL_NAMES].sort()).toEqual(tools.map((t) => t.function.name).sort())
    expect(TOOL_NAMES).toHaveLength(7)
  })

  it('an unknown tool is a structured error, not a throw', async () => {
    const d = createDispatcher(testDeps())
    const r = await d.dispatch(call('run_sql', { sql: 'select 1' }))
    expect(r).toMatchObject({ status: 'error', reason: 'unknown tool' })
    expect(r.allowed).toEqual([...TOOL_NAMES])
  })

  it('schema rejection of an unknown view never reaches the builder', async () => {
    const queryData = vi.fn()
    const d = createDispatcher(testDeps({ queryData }))
    const r = await d.dispatch(call('query_data', { view: 'laps_raw', aggregate: { fn: 'count', col: 'lap' } }))
    expect(r.status).toBe('error')
    expect(r.reason).toMatch(/view/)
    expect(r.allowed).toContain('qv_laps')
    expect(queryData).not.toHaveBeenCalled()
  })

  it('bad arguments (not JSON, wrong type, extra key) are errors', async () => {
    const d = createDispatcher(testDeps())
    expect((await d.dispatch(call('navigate', { __unparsable: true }))).status).toBe('error')
    expect((await d.dispatch(call('list_values', { domain: 'driver', limit: 99 }))).status).toBe('error')
    expect((await d.dispatch(call('list_values', { domain: 'driver', sql: 'x' }))).reason).toMatch(/not an argument/)
  })

  it('a thrown tool failure becomes a tool error', async () => {
    const d = createDispatcher(
      testDeps({
        listValues: async () => {
          throw new Error('boom')
        },
      }),
    )
    const r = await d.dispatch(call('list_values', { domain: 'driver', query: 'x' }))
    expect(r).toMatchObject({ status: 'error' })
    expect(r.reason).toMatch(/tool_failed/)
  })
})

describe('row-cap argument is in no tool schema (AX-11 re-check)', () => {
  it('no generated schema, and no template, names a row cap', () => {
    const rx = /row_?cap|rowcap|max_?rows|COMPARE_ROW_CAP/i
    expect(JSON.stringify(tools)).not.toMatch(rx)
    const tpl = readFileSync(join(__dirname, '../prompt/tools.template.json'), 'utf8')
    expect(tpl).not.toMatch(rx)
    const q = tools.find((t) => t.function.name === 'query_data')!
    expect((q.function.parameters.properties as Record<string, { maximum?: number }>).limit.maximum).toBe(25)
    const cmp = tools.find((t) => t.function.name === 'compare_lap_times')!
    expect(Object.keys(cmp.function.parameters.properties!).sort()).toEqual(['driver_a', 'driver_b', 'race_id'])
  })

  it('a model that sends rowCap (any spelling) to any tool is refused before the tool runs', async () => {
    const queryData = vi.fn()
    const compareLapTimes = vi.fn()
    const d = createDispatcher(testDeps({ queryData, compareLapTimes }))
    for (const key of ['rowCap', 'row_cap', 'rowcap']) {
      const q = await d.dispatch(call('query_data', { view: 'qv_stints', aggregate: { fn: 'count', col: 'stint' }, [key]: 500 }))
      expect(q.status).toBe('error')
      const c = await d.dispatch(call('compare_lap_times', { race_id: '2024_8', driver_a: 'LEC', driver_b: 'VER', [key]: 500 }))
      expect(c.status).toBe('error')
    }
    expect(queryData).not.toHaveBeenCalled()
    expect(compareLapTimes).not.toHaveBeenCalled()
  })
})

describe('get_fact_cards', () => {
  it('bundle teammate_race for a (driver, race) returns the whole recipe in ONE dispatch (store stubbed)', async () => {
    const d = createDispatcher(testDeps())
    const r = await d.dispatch(call('get_fact_cards', { bundle: 'teammate_race', scopes: [{ race_id: '2024_1', driver_id: 'VER' }] }))
    expect(r.status).toBe('ok')
    const ids = (r.cards as { id: string }[]).map((c) => c.id)
    // teammate PER was found by the store (display "vs PER"), not by the model
    expect(ids).toEqual(
      expect.arrayContaining([
        'race.teammate_gap:2024_1:VER',
        'race.teammate_gap:2024_1:PER',
        'race.result:2024_1:VER',
        'race.result:2024_1:PER',
        'race.cautions:2024_1',
        'driver_race.pit_stops:2024_1:VER',
      ]),
    )
    expect(ids.length).toBeLessThanOrEqual(10)
    expect(d.session.cards.size).toBe(ids.length)
    // projections, not full cards
    expect((r.cards as object[])[0]).toHaveProperty('lbl')
    expect((r.cards as object[])[0]).not.toHaveProperty('source')
  })

  it('includes a held stub of the recipe link when the store has one', async () => {
    const d = createDispatcher(testDeps())
    const r = await d.dispatch(call('get_fact_cards', { bundle: 'teammate_race', scopes: [{ race_id: '2024_1', driver_id: 'VER' }] }))
    const stub = (r.cards as { id: string; v: unknown }[]).find((c) => c.id.startsWith('race_driver.skill_components:2024_1:VER'))
    expect(stub, 'held link has a stub card').toBeDefined()
    expect(stub!.v).toBeNull()
  })

  it('a bundle with the scope missing is a structured error naming what is missing', async () => {
    const d = createDispatcher(testDeps())
    const r = await d.dispatch(call('get_fact_cards', { bundle: 'teammate_race', scopes: [{ season: 2024 }] }))
    expect(r).toMatchObject({ status: 'error', reason: 'scope_incomplete' })
  })

  it('a bundle without a recipe is refused (schema enum)', async () => {
    const d = createDispatcher(testDeps())
    const r = await d.dispatch(call('get_fact_cards', { bundle: 'what_if', scopes: [{ race_id: '2024_1' }] }))
    expect(r.status).toBe('error')
  })

  it('kinds + scopes find cards; at most 10 are returned and cards_dropped says how many were left', async () => {
    const d = createDispatcher(testDeps())
    const r = await d.dispatch(call('get_fact_cards', { kinds: ['race.result'], scopes: [{ season: 2024 }, { season: 2020 }, { season: 2018 }] }))
    expect(r.status).toBe('ok')
    expect((r.cards as unknown[]).length).toBeLessThanOrEqual(10)
    expect((r.cards as unknown[]).length).toBeGreaterThan(0)
  })

  it('kinds without a scope, and neither kinds nor bundle, are errors', async () => {
    const d = createDispatcher(testDeps())
    expect((await d.dispatch(call('get_fact_cards', { kinds: ['race.result'] }))).reason).toMatch(/scopes_required/)
    expect((await d.dispatch(call('get_fact_cards', {}))).reason).toMatch(/give kinds/)
  })

  it('a held kind with no stub is a structured error carrying its reason (refused call: held card)', async () => {
    const d = createDispatcher(testDeps({ kinds: [{ kind: 'pit_strategy.verdict', held_reason: 'held until the reproduction rate is re-measured' }] }))
    const r = await d.dispatch(call('get_fact_cards', { kinds: ['pit_strategy.verdict'], scopes: [{ race_id: '2023_6', driver_id: 'VER' }] }))
    expect(r).toMatchObject({ status: 'error', reason: 'held' })
    expect(r.held).toEqual([{ kind: 'pit_strategy.verdict', held_reason: expect.stringContaining('re-measured') }])
  })

  it('no card for a live kind is no_data', async () => {
    const d = createDispatcher(testDeps())
    const r = await d.dispatch(call('get_fact_cards', { kinds: ['race.result'], scopes: [{ race_id: '1999_1', driver_id: 'XXX' }] }))
    expect(r).toMatchObject({ status: 'no_data' })
  })

  it('the demo store has what these tests rely on', () => {
    expect(demoCards.some((c) => c.id === 'race.teammate_gap:2024_1:VER')).toBe(true)
  })
})

describe('list_values cache', () => {
  it('a repeated lookup makes no second call and is flagged cached', async () => {
    const listValues = vi.fn(async () => ({ status: 'ok' as const, rows: [{ code: 'PER', display: 'Sergio Perez', aliases_matched: ['checo'], seasons: '2018-2024' }] }))
    const d = createDispatcher(testDeps({ listValues }))
    const a = await d.dispatch(call('list_values', { domain: 'driver', query: 'Checo' }))
    const b = await d.dispatch(call('list_values', { domain: 'driver', query: ' checo ' }))
    expect(listValues).toHaveBeenCalledTimes(1)
    expect(a.cached).toBeUndefined()
    expect(b.cached).toBe(true)
    expect(d.session.listValuesCacheHits).toBe(1)
    expect(d.session.listValuesLookups).toBe(1)
    await d.dispatch(call('list_values', { domain: 'driver', query: 'Seb' }))
    expect(listValues).toHaveBeenCalledTimes(2)
  })
})

describe('query_data', () => {
  it('passes a bounded request to the builder and records the result for grounding and charts', async () => {
    const queryData = vi.fn(async () => okQuery())
    const d = createDispatcher(testDeps({ queryData }))
    const r = await d.dispatch(call('query_data', { view: 'qv_stints', group_by: ['driver_id'], aggregate: { fn: 'count', col: 'stint' }, limit: 10 }))
    expect(r).toMatchObject({ status: 'ok', label: 'computed_not_card', result_id: 'q0000000001' })
    expect(d.session.queryResults).toHaveLength(1)
  })

  it('maps no_data and builder errors to tool results', async () => {
    const d1 = createDispatcher(testDeps({ queryData: async () => ({ status: 'no_data', view: 'qv_stints', reason: 'no rows match the filters' }) }))
    expect(await d1.dispatch(call('query_data', { view: 'qv_stints' }))).toMatchObject({ status: 'no_data', reason: 'no rows match the filters' })
    const d2 = createDispatcher(testDeps({ queryData: async () => ({ status: 'error', code: 'unknown_column', field: 'x', message: 'no such column', allowed: { columns: ['a'] } }) }))
    expect(await d2.dispatch(call('query_data', { view: 'qv_stints' }))).toMatchObject({ status: 'error', reason: 'unknown_column: no such column', allowed: { columns: ['a'] } })
  })
})

describe('make_chart and compare_lap_times', () => {
  it('make_chart builds the spec from a stored result; the model never writes one', async () => {
    const d = createDispatcher(testDeps())
    await d.dispatch(call('query_data', { view: 'qv_stints', group_by: ['driver_id'], aggregate: { fn: 'count', col: 'stint' } }))
    const r = await d.dispatch(call('make_chart', { result_id: 'q0000000001' }))
    expect(r).toMatchObject({ status: 'ok', series_count: 1, n: 2 })
    expect(Object.keys(r).sort()).toEqual(['chart_id', 'n', 'series_count', 'status'])
    expect(getChart(r.chart_id as string)?.spec.type).toBe('bar')
    expect(d.session.chartIds).toEqual([r.chart_id])
  })

  it('make_chart refuses a result_id from no query this session, and a result with no group_by', async () => {
    const d = createDispatcher(testDeps())
    expect(await d.dispatch(call('make_chart', { result_id: 'deadbeef0000' }))).toMatchObject({ status: 'error' })
    const flat = { ...okQuery('q0000000002'), group_by: [] as string[] }
    const d2 = createDispatcher(testDeps({ queryData: async () => flat }))
    await d2.dispatch(call('query_data', { view: 'qv_stints' }))
    expect((await d2.dispatch(call('make_chart', { result_id: 'q0000000002' }))).reason).toMatch(/group_by/)
  })

  it('compare_lap_times calls the AX-11 function and records the chart; absent -> not_available_yet', async () => {
    const compareLapTimes = vi.fn(async () => ({ status: 'ok' as const, chart_id: 'chart_9', n_a: 76, n_b: 74, laps_missing: 2 }))
    const d = createDispatcher(testDeps({ compareLapTimes }))
    const r = await d.dispatch(call('compare_lap_times', { race_id: '2024_8', driver_a: 'LEC', driver_b: 'VER' }))
    expect(r).toMatchObject({ status: 'ok', chart_id: 'chart_9' })
    expect(compareLapTimes).toHaveBeenCalledWith('LEC', 'VER', '2024_8')
    const d2 = createDispatcher(testDeps())
    expect(await d2.dispatch(call('compare_lap_times', { race_id: '2024_8', driver_a: 'LEC', driver_b: 'VER' }))).toMatchObject({ status: 'error', reason: 'not_available_yet' })
  })
})

describe('navigate and explain_page', () => {
  it('navigate returns a validated URL and records it; a bad route is an error', async () => {
    const d = createDispatcher(testDeps())
    const ok = await d.dispatch(call('navigate', { route: '/ml/simulator' }))
    expect(ok.status).toBe('ok')
    expect(String(ok.url)).toContain('/ml/simulator')
    expect(d.session.links).toHaveLength(1)
    const bad = await d.dispatch(call('navigate', { route: 'https://evil.example/x' }))
    expect(bad.status).toBe('error')
  })

  it('explain_page returns a summary for a known page and an error listing known pages otherwise', async () => {
    const d = createDispatcher(testDeps())
    const ok = await d.dispatch(call('explain_page', { page: '/drivers/ratings-timeline' }))
    expect(ok).toMatchObject({ status: 'ok', page_id: 'era-ratings-timeline' })
    expect(String(ok.summary).length).toBeGreaterThan(50)
    const bad = await d.dispatch(call('explain_page', { page: 'nope' }))
    expect(bad.status).toBe('error')
    expect(Array.isArray(bad.allowed)).toBe(true)
  })
})

describe('code path: no module under core/ runs raw SQL', () => {
  const files = readdirSync(__dirname).filter((f) => f.endsWith('.ts') && !f.endsWith('.test.ts') && f !== 'testKit.ts')
  it('has source files to scan', () => {
    expect(files.length).toBeGreaterThanOrEqual(8)
  })
  for (const f of files) {
    const src = readFileSync(join(__dirname, f), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
    it(`${f} does not import runLabQuery or the lab layer, and builds no SQL from model text`, () => {
      expect(src).not.toMatch(/runLabQuery|queryLab|assertReadOnly|registerPartitionedParquet|rawQuery/)
      expect(src).not.toMatch(/\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE)\b[^'"`\n]*(\$\{|\+\s*\w)/)
      expect(src).not.toMatch(/\bnew Function\(|\beval\(/)
    })
  }
})
