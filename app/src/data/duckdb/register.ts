// Registers Parquet files as DuckDB views (idempotent); used by hooks before issuing queries.
import * as duckdb from '@duckdb/duckdb-wasm'
import { getConnection, getDb } from './client'
import type { DataManifest } from '../manifest'
import { getTablePath } from '../manifest'

const registered = new Set<string>()
// In-flight registrations: prevents concurrent calls for the same view from both
// issuing DDL against the shared connection, which can corrupt query state.
const pending = new Map<string, Promise<void>>()

export async function registerParquet(tableName: string, url: string): Promise<void> {
  if (registered.has(tableName)) return
  // Coalesce concurrent callers onto the same in-flight promise
  const inflight = pending.get(tableName)
  if (inflight) return inflight

  const work = (async () => {
    const conn = await getConnection()
    const db = getDb()
    if (!db) throw new Error('DuckDB not initialised')

    const absoluteUrl = new URL(url, window.location.origin).href

    if (url.split('?')[0].endsWith('.parquet')) {
      // Single-file parquet: register via HTTP then create a view over it.
      // DuckDB-Wasm resolves server-absolute paths against its virtual filesystem
      // (not the HTTP server), so we must register the file by HTTP URL first.
      const fileName = `${tableName}.parquet`
      await db.registerFileURL(fileName, absoluteUrl, duckdb.DuckDBDataProtocol.HTTP, false)
      await conn.query(
        `CREATE OR REPLACE VIEW ${tableName} AS SELECT * FROM parquet_scan('${fileName}')`
      )
    } else {
      // Directory path (e.g. fct_ghost_car_pace/2024/): create a view using an
      // HTTP glob so DuckDB fetches each race file on demand via range requests.
      await conn.query(
        `CREATE OR REPLACE VIEW ${tableName} AS SELECT * FROM parquet_scan('${absoluteUrl}/*.parquet')`
      )
    }

    registered.add(tableName)
    pending.delete(tableName)
  })()

  // Store before awaiting so subsequent synchronous callers see it
  pending.set(tableName, work.catch(err => { pending.delete(tableName); throw err }))
  return work
}

/**
 * Registers a partitioned table (one parquet per season) as a single UNION ALL view
 * under the bare table name, so the Query Lab can query it without picking a season.
 * Each partition file is registered by HTTP URL (DuckDB-Wasm resolves server-absolute
 * paths against its virtual filesystem, not the HTTP server) then UNION ALL-ed.
 */
export async function registerPartitionedParquet(name: string, manifest: DataManifest): Promise<void> {
  if (registered.has(name)) return
  const inflight = pending.get(name)
  if (inflight) return inflight

  const table = manifest.tables.find(t => t.name === name)
  if (!table) throw new Error(`Table not found in manifest: ${name}`)
  if (!table.partitioned || !table.partitions?.length) {
    // Not partitioned (or no partitions) — fall back to the single-file registrar.
    return registerParquet(name, getTablePath(manifest, name))
  }

  const work = (async () => {
    const conn = await getConnection()
    const db = getDb()
    if (!db) throw new Error('DuckDB not initialised')

    const selects: string[] = []
    for (const part of table.partitions!) {
      const url = getTablePath(manifest, name, part.value)
      const absoluteUrl = new URL(url, window.location.origin).href
      const fileName = `${name}__${part.value}.parquet`
      await db.registerFileURL(fileName, absoluteUrl, duckdb.DuckDBDataProtocol.HTTP, false)
      selects.push(`SELECT * FROM parquet_scan('${fileName}')`)
    }
    await conn.query(`CREATE OR REPLACE VIEW ${name} AS ${selects.join(' UNION ALL ')}`)

    registered.add(name)
    pending.delete(name)
  })()

  pending.set(name, work.catch(err => { pending.delete(name); throw err }))
  return work
}

export async function registerParquetMany(tables: Array<{ name: string; url: string }>): Promise<void> {
  await Promise.all(tables.map(({ name, url }) => registerParquet(name, url)))
}

export function isRegistered(tableName: string): boolean {
  return registered.has(tableName)
}

export function clearRegistrations(): void {
  registered.clear()
}
