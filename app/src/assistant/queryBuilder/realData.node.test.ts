// @vitest-environment node
// AX-06: runQuery against the real AX-05 qv_* files on duckdb-wasm's Node bundle (the browser's
// DuckDB build), checked against an independent SQL oracle. Skipped unless AX06_DATA_DIR points at
// a scratch export root (the one AX-05 wrote with export_app_data.py --out).
import { describe, it, expect, beforeAll } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createAdapter, createWasmEngine, type Adapter } from '../cards/headless/adapter'
import { parseCatalogue, type Catalogue } from '../catalogue/catalogue'
import type { DataManifest } from '../../data/manifest'
import { runQuery, type Engine } from './run'
import type { QueryResult } from './types'

const DIR = process.env.AX06_DATA_DIR
const enabled = !!DIR && existsSync(join(DIR, 'assistant', 'catalogue.json'))

describe.skipIf(!enabled)('query_data on the scratch export', () => {
  let adapter: Adapter
  let catalogue: Catalogue
  let manifest: DataManifest
  let engine: Engine & { aliases: string[] }

  beforeAll(async () => {
    adapter = createAdapter({ dataDir: DIR! }, await createWasmEngine())
    catalogue = parseCatalogue(JSON.parse(readFileSync(join(DIR!, 'assistant', 'catalogue.json'), 'utf8')))
    manifest = JSON.parse(readFileSync(join(DIR!, '_manifest.json'), 'utf8')) as DataManifest
    const aliases: string[] = []
    engine = {
      aliases,
      registerPartition: async (alias, url) => {
        aliases.push(alias)
        await adapter.registerParquet(alias, url)
      },
      prepareRun: (sql, params) => adapter.query(sql, params),
      cancel: async () => undefined,
    }
  })

  const oracle = async (sql: string) => adapter.query<Record<string, number | string>>(sql)
  const file = (rel: string) => `'${join(DIR!, rel).replace(/'/g, "''")}'`

  it('median lap time per driver, one race, equals an oracle over the parquet', async () => {
    const out = (await runQuery(
      {
        view: 'qv_laps',
        filters: [{ col: 'season', op: 'eq', val: 2024 }, { col: 'race_id', op: 'eq', val: '2024_8' }],
        group_by: ['driver_id'],
        aggregate: { fn: 'median', col: 'lap_time_s' },
        order: 'value_asc',
        limit: 25,
      },
      { catalogue, manifest, engine },
    )) as QueryResult
    expect(out.status).toBe('ok')
    expect(engine.aliases).toContain('qv_laps_2024')
    const ref = await oracle(
      `SELECT driver_id, round(median(lap_time_s), 3) AS v, count(lap_time_s) AS n, count(*) OVER () AS g
       FROM read_parquet(${file('assistant/qv/qv_laps/2024.parquet')})
       WHERE race_id = '2024_8' AND NOT is_major_outlier_lap GROUP BY driver_id ORDER BY v, driver_id`,
    )
    expect(out.row_count).toBe(Number(ref[0].g))
    expect(out.rows.map((r) => [r.driver_id, r.value, r.n])).toEqual(ref.slice(0, out.rows_shown).map((r) => [r.driver_id, Number(r.v), Number(r.n)]))
  })

  it('two-season count by compound and an IN filter with a planted string', async () => {
    const out = (await runQuery(
      {
        view: 'qv_stints',
        filters: [{ col: 'season', op: 'in', val: [2023, 2024] }, { col: 'driver_id', op: 'in', val: ['LEC', "'; DROP TABLE x; --"] }],
        group_by: ['compound'],
        aggregate: { fn: 'count', col: 'stints' },
        order: 'group_asc',
      },
      { catalogue, manifest, engine },
    )) as QueryResult
    expect(out.status).toBe('ok')
    const ref = await oracle(
      `SELECT compound, count(*) AS v FROM read_parquet(${file('assistant/qv/qv_stints.parquet')})
       WHERE season IN (2023, 2024) AND driver_id = 'LEC' GROUP BY compound ORDER BY compound NULLS LAST`,
    )
    expect(out.rows.map((r) => [r.compound, r.value])).toEqual(ref.slice(0, 10).map((r) => [r.compound, Number(r.v)]))
  })

  it('teammate corner deltas for one race register only that race file', async () => {
    const before = engine.aliases.length
    const out = (await runQuery(
      {
        view: 'qv_teammate_corners',
        filters: [{ col: 'season', op: 'eq', val: 2024 }, { col: 'race_id', op: 'eq', val: '2024_8' }],
        group_by: ['driver_a', 'corner_name'],
        aggregate: { fn: 'avg', col: 'v_min_delta_kph' },
        limit: 5,
      },
      { catalogue, manifest, engine },
    )) as QueryResult
    expect(out.status).toBe('ok')
    expect(engine.aliases.length - before).toBe(1)
    expect(out.rows_shown).toBe(5)
    expect(out.rows_dropped).toBe(out.row_count - 5)
  })
})
