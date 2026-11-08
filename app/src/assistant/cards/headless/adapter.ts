// AX-04 headless adapter: the three browser-only seams of the query layer, re-implemented over
// local files for Node (AX-04 finding 3).
//   data/duckdb/client.ts    Worker + wasm         -> duckdb-wasm's Node blocking bundle
//   data/duckdb/register.ts  new URL(url, origin)  -> URL mapped back to a local path, ?v= ignored
//   data/manifest.ts         fetch(CDN manifest)   -> the local _manifest.json
// The seam modules (client.ts, register.ts, manifest.ts in this folder) re-export from here;
// scripts/build-cards.mjs swaps them in by resolved path. The engine is the same DuckDB build the
// browser runs (@duckdb/duckdb-wasm, EH bundle), so SQL semantics match the page.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve, sep } from 'node:path'
import type { DataManifest } from '../../../data/manifest'

/** The SQL engine the adapter drives. Synchronous: duckdb-wasm's blocking Node API. */
export interface Engine {
  registerFile(name: string, localPath: string): void
  run(sql: string, params?: unknown[]): Record<string, unknown>[]
  close(): void
}

export interface HeadlessOptions {
  /** A data root laid out like app/public/data (holds _manifest.json). */
  dataDir: string
  /** CDN base the app prefixes to manifest paths; stripped when mapping a URL to a file. */
  cdnBase?: string
}

/**
 * Map a URL the query layer built (getTablePath / getRaceFilePath) to a file under dataDir.
 * Accepts CDN-absolute, origin-absolute and server-relative forms; drops the ?v= cache-buster.
 * Refuses anything that is not under /data/ or that escapes dataDir.
 */
export function urlToLocalPath(url: string, dataDir: string, cdnBase = ''): string {
  let path = url.split('?')[0].split('#')[0]
  if (cdnBase && path.startsWith(cdnBase)) path = path.slice(cdnBase.length)
  else if (/^[a-z]+:\/\//i.test(path)) path = new URL(path).pathname
  if (!path.startsWith('/data/')) throw new Error(`not a published data path: ${url}`)
  const root = resolve(dataDir)
  const local = resolve(root, decodeURIComponent(path.slice('/data/'.length)))
  if (local !== root && !local.startsWith(root + sep)) throw new Error(`path escapes the data dir: ${url}`)
  return local
}

// DuckDB-Wasm returns INTEGER/BIGINT as BigInt; the browser client coerces them to number.
function coerceBigInt(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const k in obj) {
    const v = obj[k]
    out[k] = typeof v === 'bigint' ? Number(v) : v
  }
  return out
}

