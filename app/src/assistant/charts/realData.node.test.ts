// @vitest-environment node
// AX-11: the three sample questions on the real AX-05 qv_laps files (duckdb-wasm Node bundle). Skipped unless
// AX06_DATA_DIR is set; with AX11_EVIDENCE_DIR also set, writes the resulting chart specs there.
import { describe, it, expect, beforeAll } from 'vitest'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { createAdapter, createWasmEngine, type Adapter } from '../cards/headless/adapter'
import { parseCatalogue } from '../catalogue/catalogue'
import type { DataManifest } from '../../data/manifest'
import entitiesJson from '../entities/__fixtures__/assistant_entities.json'
import type { EntityRow } from '../listValues'
import { runQuery, type Engine, type RunDeps } from '../queryBuilder/run'
import { compareLapTimes } from './compareLapTimes'
import { makeChart } from './makeChart'
import { getChart } from './chartStore'

const DIR = process.env.AX06_DATA_DIR
const OUT = process.env.AX11_EVIDENCE_DIR
const enabled = !!DIR && existsSync(join(DIR, 'assistant', 'catalogue.json'))

describe.skipIf(!enabled)('AX-11 on the scratch export', () => {
  let deps: RunDeps & { entities: EntityRow[] }
  beforeAll(async () => {
    const adapter: Adapter = createAdapter({ dataDir: DIR! }, await createWasmEngine())
    const engine: Engine = {
      registerPartition: (alias, url) => adapter.registerParquet(alias, url),
      prepareRun: (sql, params) => adapter.query(sql, params),
      cancel: async () => undefined,
    }
    deps = {
      catalogue: parseCatalogue(JSON.parse(readFileSync(join(DIR!, 'assistant', 'catalogue.json'), 'utf8'))),
      manifest: JSON.parse(readFileSync(join(DIR!, '_manifest.json'), 'utf8')) as DataManifest,
      engine,
      entities: entitiesJson as unknown as EntityRow[],
    }
  })
  const save = (name: string, id: string) => {
    const c = getChart(id)!
    if (OUT) {
      mkdirSync(OUT, { recursive: true })
      writeFileSync(join(OUT, `${name}.json`), JSON.stringify({ spec: c.spec, n: c.n, note: c.note ?? null }, null, 2))
    }
  }

  it('Q1 two-driver comparison: LEC vs VER, 2024_8', async () => {
    const r = await compareLapTimes('LEC', 'VER', '2024_8', deps)
    expect(r.status).toBe('ok')
    if (r.status !== 'ok') return
    expect(r.n_a).toBeGreaterThan(20)
    expect(r.n_a).toBeLessThanOrEqual(80)
    save('q1-two-driver', r.chart_id)
    console.log('Q1', JSON.stringify(r))
  })
  it('Q2 team-mates: LEC vs SAI, 2024_8', async () => {
    const r = await compareLapTimes('LEC', 'SAI', '2024_8', deps)
    expect(r.status).toBe('ok')
    if (r.status !== 'ok') return
    save('q2-team-mates', r.chart_id)
    console.log('Q2', JSON.stringify(r))
  })
  it('Q3 custom chart from a query_data result: median lap time by compound, 2024', async () => {
    const q = await runQuery(
      {
        view: 'qv_laps',
        filters: [{ col: 'season', op: 'eq', val: 2024 }, { col: 'driver_id', op: 'eq', val: 'LEC' }, { col: 'age_in_stint', op: 'lte', val: 25 }],
        group_by: ['age_in_stint'],
        aggregate: { fn: 'median', col: 'lap_time_s' },
        order: 'group_asc',
        limit: 25,
      },
      deps,
    )
    expect(q.status).toBe('ok')
    if (q.status !== 'ok') return
    const r = makeChart({
      type: 'line', title: 'LEC median lap time by tyre age, 2024',
      x: { col: 'age_in_stint', label: 'Tyre age (laps)' }, y: { col: 'value', label: 'Median lap time (s)' },
      series: [{ result_id: q.result_id, label: 'LEC', x_col: 'age_in_stint', y_col: 'value' }],
    })
    expect(r.status).toBe('ok')
    if (r.status !== 'ok') return
    save('q3-custom', r.chart_id)
    console.log('Q3', JSON.stringify(r))
  })
})
