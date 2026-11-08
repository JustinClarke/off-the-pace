// AX-06: query_data request, result and error shapes (design 2.5, AI-09 result shape kept).
import type { AggName, OpName, OrderName } from '../catalogue/catalogue'

export type Scalar = string | number | boolean
export type FilterValue = Scalar | Scalar[]

export interface QueryFilter {
  col: string
  op: OpName
  val: FilterValue
}

/** The only thing the model sends. */
export interface QueryRequest {
  view: string
  filters?: QueryFilter[]
  group_by?: string[]
  aggregate: { fn: AggName; col: string }
  order?: OrderName
  limit?: number
}

export interface QueryRow {
  [col: string]: Scalar | null | undefined
  value: number | null
  n: number
  thin?: true
}

export interface QueryResult {
  status: 'ok'
  view: string
  /** Filters actually applied, including the view's default filters. */
  filters_applied: QueryFilter[]
  grain: string
  aggregate: { fn: AggName; col: string }
  group_by: string[]
  rows: QueryRow[]
  /** Total groups matched (exact, from COUNT(*) OVER ()). */
  row_count: number
  rows_shown: number
  rows_dropped: number
  label: 'computed_not_card'
  notes: string[]
  result_id: string
}

export interface QueryNoData {
  status: 'no_data'
  view: string
  reason: string
}

export type QueryErrorCode =
  | 'unknown_view'
  | 'unknown_column'
  | 'bad_op'
  | 'bad_value'
  | 'missing_required_filter'
  | 'too_many_filters'
  | 'too_many_seasons'
  | 'bad_group_by'
  | 'bad_aggregate'
  | 'bad_limit'
  | 'bad_order'
  | 'timeout'

export interface QueryError {
  status: 'error'
  code: QueryErrorCode
  field: string
  message: string
  /** What the request may use instead (views, columns, ops, aggregates). */
  allowed?: Record<string, unknown>
}

export type QueryOutcome = QueryResult | QueryNoData | QueryError
