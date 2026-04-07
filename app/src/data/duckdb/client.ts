// Singleton DuckDB-Wasm client initialises the in-browser warehouse once and exposes query() for all hooks.
// Uses a self-hosted bundle (public/duckdb/) so COEP require-corp doesn't block cross-origin assets.
import * as duckdb from '@duckdb/duckdb-wasm'
import { setDbStatus } from './status'
import { track } from '../../observability'

export type DuckDBConnection = duckdb.AsyncDuckDBConnection

// Only the EH bundle is used (COI/shared-memory causes parquet extension mismatch; mvp unused).
const EH_BUNDLE = {
  mainModule: '/duckdb/duckdb-eh.wasm',
  mainWorker: '/duckdb/duckdb-browser-eh.worker.js',
}

let db: duckdb.AsyncDuckDB | null = null
let conn: duckdb.AsyncDuckDBConnection | null = null
let initPromise: Promise<duckdb.AsyncDuckDBConnection> | null = null

async function createDb(): Promise<duckdb.AsyncDuckDBConnection> {
  setDbStatus('initializing')
  const initStart = performance.now()

  try {
    const bundle: duckdb.DuckDBBundle = {
      mainModule: EH_BUNDLE.mainModule,
      mainWorker: EH_BUNDLE.mainWorker,
      pthreadWorker: null,
    }

    // Load the worker directly from its URL. The previous blob+importScripts
    // approach silently hung under COEP require-corp; loading the worker script
    // directly (it's same-origin) boots reliably.
    const worker = new Worker(bundle.mainWorker!)
    const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING)

    db = new duckdb.AsyncDuckDB(logger, worker)
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker)

    conn = await db.connect()
    setDbStatus('ready')
    track('duckdb_init', performance.now() - initStart)
    return conn
  } catch (err) {
    console.error('[DuckDB] Initialization failed:', err)
    throw err
  }
}

// First-query latency: the cold path includes parquet registration + httpfs, so the first user
// query is the latency that matters. Tracked once; subsequent queries are not instrumented here.
let firstQueryDone = false

export async function getConnection(): Promise<duckdb.AsyncDuckDBConnection> {
  if (conn) return conn
  if (!initPromise) {
    // Add a timeout to prevent hanging indefinitely
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error('DuckDB initialization timeout (30s)'))
      }, 30000)
    })

    initPromise = Promise.race([
      createDb(),
      timeoutPromise
    ]).catch(err => {
      setDbStatus('error', err instanceof Error ? err : new Error(String(err)))
      initPromise = null
      throw err
    })
  }
  return initPromise
}

// DuckDB-Wasm returns INTEGER/BIGINT columns as JS BigInt. Coerce them to number
// so all downstream code (arithmetic, React rendering, JSON serialisation) works
// without each feature needing explicit CAST in SQL.
function coerceBigInt(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const k in obj) {
    const v = obj[k]
    out[k] = typeof v === 'bigint' ? Number(v) : v
  }
  return out
}

export async function query<T = Record<string, unknown>>(
  sql: string,
  params?: unknown[]
): Promise<T[]> {
  const c = await getConnection()
  const queryStart = firstQueryDone ? 0 : performance.now()
  const stmt = params?.length ? await c.prepare(sql) : null
  const result = stmt ? await stmt.query(...(params as unknown[])) : await c.query(sql)
  if (stmt) await stmt.close()
  if (!firstQueryDone) {
    firstQueryDone = true
    track('first_query', performance.now() - queryStart)
  }
  return result.toArray().map(row => coerceBigInt(row.toJSON()) as T)
}

export function getDb(): duckdb.AsyncDuckDB | null {
  return db
}
