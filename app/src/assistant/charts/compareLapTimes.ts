// AX-11 compare_lap_times(a, b, race_id): a fixed qv_laps request (green racing laps, outliers excluded),
// two series of at most 80 points. The model gets {chart_id, n_a, n_b, laps_missing} only.
// The 25-row query_data cap is lifted here by the internal rowCap argument, which no tool schema exposes.
import { runQuery, type RunDeps } from '../queryBuilder/run'
import type { QueryResult } from '../queryBuilder/types'
import type { EntityRow } from '../listValues'
import { nextChartId, saveChart } from './chartStore'

export const MAX_LAPS_PER_SERIES = 80
export const COMPARE_ROW_CAP = 160

export type CompareResult =
  | { status: 'ok'; chart_id: string; n_a: number; n_b: number; laps_missing: number }
  | { status: 'no_data'; reason: string }
  | { status: 'error'; reason: string }

const CODE = /^[A-Z0-9]{2,4}$/
const RACE = /^\d{4}_\d{1,2}$/

export interface CompareDeps extends RunDeps {
  entities: EntityRow[]
}

export async function compareLapTimes(a: unknown, b: unknown, raceId: unknown, deps: CompareDeps): Promise<CompareResult> {
  const bad = (what: string): CompareResult => ({
    status: 'error',
    reason: `${what} must be an exact code; call list_values to resolve names to codes`,
  })
  if (typeof a !== 'string' || !CODE.test(a) || !deps.entities.some((e) => e.domain === 'driver' && e.code === a)) return bad('a')
  if (typeof b !== 'string' || !CODE.test(b) || !deps.entities.some((e) => e.domain === 'driver' && e.code === b)) return bad('b')
  if (a === b) return { status: 'error', reason: 'a and b must be two different drivers' }
  if (typeof raceId !== 'string' || !RACE.test(raceId) || !deps.entities.some((e) => e.domain === 'race' && e.code === raceId))
    return bad('race_id')
  const season = Number(raceId.split('_')[0])

  const out = await runQuery(
    {
      view: 'qv_laps',
      filters: [
        { col: 'season', op: 'eq', val: season },
        { col: 'race_id', op: 'eq', val: raceId },
        { col: 'driver_id', op: 'in', val: [a, b] },
      ],
      group_by: ['driver_id', 'lap_number'],
      aggregate: { fn: 'median', col: 'lap_time_s' },
      order: 'group_asc',
      limit: 25,
    },
    deps,
    { rowCap: COMPARE_ROW_CAP },
  )
  if (out.status === 'error') return { status: 'error', reason: `${out.code}: ${out.message}` }
  if (out.status === 'no_data') return { status: 'no_data', reason: out.reason }
  const res: QueryResult = out
  const pts = (d: string) =>
    res.rows
      .filter((r) => r.driver_id === d && typeof r.lap_number === 'number' && typeof r.value === 'number')
      .map((r) => ({ x: r.lap_number as number, y: r.value as number }))
      .slice(0, MAX_LAPS_PER_SERIES)
  const pa = pts(a), pb = pts(b)
  if (pa.length === 0 || pb.length === 0) {
    const who = pa.length === 0 ? a : b
    return { status: 'no_data', reason: `${who} has no green racing laps in ${raceId}` }
  }
  const la = new Set(pa.map((p) => p.x)), lb = new Set(pb.map((p) => p.x))
  let missing = 0
  for (const x of la) if (!lb.has(x)) missing++
  for (const x of lb) if (!la.has(x)) missing++

  const chart_id = nextChartId()
  saveChart({
    chart_id,
    spec: {
      type: 'line',
      title: `${a} vs ${b} lap times, ${raceId}`,
      x: { col: 'lap_number', label: 'Lap' },
      y: { col: 'value', label: 'Lap time (s)' },
      series: [a, b].map((d) => ({ result_id: res.result_id, label: d, x_col: 'lap_number', y_col: 'value' })),
    },
    series: [
      { label: a, points: pa },
      { label: b, points: pb },
    ],
    n: [pa.length, pb.length],
    label: 'computed_not_card',
    note: 'Observed green racing laps, major outliers excluded; not fuel- or tyre-corrected.',
  })
  return { status: 'ok', chart_id, n_a: pa.length, n_b: pb.length, laps_missing: missing }
}