/** The query layer over an engine and a data dir. Pure enough to unit-test with a fake engine. */
export function createAdapter(opts: HeadlessOptions, engine: Engine) {
  const registered = new Set<string>()
  const dataDir = resolve(opts.dataDir)
  const cdnBase = opts.cdnBase ?? ''
  let manifest: DataManifest | null = null

  function loadManifestSync(): DataManifest {
    if (!manifest) manifest = JSON.parse(readFileSync(join(dataDir, '_manifest.json'), 'utf8')) as DataManifest
    return manifest
  }

  async function query<T = Record<string, unknown>>(sql: string, params?: unknown[]): Promise<T[]> {
    return engine.run(sql, params).map((r) => coerceBigInt(r) as T)
  }

  async function registerParquet(tableName: string, url: string): Promise<void> {
    if (registered.has(tableName)) return
    const local = urlToLocalPath(url, dataDir, cdnBase)
    if (!existsSync(local)) throw new Error(`${tableName}: ${local} is not in the scratch export`)
    if (statSync(local).isFile()) {
      const fileName = `${tableName}.parquet`
      engine.registerFile(fileName, local)
      engine.run(`CREATE OR REPLACE VIEW ${tableName} AS SELECT * FROM parquet_scan('${fileName}')`)
    } else {
      // Directory (the browser globs dir/*.parquet over HTTP): register each file, scan the list.
      const files = readdirSync(local).filter((f) => f.endsWith('.parquet')).sort()
      if (!files.length) throw new Error(`${tableName}: no parquet files under ${local}`)
      const names = files.map((f, i) => {
        const n = `${tableName}__${i}.parquet`
        engine.registerFile(n, join(local, f))
        return `'${n}'`
      })
      engine.run(`CREATE OR REPLACE VIEW ${tableName} AS SELECT * FROM parquet_scan([${names.join(', ')}])`)
    }
    registered.add(tableName)
  }

  async function registerPartitionedParquet(name: string, m: DataManifest, getTablePath: (m: DataManifest, n: string, p?: string | number) => string): Promise<void> {
    if (registered.has(name)) return
    const table = m.tables.find((t) => t.name === name)
    if (!table) throw new Error(`Table not found in manifest: ${name}`)
    if (!table.partitioned || !table.partitions?.length) return registerParquet(name, getTablePath(m, name))
    const selects: string[] = []
    for (const part of table.partitions) {
      const fileName = `${name}__${part.value}.parquet`
      engine.registerFile(fileName, urlToLocalPath(getTablePath(m, name, part.value), dataDir, cdnBase))
      selects.push(`SELECT * FROM parquet_scan('${fileName}')`)
    }
    engine.run(`CREATE OR REPLACE VIEW ${name} AS ${selects.join(' UNION ALL ')}`)
    registered.add(name)
  }

  return {
    dataDir,
    query,
    registerParquet,
    registerPartitionedParquet,
    isRegistered: (t: string) => registered.has(t),
    clearRegistrations: () => registered.clear(),
    loadManifest: async () => loadManifestSync(),
    peekManifest: () => manifest,
    close: () => engine.close(),
  }
}

export type Adapter = ReturnType<typeof createAdapter>

/** duckdb-wasm's Node blocking bundle (AX-04 spike: reads local parquet, no new dependency). */
export async function createWasmEngine(): Promise<Engine> {
  const duckdb = await import('@duckdb/duckdb-wasm/blocking')
  const { createRequire } = await import('node:module')
  const req = createRequire(import.meta.url)
  const dist = join(req.resolve('@duckdb/duckdb-wasm/dist/duckdb-node-blocking.cjs'), '..')
  const db = await duckdb.createDuckDB(
    {
      mvp: { mainModule: join(dist, 'duckdb-mvp.wasm'), mainWorker: join(dist, 'duckdb-node-mvp.worker.cjs') },
      eh: { mainModule: join(dist, 'duckdb-eh.wasm'), mainWorker: join(dist, 'duckdb-node-eh.worker.cjs') },
    },
    new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING),
    duckdb.NODE_RUNTIME,
  )
  await db.instantiate()
  const conn = db.connect()
  return {
    registerFile: (name, localPath) => {
      db.registerFileURL(name, localPath, duckdb.DuckDBDataProtocol.NODE_FS, false)
    },
    run: (sql, params) => {
      if (params?.length) {
        const stmt = conn.prepare(sql)
        try {
          return stmt.query(...params).toArray().map((r: { toJSON(): Record<string, unknown> }) => ({ ...r.toJSON() }))
        } finally {
          stmt.close()
        }
      }
      return conn.query(sql).toArray().map((r: { toJSON(): Record<string, unknown> }) => ({ ...r.toJSON() }))
    },
    close: () => {
      conn.close()
    },
  }
}

// ---- module singleton used by the seam modules ----

let active: Adapter | null = null

/** Configure the singleton the seam modules use. Call once per process before loading features. */
export async function configureHeadless(opts: HeadlessOptions, engine?: Engine): Promise<Adapter> {
  active?.close()
  active = createAdapter(opts, engine ?? (await createWasmEngine()))
  return active
}

export function headless(): Adapter {
  if (!active) throw new Error('headless adapter not configured: call configureHeadless({ dataDir }) first')
  return active
}
