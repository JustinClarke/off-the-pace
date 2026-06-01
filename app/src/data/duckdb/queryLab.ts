// Query Lab engine: read-only SQL runner over the gold warehouse. Resolves referenced
// manifest tables, registers only those (single + partitioned UNION views), executes on a
// dedicated connection, and shapes the result into dynamic columns + an instrument readout.
import type { AsyncDuckDBConnection } from '@duckdb/duckdb-wasm'
import { getConnection, getDb } from './client'
import { registerParquet, registerPartitionedParquet } from './register'
import { loadManifest, getTablePath, type DataManifest } from '../manifest'

export class QueryLabError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'QueryLabError'
  }
}

// Materialise at most this many rows; the grid renders a subset, CSV exports the full set.
export const MAX_ROWS = 5000

export interface LabResult {
  columns: string[]
  rows: Record<string, unknown>[]
  rowCount: number
  truncated: boolean
  elapsedMs: number
}

// Statement forms the lab permits. Anything that mutates the shared catalog or filesystem
// (CREATE/DROP/ALTER/INSERT/UPDATE/DELETE/ATTACH/COPY/INSTALL/LOAD) is rejected — the shared
// view catalog means a single DROP would break every other page until a reload.
const ALLOWED_LEADING = /^(SELECT|WITH|EXPLAIN|DESCRIBE|DESC|SUMMARIZE|SHOW|PRAGMA|PIVOT|TABLE|VALUES|FROM)\b/i
const FORBIDDEN = /\b(CREATE|DROP|ALTER|INSERT|UPDATE|DELETE|TRUNCATE|ATTACH|DETACH|COPY|INSTALL|LOAD|CALL|SET|RESET|EXPORT|IMPORT)\b/i

/** Strip line and block SQL comments and surrounding whitespace. */
function stripComments(sql: string): string {
  return sql
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/--[^\n]*/g, ' ')
    .trim()
}

/**
 * Throws QueryLabError unless `sql` is a single read-only statement. PRAGMA is allowed only
 * for the read-only `table_info` introspection form.
 */
export function assertReadOnly(sql: string): void {
  const cleaned = stripComments(sql)
  if (!cleaned) throw new QueryLabError('Empty query.')

  // Reject multiple statements (ignore a single trailing semicolon).
  const withoutTrailing = cleaned.replace(/;\s*$/, '')
  if (withoutTrailing.includes(';')) {
    throw new QueryLabError('Only a single statement may be run at a time.')
  }

  if (!ALLOWED_LEADING.test(withoutTrailing)) {
    throw new QueryLabError('Only read-only queries are allowed (SELECT, WITH, EXPLAIN, DESCRIBE, SUMMARIZE, SHOW, PRAGMA table_info, PIVOT).')
  }

  if (/^PRAGMA\b/i.test(withoutTrailing) && !/^PRAGMA\s+table_info\b/i.test(withoutTrailing)) {
    throw new QueryLabError('Only `PRAGMA table_info(...)` is permitted.')
  }

  if (FORBIDDEN.test(withoutTrailing)) {
    throw new QueryLabError('This statement type is not allowed in the read-only Query Lab.')
  }
}

/**
 * Extracts identifiers from `sql` that match manifest table names. Matching is done against
 * the manifest's known names (the dim_/fct_/int_/mart_ prefixes plus the two literals), so
 * column names and aliases that happen to share a prefix can't cause spurious registration.
 */
export function resolveTablesInSql(sql: string, manifest: DataManifest): string[] {
  const cleaned = stripComments(sql).toLowerCase()
  // Word tokens, including the dotted-prefix table names.
  const tokens = new Set(cleaned.match(/[a-z_][a-z0-9_]*/g) ?? [])
  return manifest.tables.map(t => t.name).filter(name => tokens.has(name.toLowerCase()))
}

let labConn: AsyncDuckDBConnection | null = null

/** Lazily opens a dedicated connection off the shared db to isolate lab session state. */
export async function getLabConnection(): Promise<AsyncDuckDBConnection> {
  if (labConn) return labConn
  await getConnection() // ensure the engine is booted
  const db = getDb()
  if (!db) throw new QueryLabError('DuckDB not initialised')
  labConn = await db.connect()
  return labConn
}

// DuckDB-Wasm returns INTEGER/BIGINT columns as JS BigInt; coerce so React/CSV/JSON work.
function coerceBigInt(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const k in obj) {
    const v = obj[k]
    out[k] = typeof v === 'bigint' ? Number(v) : v
  }
  return out
}

async function registerReferenced(names: string[], manifest: DataManifest): Promise<void> {
  await Promise.all(names.map(name => {
    const table = manifest.tables.find(t => t.name === name)
    if (table?.partitioned) return registerPartitionedParquet(name, manifest)
    return registerParquet(name, getTablePath(manifest, name))
  }))
}

/**
 * Runs a single read-only query: guards it, registers referenced tables, executes on the
 * dedicated lab connection, coerces BigInts, and caps the result at MAX_ROWS.
 */
export async function runLabQuery(sql: string): Promise<LabResult> {
  assertReadOnly(sql)

  const manifest = await loadManifest()
  const referenced = resolveTablesInSql(sql, manifest)
  await registerReferenced(referenced, manifest)

  const conn = await getLabConnection()
  const started = performance.now()
  const result = await conn.query(sql)
  const elapsedMs = performance.now() - started

  const all = result.toArray()
  const rowCount = all.length
  const truncated = rowCount > MAX_ROWS
  const rows = (truncated ? all.slice(0, MAX_ROWS) : all).map(r => coerceBigInt(r.toJSON()))
  const columns = result.schema.fields.map(f => f.name)

  return { columns, rows, rowCount: truncated ? MAX_ROWS : rowCount, truncated, elapsedMs }
}
