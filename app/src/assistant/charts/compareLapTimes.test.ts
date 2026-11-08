import { describe, it, expect, beforeEach } from 'vitest'
import entitiesJson from '../entities/__fixtures__/assistant_entities.json'
import { compareLapTimes, COMPARE_ROW_CAP } from './compareLapTimes'
import { catalogue, makeManifest, spyEngine } from '../queryBuilder/__fixtures__/fixtures'
import { runQuery } from '../queryBuilder/run'
import { compile } from '../queryBuilder/compile'
import { validate } from '../queryBuilder/validate'
import { clearResults } from '../queryBuilder/store'
import { clearCharts, getChart } from './chartStore'
import type { EntityRow } from '../listValues'

const entities = entitiesJson as unknown as EntityRow[]
const manifest = makeManifest()

function laps(d: string, from: number, to: number) {
  return Array.from({ length: to - from + 1 }, (_, i) => ({ driver_id: d, lap_number: from + i, value: 90 + i / 10, n: 1, total_groups: 160 }))
}
const deps = (rows: Record<string, unknown>[]) => ({ catalogue, manifest, engine: spyEngine(rows), entities })

describe('compare_lap_times', () => {
  beforeEach(() => { clearCharts(); clearResults() })
  it('returns the 4-field result with n_a, n_b and laps_missing', async () => {
    const d = deps([...laps('LEC', 1, 57), ...laps('SAI', 1, 55)])
    const r = await compareLapTimes('LEC', 'SAI', '2024_8', d)
    expect(r).toMatchObject({ status: 'ok', n_a: 57, n_b: 55, laps_missing: 2 })
    expect(Object.keys(r).sort()).toEqual(['chart_id', 'laps_missing', 'n_a', 'n_b', 'status'])
    expect(getChart((r as { chart_id: string }).chart_id)?.n).toEqual([57, 55])
    expect(d.engine.runs[0].sql).toContain('LIMIT 160')
  })
  it('counts laps present for only one driver on both sides', async () => {
    const r = await compareLapTimes('LEC', 'SAI', '2024_8', deps([...laps('LEC', 1, 10), ...laps('SAI', 3, 12)]))
    expect(r).toMatchObject({ n_a: 10, n_b: 10, laps_missing: 4 })
  })
  it('non-code input returns an error pointing at list_values; engine untouched', async () => {
    const d = deps([])
    for (const [a, b, r] of [['Leclerc', 'SAI', '2024_8'], ['LEC', 'sai', '2024_8'], ['LEC', 'SAI', 'Monaco'], ['LEC', 'ZZZ', '2024_8'], ['LEC', 'SAI', '2024_99']]) {
      const out = await compareLapTimes(a, b, r, d)
      expect(out.status).toBe('error')
      expect((out as { reason: string }).reason).toMatch(/list_values/)
    }
    expect(d.engine.runs).toHaveLength(0)
  })
  it('a driver absent from the race gives no_data, not an empty chart', async () => {
    const r = await compareLapTimes('LEC', 'SAI', '2024_8', deps(laps('LEC', 1, 20)))
    expect(r).toMatchObject({ status: 'no_data' })
    expect(await compareLapTimes('LEC', 'SAI', '2024_8', deps([]))).toMatchObject({ status: 'no_data' })
  })
})

describe('internal rowCap', () => {
  const req = {
    view: 'qv_laps',
    filters: [{ col: 'season', op: 'eq', val: 2024 }],
    group_by: ['driver_id'],
    aggregate: { fn: 'median', col: 'lap_time_s' },
  }
  it('a model-supplied rowCap is rejected by validate and by runQuery', async () => {
    for (const key of ['rowCap', 'row_cap', 'rowcap']) {
      expect(validate({ ...req, [key]: 160 }, catalogue)).toMatchObject({ status: 'error', code: 'bad_value' })
      expect(await runQuery({ ...req, [key]: 160 }, { catalogue, manifest, engine: spyEngine([]) })).toMatchObject({ status: 'error' })
    }
    expect(validate({ ...req, limit: 160 }, catalogue)).toMatchObject({ status: 'error', code: 'bad_limit' })
  })
  it('compile honours only an in-range integer internal cap', () => {
    const v = validate(req, catalogue)
    if ('status' in v) throw new Error('invalid')
    expect(compile(v).sql).toMatch(/LIMIT 10$/)
    expect(compile(v, { rowCap: COMPARE_ROW_CAP }).sql).toMatch(/LIMIT 160$/)
    for (const bad of [0, 201, 1.5, NaN]) expect(() => compile(v, { rowCap: bad })).toThrow()
  })
  it('result_id differs between a capped and an uncapped identical request', async () => {
    const rows = laps('LEC', 1, 3)
    const a = await runQuery({ ...req, group_by: ['driver_id', 'lap_number'], filters: [...req.filters, { col: 'race_id', op: 'eq', val: '2024_8' }] }, { catalogue, manifest, engine: spyEngine(rows) })
    const b = await runQuery({ ...req, group_by: ['driver_id', 'lap_number'], filters: [...req.filters, { col: 'race_id', op: 'eq', val: '2024_8' }] }, { catalogue, manifest, engine: spyEngine(rows) }, { rowCap: 160 })
    expect((a as { result_id: string }).result_id).not.toBe((b as { result_id: string }).result_id)
  })
  it('no tool schema or catalogue field exposes a row cap', () => {
    const catJson = JSON.stringify(catalogue).toLowerCase()
    expect(catJson).not.toMatch(/rowcap|row_cap/)
    expect(JSON.stringify(catalogue.limits)).not.toMatch(/160/)
  })
})
