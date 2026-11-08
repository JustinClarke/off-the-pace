// AX-06: compile a ValidatedRequest to one SQL statement plus bound parameters. Every identifier
// in the SQL comes from a catalogue object (view, column, alias built from a catalogue season);
// every request value goes into `params`. The limit is a validated integer 1..25.
import { sha256Hex } from '../cards/sha256'
import type { Scalar } from './types'
import { isValidated, type ValidatedRequest } from './validate'

export interface PartitionAlias {
  /** DuckDB view name the builder registers (qv_laps_2024, qv_teammate_corners_2024_<hash>). */
  alias: string
  season: number | null
  race_id: string | null
}

export interface Compiled {
  sql: string
  params: Scalar[]
  seasons: number[]
  aliases: PartitionAlias[]
}

const IDENT = /^[a-z][a-z0-9_]*$/
function q(ident: string): string {
  // Catalogue identifiers only; parseCatalogue already enforces the pattern, this is a second guard.
  if (!IDENT.test(ident)) throw new Error(`bad identifier in catalogue: ${ident}`)
  return `"${ident}"`
}

const AGG_SQL = { avg: 'AVG', median: 'MEDIAN', min: 'MIN', max: 'MAX', sum: 'SUM' } as const

export function aliasesFor(v: ValidatedRequest): PartitionAlias[] {
  const view = v.view
  if (!view.partition_key) return [{ alias: view.name, season: null, race_id: null }]
  if (view.sub_partition_key === 'race_id') {
    // The alias carries a hash of the race id, never the request string itself.
    return v.seasons.map((s) => ({
      alias: `${view.name}_${s}_r${sha256Hex(String(v.race_id)).slice(0, 12)}`,
      season: s,
      race_id: v.race_id,
    }))
  }
  return v.seasons.map((s) => ({ alias: `${view.name}_${s}`, season: s, race_id: null }))
}

/** Hard ceiling for the internal row cap (a tool needing more rows must say so here, in code). */
export const MAX_INTERNAL_ROW_CAP = 200

export interface CompileOptions {
  /** INTERNAL ONLY (AX-11). Overrides the 25-row LIMIT for app-built requests such as compare_lap_times.
   * Never read from a model request: validate() rejects unknown keys and no tool schema exposes it. */
  rowCap?: number
}

export function compile(v: ValidatedRequest, opts: CompileOptions = {}): Compiled {
  if (!isValidated(v)) throw new Error('compile() takes only a request returned by validate()')
  const aliases = aliasesFor(v)
  const params: Scalar[] = []

  const source =
    aliases.length === 1
      ? q(aliases[0].alias)
      : `(${aliases.map((a) => `SELECT * FROM ${q(a.alias)}`).join(' UNION ALL ')}) AS src`

  const where = v.filters.map((f) => {
    const col = q(f.column.name)
    switch (f.op) {
      case 'in':
        params.push(...f.values)
        return `${col} IN (${f.values.map(() => '?').join(', ')})`
      case 'between':
        params.push(f.values[0], f.values[1])
        return `${col} BETWEEN ? AND ?`
      default: {
        const sqlOp = { eq: '=', ne: '<>', lt: '<', lte: '<=', gt: '>', gte: '>=' }[f.op]
        params.push(f.values[0])
        return `${col} ${sqlOp} ?`
      }
    }
  })

  const groups = v.group_by.map((c) => q(c.name))
  const { fn, column } = v.aggregate
  const value = fn === 'count' || !column ? 'COUNT(*)' : `${AGG_SQL[fn]}(${q(column.name)})`
  // n = rows behind the value: all rows for a count, non-null rows of the measure otherwise.
  const n = fn === 'count' || !column ? 'COUNT(*)' : `COUNT(${q(column.name)})`
  const select = [...groups, `${value} AS "value"`, `${n} AS "n"`, `COUNT(*) OVER () AS "total_groups"`]

  const orderBy =
    v.order === 'group_asc'
      ? [...groups.map((g) => `${g} ASC NULLS LAST`), '"value" DESC NULLS LAST']
      : [`"value" ${v.order === 'value_asc' ? 'ASC' : 'DESC'} NULLS LAST`, ...groups.map((g) => `${g} ASC NULLS LAST`)]

  const cap = opts.rowCap
  if (cap !== undefined && !(Number.isInteger(cap) && cap >= 1 && cap <= MAX_INTERNAL_ROW_CAP)) throw new Error('bad rowCap')
  const limit = cap ?? (Number.isInteger(v.limit) && v.limit >= 1 && v.limit <= 25 ? v.limit : 10)
  const sql = [
    `SELECT ${select.join(', ')}`,
    `FROM ${source}`,
    where.length ? `WHERE ${where.join(' AND ')}` : '',
    groups.length ? `GROUP BY ${groups.join(', ')}` : '',
    `ORDER BY ${orderBy.join(', ')}`,
    `LIMIT ${limit}`,
  ]
    .filter(Boolean)
    .join(' ')
  return { sql, params, seasons: [...v.seasons], aliases }
}
