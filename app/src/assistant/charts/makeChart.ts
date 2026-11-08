// AX-11 make_chart: a fixed-shape chart description from rows of query_data results of THIS session.
// The model never writes code, SQL or a URL; it gets back {chart_id, n, series_count} only.
import { getResultRows, nextChartId, saveChart, type Cell, type ChartSeries, type ChartSpec } from './chartStore'

export const MAX_SERIES = 6
export const MAX_POINTS = 500
export const MAX_TEXT = 80

export type MakeChartResult =
  | { status: 'ok'; chart_id: string; n: number; series_count: number }
  | { status: 'error'; reason: string }

const err = (reason: string): MakeChartResult => ({ status: 'error', reason })
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

/** Plain text of 1..80 chars, no control characters. Rendered as text by React, never as HTML. */
function text(v: unknown): string | null {
  if (typeof v !== 'string') return null
  const t = v.trim()
  // eslint-disable-next-line no-control-regex
  if (t.length === 0 || t.length > MAX_TEXT || /[\u0000-\u001f\u007f]/.test(t)) return null
  return t
}

function colName(v: unknown): string | null {
  return typeof v === 'string' && /^[a-z][a-z0-9_]{0,63}$/.test(v) ? v : null
}

export function makeChart(spec: unknown): MakeChartResult {
  if (!isObj(spec)) return err('spec must be an object')
  const type = spec.type
  if (type !== 'line' && type !== 'bar' && type !== 'scatter') return err('type must be line, bar or scatter')
  const title = text(spec.title)
  if (!title) return err(`title must be plain text of 1 to ${MAX_TEXT} characters`)
  const x = spec.x, y = spec.y
  if (!isObj(x) || !isObj(y)) return err('x and y must be {col, label}')
  const xl = text(x.label), yl = text(y.label), xc = colName(x.col), yc = colName(y.col)
  if (!xl || !yl) return err(`axis labels must be plain text of 1 to ${MAX_TEXT} characters`)
  if (!xc || !yc) return err('x.col and y.col must be column names')
  if (!Array.isArray(spec.series) || spec.series.length === 0) return err('series must be a non-empty array')
  if (spec.series.length > MAX_SERIES) return err(`at most ${MAX_SERIES} series (got ${spec.series.length})`)

  const outSeries: ChartSeries[] = []
  const specSeries: ChartSpec['series'] = []
  for (let i = 0; i < spec.series.length; i++) {
    const s: unknown = spec.series[i]
    if (!isObj(s)) return err(`series[${i}] must be {result_id, label, x_col, y_col}`)
    const label = text(s.label)
    const sx = colName(s.x_col), sy = colName(s.y_col)
    if (!label) return err(`series[${i}].label must be plain text of 1 to ${MAX_TEXT} characters`)
    if (!sx || !sy) return err(`series[${i}] x_col and y_col must be column names`)
    const rid = typeof s.result_id === 'string' ? s.result_id : ''
    const rows = getResultRows(rid)
    if (!rows) return err(`series[${i}].result_id is not a result from this session; call query_data first`)
    if (rows.length > MAX_POINTS) return err(`series[${i}] has ${rows.length} points; at most ${MAX_POINTS}`)
    const first = rows[0]
    if (!first || !(sx in first)) return err(`series[${i}].x_col "${sx}" is not a column of that result`)
    if (!(sy in first)) return err(`series[${i}].y_col "${sy}" is not a column of that result`)
    const points: ChartSeries['points'] = []
    for (const r of rows) {
      const xv: Cell = r[sx], yv: Cell = r[sy]
      if (typeof yv !== 'number' || !Number.isFinite(yv)) continue
      if (typeof xv !== 'number' && typeof xv !== 'string') continue
      if (type === 'scatter' && typeof xv !== 'number') continue
      points.push({ x: xv, y: yv })
    }
    if (points.length === 0) return err(`series[${i}] has no plottable points`)
    outSeries.push({ label, points })
    specSeries.push({ result_id: rid, label, x_col: sx, y_col: sy })
  }
  const chart_id = nextChartId()
  saveChart({
    chart_id,
    spec: { type, title, x: { col: xc, label: xl }, y: { col: yc, label: yl }, series: specSeries },
    series: outSeries,
    n: outSeries.map((s) => s.points.length),
    label: 'computed_not_card',
  })
  return { status: 'ok', chart_id, n: outSeries.reduce((a, s) => a + s.points.length, 0), series_count: outSeries.length }
}
