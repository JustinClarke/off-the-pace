// AX-11: session-scoped chart store. Rows live here and go only to the renderer, never to the model.
import { getResult, sessionResults } from '../queryBuilder/store'

export type ChartType = 'line' | 'bar' | 'scatter'
export type Cell = string | number | boolean | null | undefined

export interface ChartSeries {
  label: string
  /** [x, y] pairs, already extracted from a result in this session. */
  points: { x: string | number; y: number }[]
}

export interface ChartSpec {
  type: ChartType
  title: string
  x: { col: string; label: string }
  y: { col: string; label: string }
  series: { result_id: string; label: string; x_col: string; y_col: string }[]
}

export interface StoredChart {
  chart_id: string
  spec: ChartSpec
  series: ChartSeries[]
  /** Points per series. */
  n: number[]
  label: 'computed_not_card'
  /** Optional extra caption for the card (e.g. "driver A vs B, race 2024_8"). */
  note?: string
}

const charts = new Map<string, StoredChart>()
const MAX_CHARTS = 50
let counter = 0

export function nextChartId(): string {
  counter += 1
  return `chart_${counter}`
}

export function saveChart(c: StoredChart): void {
  charts.set(c.chart_id, c)
  while (charts.size > MAX_CHARTS) charts.delete(charts.keys().next().value as string)
}

export function getChart(id: string): StoredChart | undefined {
  return charts.get(id)
}

/** Rows of a query_data result from this session, or undefined (made-up or foreign id). */
export function getResultRows(resultId: string): Record<string, Cell>[] | undefined {
  if (typeof resultId !== 'string') return undefined
  return getResult(resultId)?.rows as Record<string, Cell>[] | undefined
}

export function knownResultIds(): string[] {
  return sessionResults().map((r) => r.result_id)
}

export function clearCharts(): void {
  charts.clear()
}
