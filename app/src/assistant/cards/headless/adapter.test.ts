// AX-04 adapter: URL-to-path mapping (?v= ignored), registerParquet idempotent, directories and
// partitions registered file by file. Uses a fake engine; the real engine runs in the parity test.
// @vitest-environment node
import { describe, it, expect, beforeAll } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createAdapter, urlToLocalPath } from './adapter'
import type { Engine } from './adapter'
import { getTablePath } from '../../../data/manifest'
import type { DataManifest } from '../../../data/manifest'

const CDN = 'https://storage.googleapis.com/off-the-pace-cdn'

function fakeEngine() {
  const files: [string, string][] = []
  const sql: string[] = []
  const engine: Engine = {
    registerFile: (n, p) => void files.push([n, p]),
    run: (s) => {
      sql.push(s)
      return [{ n: 3n, s: 'x' }]
    },
    close: () => {},
  }
  return { engine, files, sql }
}

let dir: string
beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), 'ax04-adapter-'))
  mkdirSync(join(dir, 'facts/fct_lap_residuals'), { recursive: true })
  mkdirSync(join(dir, 'intermediates'), { recursive: true })
  for (const f of ['facts/fct_lap_residuals/2024.parquet', 'facts/fct_lap_residuals/2023.parquet', 'intermediates/era.parquet']) {
    writeFileSync(join(dir, f), 'PAR1')
  }
  const manifest: DataManifest = {
    version: 'abc123',
    generatedAt: '',
    tables: [
      { name: 'era', path: '/data/intermediates/era.parquet', partitioned: false },
      {
        name: 'fct_lap_residuals',
        path: '/data/facts/fct_lap_residuals',
        partitioned: true,
        partitions: [
          { value: 2023, path: '/data/facts/fct_lap_residuals/2023.parquet' },
          { value: 2024, path: '/data/facts/fct_lap_residuals/2024.parquet' },
        ],
      },
    ],
  }
  writeFileSync(join(dir, '_manifest.json'), JSON.stringify(manifest))
})

describe('AX-04 urlToLocalPath', () => {
  it('maps CDN, origin-absolute and server-relative URLs, ignoring ?v=', () => {
    const want = join(dir, 'intermediates/era.parquet')
    expect(urlToLocalPath(`${CDN}/data/intermediates/era.parquet?v=abc123`, dir, CDN)).toBe(want)
    expect(urlToLocalPath('http://localhost:5173/data/intermediates/era.parquet?v=zzz', dir)).toBe(want)
    expect(urlToLocalPath('/data/intermediates/era.parquet', dir)).toBe(want)
    expect(urlToLocalPath('/data/facts/fct_lap_residuals', dir)).toBe(join(dir, 'facts/fct_lap_residuals'))
  })
  it('refuses paths outside /data/ or escaping the data dir', () => {
    expect(() => urlToLocalPath('/models/x.onnx', dir)).toThrow(/not a published data path/)
    expect(() => urlToLocalPath('/data/../../etc/passwd', dir)).toThrow(/escapes/)
    expect(() => urlToLocalPath('/data/%2e%2e/%2e%2e/etc', dir)).toThrow(/escapes/)
  })
})

describe('AX-04 createAdapter', () => {
  it('registerParquet is idempotent per table name', async () => {
    const { engine, files, sql } = fakeEngine()
    const a = createAdapter({ dataDir: dir, cdnBase: CDN }, engine)
    await a.registerParquet('era', `${CDN}/data/intermediates/era.parquet?v=1`)
    await a.registerParquet('era', `${CDN}/data/intermediates/era.parquet?v=2`)
    expect(files).toEqual([['era.parquet', join(dir, 'intermediates/era.parquet')]])
    expect(sql.filter((s) => s.startsWith('CREATE'))).toHaveLength(1)
    expect(a.isRegistered('era')).toBe(true)
  })
  it('registers a directory file by file, like the browser glob', async () => {
    const { engine, files, sql } = fakeEngine()
    const a = createAdapter({ dataDir: dir }, engine)
    await a.registerParquet('laps_dir', '/data/facts/fct_lap_residuals')
    expect(files.map((f) => f[1])).toEqual([join(dir, 'facts/fct_lap_residuals/2023.parquet'), join(dir, 'facts/fct_lap_residuals/2024.parquet')])
    expect(sql[0]).toMatch(/parquet_scan\(\['laps_dir__0\.parquet', 'laps_dir__1\.parquet'\]\)/)
  })
  it('registers a partitioned table as a UNION ALL view through the real getTablePath', async () => {
    const { engine, files, sql } = fakeEngine()
    const a = createAdapter({ dataDir: dir, cdnBase: CDN }, engine)
    const m = await a.loadManifest()
    // The real getTablePath prefixes DATA_CDN_BASE; map it back with the same base.
    const base = getTablePath(m, 'era').replace('/data/intermediates/era.parquet?v=abc123', '')
    const b = createAdapter({ dataDir: dir, cdnBase: base }, engine)
    await b.registerPartitionedParquet('fct_lap_residuals', m, getTablePath)
    expect(files.map((f) => f[0])).toEqual(['fct_lap_residuals__2023.parquet', 'fct_lap_residuals__2024.parquet'])
    expect(sql.at(-1)).toMatch(/UNION ALL/)
  })
  it('fails loudly on a table missing from the export', async () => {
    const a = createAdapter({ dataDir: dir }, fakeEngine().engine)
    await expect(a.registerParquet('nope', '/data/marts/nope.parquet')).rejects.toThrow(/not in the scratch export/)
  })
  it('query coerces BigInt to number, like the browser client', async () => {
    const a = createAdapter({ dataDir: dir }, fakeEngine().engine)
    expect(await a.query('select 1')).toEqual([{ n: 3, s: 'x' }])
  })
  it('loadManifest reads the local _manifest.json', async () => {
    const a = createAdapter({ dataDir: dir }, fakeEngine().engine)
    expect(a.peekManifest()).toBeNull()
    expect((await a.loadManifest()).version).toBe('abc123')
    expect(a.peekManifest()?.version).toBe('abc123')
  })
})
