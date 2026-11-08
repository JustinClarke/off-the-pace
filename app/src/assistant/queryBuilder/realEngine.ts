// AX-06: the browser engine for query_data. Its own connection off the shared DuckDB-wasm db
// (views registered through registerParquet are visible to it), prepared statements only, and a
// cancel that sends cancelSent() and then replaces the connection (whether a cancelled connection
// stays usable is not relied on). Uses none of runLabQuery / assertReadOnly /
// registerPartitionedParquet (AXW5).
import type { AsyncDuckDBConnection } from '@duckdb/duckdb-wasm'
import { getConnection, getDb } from '../../data/duckdb/client'
import { registerParquet } from '../../data/duckdb/register'
import { DATA_CDN_BASE, loadManifest } from '../../data/manifest'
import { loadCatalogue } from '../catalogue/catalogue'
import { runQuery, type Engine } from './run'
import type { QueryOutcome, Scalar } from './types'

let conn: AsyncDuckDBConnection | null = null

async function connection(): Promise<AsyncDuckDBConnection> {
  if (conn) return conn
  await getConnection() // boots the engine
  const db = getDb()
  if (!db) throw new Error('DuckDB not initialised')
  conn = await db.connect()
  return conn
}

export const realEngine: Engine = {
  async registerPartition(alias, url) {
    await registerParquet(alias, url)
  },
  async prepareRun(sql: string, params: Scalar[]) {
    const c = await connection()
    const stmt = await c.prepare(sql)
    try {
      // send() runs the statement as a pending query the worker polls in steps, so cancelSent()
      // can interrupt it; query() would block the worker until it finished (found in the e2e run).
      const reader = await stmt.send(...params)
      const out: Record<string, unknown>[] = []
      for await (const batch of reader) {
        for (const r of batch.toArray()) out.push(r.toJSON() as Record<string, unknown>)
      }
      return out
    } finally {
      await stmt.close().catch(() => undefined)
    }
  },
  async cancel() {
    const c = conn
    conn = null
    if (!c) return
    await c.cancelSent().catch(() => false)
    await c.close().catch(() => undefined)
  },
}

/** query_data in the app: catalogue and manifest from the data host, the real engine. */
export async function queryData(req: unknown): Promise<QueryOutcome> {
  const [catalogue, manifest] = await Promise.all([loadCatalogue(), loadManifest()])
  return runQuery(req, { catalogue, manifest, engine: realEngine, dataBase: DATA_CDN_BASE })
}

// Dev-only hook for app/e2e/query-builder.e2e.ts. import.meta.env.DEV is false in a production build,
// so the block is removed from the bundle.
if (import.meta.env.DEV && typeof window !== 'undefined') {
  ;(window as unknown as Record<string, unknown>).__axQueryBuilder = {
    queryData,
    engine: realEngine,
    runSlow: async (ms: number) => {
      const c = await connection()
      const started = performance.now()
      const slow = c.send(`SELECT sum(hash(a.range * b.range)) FROM range(${Math.max(1, Math.floor(ms)) * 2000}) a, range(100000) b`)
      const timeout = new Promise((r) => setTimeout(() => r('timeout'), 3000))
      const outcome = await Promise.race([slow.then(async (r) => { for await (const b of r) void b; return 'done' }), timeout])
      if (outcome === 'timeout') await realEngine.cancel()
      const after = await realEngine.prepareRun('SELECT 42 AS x', [])
      return { outcome, elapsed: performance.now() - started, after }
    },
  }
}
