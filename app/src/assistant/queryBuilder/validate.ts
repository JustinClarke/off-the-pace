// AX-06: validate a model-sent request against the catalogue. Everything downstream (compile, run)
// takes a ValidatedRequest, which only this module can make: it holds catalogue objects for every
// identifier, and request data only as bound values.
import {
  AGG_NAMES,
  ORDER_NAMES,
  type AggName,
  type Catalogue,
  type CatalogueColumn,
  type CatalogueView,
  type OpName,
  type OrderName,
} from '../catalogue/catalogue'
import type { QueryError, QueryErrorCode, QueryFilter, Scalar } from './types'

declare const brand: unique symbol

export interface ValidatedFilter {
  column: CatalogueColumn
  op: OpName
  /** Bound values only (1 for scalar ops, n for in, 2 for between). */
  values: Scalar[]
}

export interface ValidatedRequest {
  readonly [brand]: true
  view: CatalogueView
  filters: ValidatedFilter[]
  group_by: CatalogueColumn[]
  aggregate: { fn: AggName; column: CatalogueColumn | null; col: string }
  order: OrderName
  limit: number
  /** Seasons to register, taken from catalogue.seasons (never from the request). */
  seasons: number[]
  /** The single race of a race-sub-partitioned view. */
  race_id: string | null
  /** Canonical request (defaults applied) for result_id and filters_applied. */
  canonical: {
    view: string
    filters: QueryFilter[]
    group_by: string[]
    aggregate: { fn: AggName; col: string }
    order: OrderName
    limit: number
  }
}

const validated = new WeakSet<object>()

/** Runtime half of the brand: true only for objects validate() returned. */
export function isValidated(v: unknown): v is ValidatedRequest {
  return typeof v === 'object' && v !== null && validated.has(v)
}

export const DEFAULT_LIMIT = 10
export const DEFAULT_ORDER: OrderName = 'value_desc'
const REQUEST_KEYS = ['view', 'filters', 'group_by', 'aggregate', 'order', 'limit']
const RACE_ID = /^\d{4}_\d{1,2}$/

function err(code: QueryErrorCode, field: string, message: string, allowed?: Record<string, unknown>): QueryError {
  return allowed ? { status: 'error', code, field, message, allowed } : { status: 'error', code, field, message }
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) return false
  const proto = Object.getPrototypeOf(v)
  return proto === Object.prototype || proto === null
}

/** Own keys must be a subset of `allowed`; returns the first offending key. */
function extraKey(obj: Record<string, unknown>, allowed: string[]): string | null {
  for (const k of Reflect.ownKeys(obj)) {
    if (typeof k !== 'string' || !allowed.includes(k)) return String(k)
  }
  return null
}

function own(obj: Record<string, unknown>, key: string): unknown {
  return Object.prototype.hasOwnProperty.call(obj, key) ? obj[key] : undefined
}

function viewAllowed(view: CatalogueView): Record<string, unknown> {
  const dims = view.columns.filter((c) => c.role === 'dimension')
  return {
    filter_columns: Object.fromEntries(dims.map((c) => [c.name, c.ops])),
    group_by: view.columns.filter((c) => c.group_by).map((c) => c.name),
    aggregates: {
      ...Object.fromEntries(view.columns.filter((c) => c.role === 'measure').map((c) => [c.name, c.aggregates])),
      [view.count_name]: ['count'],
    },
    required_filters: view.required_filters,
  }
}

function checkScalar(col: CatalogueColumn, v: unknown, maxLen: number): Scalar | string {
  switch (col.type) {
    case 'string':
      if (typeof v !== 'string') return 'expected a string'
      if (v.length === 0 || v.length > maxLen) return `string must be 1-${maxLen} characters`
      return v
    case 'integer':
      if (typeof v !== 'number' || !Number.isFinite(v) || !Number.isInteger(v)) return 'expected an integer'
      return v
    case 'number':
      if (typeof v !== 'number' || !Number.isFinite(v)) return 'expected a finite number'
      return v
    case 'boolean':
      if (typeof v !== 'boolean') return 'expected true or false'
      return v
  }
}

/** Returns a ValidatedRequest, or a QueryError naming the field and what is allowed. Never throws. */
export function validate(req: unknown, cat: Catalogue): ValidatedRequest | QueryError {
  try {
    return validateInner(req, cat)
  } catch (e) {
    return err('bad_value', 'request', `request could not be read: ${e instanceof Error ? e.message.slice(0, 80) : 'error'}`)
  }
}

