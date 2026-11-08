// AX-05: the query catalogue type and loader. The catalogue is emitted by the export
// (scripts/assistant_query_views.py) as /data/assistant/catalogue.json; the bounded query builder
// (AX-06) validates every request against it and takes every SQL identifier from it.
import { DATA_CDN_BASE } from '../../data/manifest'

export const OP_NAMES = ['eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'in', 'between'] as const
export type OpName = (typeof OP_NAMES)[number]
export const AGG_NAMES = ['count', 'avg', 'median', 'min', 'max', 'sum'] as const
export type AggName = (typeof AGG_NAMES)[number]
export const ORDER_NAMES = ['value_asc', 'value_desc', 'group_asc'] as const
export type OrderName = (typeof ORDER_NAMES)[number]
export type ColumnType = 'string' | 'integer' | 'number' | 'boolean'

export interface CatalogueColumn {
  name: string
  role: 'dimension' | 'measure'
  type: ColumnType
  ops: OpName[]
  aggregates: Exclude<AggName, 'count'>[]
  group_by: boolean
  description: string
}

export interface CatalogueFilter {
  col: string
  op: OpName
  val: string | number | boolean
}

export interface CatalogueView {
  name: string
  grain: string
  note: string
  /** The name a count request uses as aggregate.col (compiled to COUNT(*)). */
  count_name: string
  required_filters: string[]
  /** Grouping by the key requires a filter on each listed column. */
  group_by_requires: Record<string, string[]>
  /** Applied unless the request filters on the same column. */
  default_filters: CatalogueFilter[]
  max_seasons: number | null
  partition_key: 'season' | null
  sub_partition_key: 'race_id' | null
  columns: CatalogueColumn[]
}

export interface CatalogueLimits {
  max_filters: number
  max_in_values: number
  max_group_by: number
  max_limit: number
  max_string_length: number
  timeout_ms: number
  thin_n: number
  decimals: number
}

export interface Catalogue {
  schema_version: number
  catalogue_version: string
  seasons: number[]
  ops: Record<OpName, { arity: 'scalar' | 'list' | 'pair' }>
  aggregates: Record<AggName, string>
  orders: OrderName[]
  limits: CatalogueLimits
  views: CatalogueView[]
}

function fail(msg: string): never {
  throw new Error(`catalogue.json: ${msg}`)
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const isStrArr = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === 'string')

/** Runtime check that parsed JSON has the Catalogue shape; returns it typed or throws. */
export function parseCatalogue(raw: unknown): Catalogue {
  if (!isObj(raw)) fail('not an object')
  if (raw.schema_version !== 1) fail(`unsupported schema_version ${String(raw.schema_version)}`)
  if (typeof raw.catalogue_version !== 'string' || !/^[0-9a-f]{64}$/.test(raw.catalogue_version)) fail('catalogue_version')
  if (!Array.isArray(raw.seasons) || !raw.seasons.every((s) => Number.isInteger(s))) fail('seasons')
  if (!isObj(raw.ops) || !OP_NAMES.every((o) => isObj((raw.ops as Record<string, unknown>)[o]))) fail('ops')
  if (!isObj(raw.aggregates) || !AGG_NAMES.every((a) => a in (raw.aggregates as object))) fail('aggregates')
  if (!isStrArr(raw.orders) || !raw.orders.every((o) => (ORDER_NAMES as readonly string[]).includes(o))) fail('orders')
  if (!isObj(raw.limits)) fail('limits')
  for (const k of ['max_filters', 'max_in_values', 'max_group_by', 'max_limit', 'max_string_length', 'timeout_ms', 'thin_n', 'decimals']) {
    if (typeof raw.limits[k] !== 'number') fail(`limits.${k}`)
  }
  if (!Array.isArray(raw.views) || raw.views.length === 0) fail('views')
  const seen = new Set<string>()
  for (const v of raw.views as unknown[]) {
    if (!isObj(v) || typeof v.name !== 'string' || !/^qv_[a-z_]+$/.test(v.name)) fail('view name')
    if (seen.has(v.name)) fail(`duplicate view ${v.name}`)
    seen.add(v.name)
    if (typeof v.count_name !== 'string' || !/^[a-z_]+$/.test(v.count_name)) fail(`${v.name}.count_name`)
    if (!isStrArr(v.required_filters)) fail(`${v.name}.required_filters`)
    if (!isObj(v.group_by_requires)) fail(`${v.name}.group_by_requires`)
    if (!Array.isArray(v.default_filters)) fail(`${v.name}.default_filters`)
    if (!Array.isArray(v.columns) || v.columns.length === 0) fail(`${v.name}.columns`)
    const cols = new Set<string>()
    for (const c of v.columns as unknown[]) {
      if (!isObj(c) || typeof c.name !== 'string' || !/^[a-z][a-z0-9_]*$/.test(c.name)) fail(`${v.name} column name`)
      if (c.role !== 'dimension' && c.role !== 'measure') fail(`${v.name}.${c.name}.role`)
      if (!['string', 'integer', 'number', 'boolean'].includes(c.type as string)) fail(`${v.name}.${c.name}.type`)
      if (!isStrArr(c.ops) || !c.ops.every((o) => (OP_NAMES as readonly string[]).includes(o))) fail(`${v.name}.${c.name}.ops`)
      if (!isStrArr(c.aggregates) || !c.aggregates.every((a) => (AGG_NAMES as readonly string[]).includes(a) && a !== 'count'))
        fail(`${v.name}.${c.name}.aggregates`)
      if (typeof c.group_by !== 'boolean') fail(`${v.name}.${c.name}.group_by`)
      cols.add(c.name)
    }
    for (const r of [...v.required_filters, ...Object.keys(v.group_by_requires)]) {
      if (!cols.has(r)) fail(`${v.name}: ${r} is not a column`)
    }
    if (v.partition_key !== null && v.partition_key !== 'season') fail(`${v.name}.partition_key`)
    if (v.sub_partition_key !== null && v.sub_partition_key !== 'race_id') fail(`${v.name}.sub_partition_key`)
  }
  return raw as unknown as Catalogue
}

let cached: Promise<Catalogue> | null = null

/** Fetch and check /data/assistant/catalogue.json once per session. */
export function loadCatalogue(): Promise<Catalogue> {
  if (!cached) {
    cached = fetch(`${DATA_CDN_BASE}/data/assistant/catalogue.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load query catalogue: ${res.status}`)
        return res.json() as Promise<unknown>
      })
      .then(parseCatalogue)
      .catch((err: unknown) => {
        cached = null
        throw err
      })
  }
  return cached
}

export function getView(cat: Catalogue, name: string): CatalogueView | undefined {
  return cat.views.find((v) => v.name === name)
}
