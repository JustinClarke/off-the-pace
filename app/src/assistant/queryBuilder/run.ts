// AX-06: query_data. Validate -> compile -> register only the needed (view, season[, race]) files ->
// run the prepared statement on the engine's own connection under a 3 s timer -> shape the result.
// The engine is injected so the unit tests run without wasm; realEngine.ts is the browser one.
import type { Catalogue } from '../catalogue/catalogue'
import type { DataManifest } from '../../data/manifest'
import { sha256Hex } from '../cards/sha256'
import { compile, type PartitionAlias } from './compile'
import { validate } from './validate'
import { rememberResult } from './store'
import type { QueryError, QueryNoData, QueryOutcome, QueryResult, QueryRequest, QueryRow, Scalar } from './types'

export interface Engine {
  /** Register one published parquet file under `alias` (idempotent). */
  registerPartition(alias: string, url: string): Promise<void>
  /** Prepare and run on the builder's own connection; rows as plain objects. */
  prepareRun(sql: string, params: Scalar[]): Promise<Record<string, unknown>[]>
  /** Cancel the running statement and replace the connection. */
  cancel(): Promise<void>
}

export interface RunDeps {
  catalogue: Catalogue
  manifest: DataManifest
  engine: Engine
  /** Prefix for file URLs (DATA_CDN_BASE in the app). */
  dataBase?: string
  timeoutMs?: number
}

interface ManifestPartition {
  value: string | number
  path: string
  subPartitions?: { value: string | number; path: string }[]
}

function withVersion(url: string, version: string): string {
  return `${url}?v=${encodeURIComponent(version)}`
}

/** Resolve each alias to a published file from the manifest; null when the data has no such file. */
export function resolveFiles(aliases: PartitionAlias[], view: string, manifest: DataManifest, base = ''): { alias: string; url: string }[] | null {
  const table = manifest.tables.find((t) => t.name === view)
  if (!table) return null
  const out: { alias: string; url: string }[] = []
  for (const a of aliases) {
    let path: string | undefined
    if (a.season === null) {
      path = table.partitioned ? undefined : table.path
    } else {
      const part = (table.partitions as ManifestPartition[] | undefined)?.find((p) => p.value === a.season)
      path = a.race_id === null ? part?.path : part?.subPartitions?.find((s) => s.value === a.race_id)?.path
    }
    if (!path || !path.endsWith('.parquet')) return null
    out.push({ alias: a.alias, url: withVersion(`${base}${path}`, manifest.version) })
  }
  return out
}

function canonicalJson(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canonicalJson).join(',')}]`
  if (v && typeof v === 'object') {
    const o = v as Record<string, unknown>
    return `{${Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${canonicalJson(o[k])}`).join(',')}}`
  }
  return JSON.stringify(v)
}

export function resultId(canonical: unknown, manifestVersion: string): string {
  return sha256Hex(`${canonicalJson(canonical)}|${manifestVersion}`).slice(0, 12)
}

function toNumber(v: unknown): unknown {
  return typeof v === 'bigint' ? Number(v) : v
}

function round(v: unknown, decimals: number): unknown {
  const x = toNumber(v)
  if (typeof x !== 'number' || !Number.isFinite(x)) return x
  const f = 10 ** decimals
  return Math.round(x * f) / f
}

export class TimeoutError extends Error {}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined
  const t = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new TimeoutError(`query exceeded ${ms} ms`)), ms)
  })
  return Promise.race([p, t]).finally(() => clearTimeout(timer))
}

/** The query_data tool. Never throws: every failure is a QueryError or QueryNoData. */
export async function runQuery(
  req: QueryRequest | unknown,
  deps: RunDeps,
  /** INTERNAL ONLY (AX-11): a third function argument, so it can never arrive in a model request. */
  internal: { rowCap?: number } = {},
): Promise<QueryOutcome> {
  const { catalogue, manifest, engine } = deps
  const timeoutMs = deps.timeoutMs ?? catalogue.limits.timeout_ms
  const v = validate(req, catalogue)
  if ('status' in v) return v
  const view = v.view
  const noData = (reason: string): QueryNoData => ({ status: 'no_data', view: view.name, reason })

  let compiled
  try {
    compiled = compile(v, { rowCap: internal.rowCap })
  } catch {
    return { status: 'error', code: 'bad_value', field: 'request', message: 'request could not be compiled' }
  }
  if (compiled.aliases.length === 0) return noData('no published season matches the season filter')
  const files = resolveFiles(compiled.aliases, view.name, manifest, deps.dataBase ?? '')
  if (!files) return noData('no published file for that season or race')

  let raw: Record<string, unknown>[]
  try {
    for (const f of files) await engine.registerPartition(f.alias, f.url)
    raw = await withTimeout(engine.prepareRun(compiled.sql, compiled.params), timeoutMs)
  } catch (e) {
    if (e instanceof TimeoutError) {
      try {
        await engine.cancel()
      } catch {
        /* the connection is replaced either way */
      }
      const out: QueryError = { status: 'error', code: 'timeout', field: 'request', message: `stopped after ${timeoutMs} ms; narrow the filters` }
      return out
    }
    return noData(`the query could not run: ${e instanceof Error ? e.message.slice(0, 120) : 'error'}`)
  }

  const d = catalogue.limits.decimals
  const groupCols = v.group_by.map((c) => c.name)
  const rows: QueryRow[] = []
  let total = 0
  for (const r of raw) {
    const n = Number(toNumber(r.n) ?? 0)
    if (!(n > 0)) continue
    total = Number(toNumber(r.total_groups) ?? 0)
    const row: QueryRow = { value: round(r.value, d) as number | null, n }
    for (const g of groupCols) row[g] = round(r[g], d) as Scalar | null
    if (n < catalogue.limits.thin_n) row.thin = true
    rows.push(row)
  }
  if (rows.length === 0) return noData('no rows match the filters')

  const notes: string[] = [view.note]
  for (const d of view.default_filters) {
    if (!v.canonical.filters.some((f) => f.col === d.col && f.val !== d.val)) {
      notes.push(`Default filter applied: ${d.col} ${d.op} ${String(d.val)}.`)
    }
  }
  if (rows.some((r) => r.thin)) notes.push(`Rows with n < ${catalogue.limits.thin_n} are marked thin: treat them as a small sample.`)
  notes.push('A plain aggregate computed from published data, not a fact card, rating or model output.')

  const rows_shown = Math.min(rows.length, internal.rowCap ?? catalogue.limits.max_limit)
  const result: QueryResult = {
    status: 'ok',
    view: view.name,
    filters_applied: v.canonical.filters,
    grain: view.grain,
    aggregate: v.canonical.aggregate,
    group_by: v.canonical.group_by,
    rows: rows.slice(0, rows_shown),
    row_count: Math.max(total, rows_shown),
    rows_shown,
    rows_dropped: Math.max(total, rows_shown) - rows_shown,
    label: 'computed_not_card',
    notes,
    result_id: resultId(internal.rowCap ? { ...v.canonical, rowCap: internal.rowCap } : v.canonical, manifest.version),
  }
  rememberResult(result)
  return result
}