function validateInner(req: unknown, cat: Catalogue): ValidatedRequest | QueryError {
  const L = cat.limits
  const viewNames = cat.views.map((v) => v.name)
  if (!isPlainObject(req)) return err('bad_value', 'request', 'request must be a JSON object')
  const extra = extraKey(req, REQUEST_KEYS)
  if (extra !== null) return err('bad_value', extra.slice(0, 64), `unknown request field`, { fields: REQUEST_KEYS })

  const viewName = own(req, 'view')
  const view = typeof viewName === 'string' ? cat.views.find((v) => v.name === viewName) : undefined
  if (!view) return err('unknown_view', 'view', 'unknown view', { views: viewNames })
  const allowed = viewAllowed(view)
  const colByName = (name: unknown): CatalogueColumn | undefined =>
    typeof name === 'string' ? view.columns.find((c) => c.name === name) : undefined

  // ── filters ──
  const rawFilters = own(req, 'filters') ?? []
  if (!Array.isArray(rawFilters)) return err('bad_value', 'filters', 'filters must be an array', allowed)
  if (rawFilters.length > L.max_filters) return err('too_many_filters', 'filters', `at most ${L.max_filters} filters`)
  const filters: ValidatedFilter[] = []
  const canonicalFilters: QueryFilter[] = []
  const seen = new Set<string>()
  for (let i = 0; i < rawFilters.length; i++) {
    const f: unknown = rawFilters[i]
    const field = `filters[${i}]`
    if (!isPlainObject(f)) return err('bad_value', field, 'a filter is {col, op, val}')
    const fx = extraKey(f, ['col', 'op', 'val'])
    if (fx !== null) return err('bad_value', field, 'a filter is {col, op, val}')
    const column = colByName(own(f, 'col'))
    if (!column || column.role !== 'dimension') return err('unknown_column', `${field}.col`, 'not a filter column of this view', allowed)
    if (seen.has(column.name)) return err('bad_value', `${field}.col`, 'one filter per column')
    seen.add(column.name)
    const opRaw = own(f, 'op')
    const op = column.ops.find((o) => o === opRaw)
    if (!op) return err('bad_op', `${field}.op`, `operator not allowed on ${column.name}`, { ops: column.ops })
    if (column.name === 'season' && !['eq', 'in', 'between'].includes(op))
      return err('bad_op', `${field}.op`, 'season takes eq, in or between', { ops: ['eq', 'in', 'between'] })
    const arity = cat.ops[op]?.arity
    const val = own(f, 'val')
    let values: Scalar[]
    if (arity === 'scalar') {
      const s = checkScalar(column, val, L.max_string_length)
      if (typeof s === 'string' && column.type !== 'string') return err('bad_value', `${field}.val`, s)
      if (column.type === 'string' && s !== val) return err('bad_value', `${field}.val`, String(s))
      values = [s]
    } else if (arity === 'list') {
      if (!Array.isArray(val) || val.length === 0) return err('bad_value', `${field}.val`, 'in takes a non-empty array')
      if (val.length > L.max_in_values) return err('bad_value', `${field}.val`, `in takes at most ${L.max_in_values} values`)
      values = []
      for (const x of val) {
        const s = checkScalar(column, x, L.max_string_length)
        if (s !== x) return err('bad_value', `${field}.val`, typeof s === 'string' ? s : 'bad value')
        values.push(s)
      }
      values = [...new Set(values)]
    } else if (arity === 'pair') {
      if (!Array.isArray(val) || val.length !== 2) return err('bad_value', `${field}.val`, 'between takes [low, high]')
      const [lo, hi] = val
      const a = checkScalar(column, lo, L.max_string_length)
      const b = checkScalar(column, hi, L.max_string_length)
      if (a !== lo || b !== hi || typeof lo !== 'number' || typeof hi !== 'number' || lo > hi)
        return err('bad_value', `${field}.val`, 'between takes two numbers, low <= high')
      values = [lo, hi]
    } else {
      return err('bad_op', `${field}.op`, 'unknown operator', { ops: column.ops })
    }
    if (column.name === 'race_id' && view.sub_partition_key === 'race_id' && !RACE_ID.test(String(values[0])))
      return err('bad_value', `${field}.val`, 'race_id looks like 2024_8')
    filters.push({ column, op, values })
    canonicalFilters.push({ col: column.name, op, val: arity === 'scalar' ? values[0] : values })
  }

  // ── seasons ──
  const seasonFilter = filters.find((f) => f.column.name === 'season')
  let seasons: number[] = []
  if (seasonFilter) {
    const nums = seasonFilter.values as number[]
    const named =
      seasonFilter.op === 'between' ? cat.seasons.filter((s) => s >= nums[0] && s <= nums[1]) : nums
    // Take the season integers from the catalogue list, never the request.
    seasons = cat.seasons.filter((s) => named.includes(s))
    const unknown = seasonFilter.op === 'between' ? [] : nums.filter((s) => !cat.seasons.includes(s))
    if (unknown.length > 0) return err('bad_value', 'season', 'season not in the data', { seasons: cat.seasons })
    // AX-13 ruling 6: honour the catalogue. A set max_seasons is the cap; null on an unpartitioned view
    // (one file loaded whole whatever the seasons) means no per-request season cap; null on a
    // partitioned view keeps 2.
    const max = view.max_seasons ?? (view.partition_key ? 2 : Number.POSITIVE_INFINITY)
    if (seasonFilter.op === 'between' && nums[1] - nums[0] + 1 > max)
      return err('too_many_seasons', 'season', `at most ${max} season(s) per request`, { seasons: cat.seasons })
    if (seasons.length > max) return err('too_many_seasons', 'season', `at most ${max} season(s) per request`, { seasons: cat.seasons })
  }
  for (const r of view.required_filters) {
    if (!filters.some((f) => f.column.name === r))
      return err('missing_required_filter', 'filters', `${view.name} needs a filter on ${r}`, allowed)
  }
  let race_id: string | null = null
  if (view.sub_partition_key === 'race_id') {
    const rf = filters.find((f) => f.column.name === 'race_id')
    if (!rf || rf.op !== 'eq') return err('missing_required_filter', 'filters', 'race_id must be one eq filter', allowed)
    race_id = String(rf.values[0])
  }

  // ── group_by ──
  const rawGroup = own(req, 'group_by') ?? []
  if (!Array.isArray(rawGroup)) return err('bad_group_by', 'group_by', 'group_by must be an array', allowed)
  if (rawGroup.length > L.max_group_by) return err('bad_group_by', 'group_by', `at most ${L.max_group_by} columns`, allowed)
  const group_by: CatalogueColumn[] = []
  for (const g of rawGroup) {
    const column = colByName(g)
    if (!column || !column.group_by) return err('bad_group_by', 'group_by', 'not a group_by column of this view', allowed)
    if (group_by.includes(column)) return err('bad_group_by', 'group_by', 'duplicate group_by column')
    for (const need of view.group_by_requires[column.name] ?? []) {
      if (!filters.some((f) => f.column.name === need))
        return err('missing_required_filter', 'filters', `grouping by ${column.name} needs a filter on ${need}`, allowed)
    }
    group_by.push(column)
  }

  // ── aggregate ──
  const agg = own(req, 'aggregate')
  if (!isPlainObject(agg) || extraKey(agg, ['fn', 'col']) !== null)
    return err('bad_aggregate', 'aggregate', 'aggregate is {fn, col}', allowed)
  const fnRaw = own(agg, 'fn')
  const fn = AGG_NAMES.find((a) => a === fnRaw)
  if (!fn) return err('bad_aggregate', 'aggregate.fn', 'unknown aggregate', { fns: AGG_NAMES })
  const colRaw = own(agg, 'col')
  let aggColumn: CatalogueColumn | null = null
  let aggCol: string
  if (fn === 'count') {
    if (colRaw !== view.count_name) return err('bad_aggregate', 'aggregate.col', `count uses col "${view.count_name}"`, allowed)
    aggCol = view.count_name
  } else {
    const column = colByName(colRaw)
    if (!column || column.role !== 'measure') return err('bad_aggregate', 'aggregate.col', 'not a measure of this view', allowed)
    if (!column.aggregates.some((a) => a === fn))
      return err('bad_aggregate', 'aggregate.fn', `${fn} is not allowed on ${column.name}`, { fns: column.aggregates })
    aggColumn = column
    aggCol = column.name
  }

  // ── order, limit ──
  const orderRaw = own(req, 'order') ?? DEFAULT_ORDER
  const order = ORDER_NAMES.find((o) => o === orderRaw)
  if (!order) return err('bad_order', 'order', 'unknown order', { orders: ORDER_NAMES })
  const limitRaw = own(req, 'limit') ?? DEFAULT_LIMIT
  if (typeof limitRaw !== 'number' || !Number.isInteger(limitRaw) || limitRaw < 1 || limitRaw > L.max_limit)
    return err('bad_limit', 'limit', `limit is an integer from 1 to ${L.max_limit}`)
  const limit = limitRaw

  // ── default filters (applied unless the request filters the same column) ──
  for (const d of view.default_filters) {
    if (filters.some((f) => f.column.name === d.col)) continue
    const column = view.columns.find((c) => c.name === d.col)
    if (!column) continue
    filters.push({ column, op: d.op, values: [d.val] })
    canonicalFilters.push({ col: d.col, op: d.op, val: d.val })
  }

  const out = {
    view,
    filters,
    group_by,
    aggregate: { fn, column: aggColumn, col: aggCol },
    order,
    limit,
    seasons,
    race_id,
    canonical: {
      view: view.name,
      filters: canonicalFilters,
      group_by: group_by.map((c) => c.name),
      aggregate: { fn, col: aggCol },
      order,
      limit,
    },
  } as unknown as ValidatedRequest
  validated.add(out)
  return out
}
