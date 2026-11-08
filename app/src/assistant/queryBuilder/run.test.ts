// AX-06: runQuery on a spy engine: partition scoping, timeout, no-data, thin rows, rounding,
// result_id stability, store, and the honesty projection.
import { describe, it, expect, beforeEach } from 'vitest'
import { catalogue, makeManifest, spyEngine } from './__fixtures__/fixtures'
import { runQuery, resultId } from './run'
import { clearResults, getResult } from './store'
import { queryResultToCheckerCard } from '../honesty/queryCard'
import type { QueryResult } from './types'

const manifest = makeManifest('m1')
const req = {
  view: 'qv_laps',
  filters: [{ col: 'season', op: 'eq', val: 2024 }, { col: 'race_id', op: 'eq', val: '2024_8' }],
  group_by: ['driver_id'],
  aggregate: { fn: 'median', col: 'lap_time_s' },
  order: 'value_asc',
  limit: 2,
}
const rows = [
  { driver_id: 'LEC', value: 75.123456, n: 70n, total_groups: 20n },
  { driver_id: 'SAI', value: 75.2, n: 3n, total_groups: 20n },
]

beforeEach(() => clearResults())

describe('runQuery', () => {
  it('registers only the filtered seasons', async () => {
    const e = spyEngine(rows)
    await runQuery(req, { catalogue, manifest, engine: e })
    expect(e.registered).toEqual([{ alias: 'qv_laps_2024', url: '/data/assistant/qv/qv_laps/2024.parquet?v=m1' }])
    const e2 = spyEngine(rows)
    await runQuery({ ...req, filters: [{ col: 'season', op: 'between', val: [2022, 2023] }], group_by: [] }, { catalogue, manifest, engine: e2 })
    expect(e2.registered.map((r) => r.alias).sort()).toEqual(['qv_laps_2022', 'qv_laps_2023'])
  })

  it('registers the one race file of a race-partitioned view', async () => {
    const e = spyEngine([{ corner_name: 'Turn_1', value: 2.5, n: 40, total_groups: 1 }])
    await runQuery(
      { view: 'qv_teammate_corners', filters: [{ col: 'season', op: 'eq', val: 2024 }, { col: 'race_id', op: 'eq', val: '2024_8' }], group_by: ['corner_name'], aggregate: { fn: 'avg', col: 'v_min_delta_kph' } },
      { catalogue, manifest, engine: e },
    )
    expect(e.registered).toHaveLength(1)
    expect(e.registered[0].url).toBe('/data/assistant/qv/qv_teammate_corners/2024/2024_8.parquet?v=m1')
  })

  it('shapes the result: n on every row, thin, 3 decimals, rows_dropped exact, label', async () => {
    const out = (await runQuery(req, { catalogue, manifest, engine: spyEngine(rows) })) as QueryResult
    expect(out.status).toBe('ok')
    expect(out.rows).toEqual([
      { driver_id: 'LEC', value: 75.123, n: 70 },
      { driver_id: 'SAI', value: 75.2, n: 3, thin: true },
    ])
    expect(out.row_count).toBe(20)
    expect(out.rows_shown).toBe(2)
    expect(out.rows_dropped).toBe(18)
    expect(out.label).toBe('computed_not_card')
    expect(out.filters_applied).toContainEqual({ col: 'is_major_outlier_lap', op: 'eq', val: false })
    expect(out.notes.join(' ')).toMatch(/thin/)
    expect(getResult(out.result_id)).toBe(out)
  })

  it('result_id is stable for the same request and manifest, and moves with either', async () => {
    const a = (await runQuery(req, { catalogue, manifest, engine: spyEngine(rows) })) as QueryResult
    const b = (await runQuery(JSON.parse(JSON.stringify(req)), { catalogue, manifest, engine: spyEngine(rows) })) as QueryResult
    const c = (await runQuery(req, { catalogue, manifest: makeManifest('m2'), engine: spyEngine(rows) })) as QueryResult
    const d = (await runQuery({ ...req, limit: 3 }, { catalogue, manifest, engine: spyEngine(rows) })) as QueryResult
    expect(a.result_id).toMatch(/^[0-9a-f]{12}$/)
    expect(b.result_id).toBe(a.result_id)
    expect(c.result_id).not.toBe(a.result_id)
    expect(d.result_id).not.toBe(a.result_id)
    expect(resultId({ b: 1, a: 2 }, 'x')).toBe(resultId({ a: 2, b: 1 }, 'x'))
  })

  it('no_data on empty rows, on n = 0, and on a race with no file', async () => {
    expect((await runQuery(req, { catalogue, manifest, engine: spyEngine([]) })).status).toBe('no_data')
    expect((await runQuery(req, { catalogue, manifest, engine: spyEngine([{ value: null, n: 0, total_groups: 1 }]) })).status).toBe('no_data')
    const out = await runQuery(
      { view: 'qv_teammate_corners', filters: [{ col: 'season', op: 'eq', val: 2024 }, { col: 'race_id', op: 'eq', val: '2024_99' }], aggregate: { fn: 'count', col: 'corners' } },
      { catalogue, manifest, engine: spyEngine() },
    )
    expect(out).toMatchObject({ status: 'no_data' })
  })

  it('times out a never-resolving query within the limit and replaces the connection', async () => {
    const e = spyEngine(() => new Promise(() => {}))
    const t0 = Date.now()
    const out = await runQuery(req, { catalogue, manifest, engine: e, timeoutMs: 50 })
    expect(out).toMatchObject({ status: 'error', code: 'timeout' })
    expect(Date.now() - t0).toBeLessThan(3000)
    expect(e.cancels).toBe(1)
  })

  it('uses the catalogue 3 s timeout by default', async () => {
    expect(catalogue.limits.timeout_ms).toBe(3000)
    const e = spyEngine(() => new Promise(() => {}))
    const t0 = Date.now()
    const out = await runQuery(req, { catalogue, manifest, engine: e })
    expect(out).toMatchObject({ code: 'timeout' })
    expect(Date.now() - t0).toBeLessThan(3500)
  }, 6000)

  it('returns validation errors without touching the engine', async () => {
    const e = spyEngine(rows)
    expect(await runQuery({ ...req, view: 'nope' }, { catalogue, manifest, engine: e })).toMatchObject({ code: 'unknown_view' })
    expect(e.registered).toEqual([])
    expect(e.runs).toEqual([])
  })

  it('projects into a checker card that fires COMPUTED_NOT_CARD_WORDING', async () => {
    const out = (await runQuery(req, { catalogue, manifest, engine: spyEngine(rows) })) as QueryResult
    expect(queryResultToCheckerCard(out)).toMatchObject({ metric: 'qv_laps.lap_time_s', label: 'computed_not_card', n: 3, n_unit: 'rows' })
  })
})
