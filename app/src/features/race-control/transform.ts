import type { CautionLapRow, HazardRow, PooledRateRow } from './queries'

export type CautionKind = 'safety_car' | 'vsc' | 'red_flag'

export interface CautionSegment {
  kind: CautionKind
  startLap: number
  endLap: number
  /** Duration in laps, which is the unit a race is actually read in. */
  laps: number
}

export interface TimelineResult {
  raceLaps: number
  segments: CautionSegment[]
  /** Laps under any caution, over laps in the race. */
  cautionLaps: number
  greenLaps: number
}

export const KIND_LABEL: Record<CautionKind, string> = {
  safety_car: 'Safety Car',
  vsc: 'Virtual Safety Car',
  red_flag: 'Red Flag',
}

export const KIND_COLOR: Record<CautionKind, string> = {
  safety_car: 'rgb(251,191,36)',
  vsc: 'rgb(250,204,21)',
  red_flag: 'rgb(239,68,68)',
}

/**
 * Collapse the per-lap status into contiguous runs.
 *
 * Two deployments with no green lap between them merge into one run: measured
 * against stg_track_status this reconstructs 112 runs against 119 logged
 * onsets, agreeing exactly on 76 of the 85 races that have safety-car laps.
 * The page states that rather than implying a one-to-one event count.
 */
export function transform(rows: CautionLapRow[]): TimelineResult {
  const raceLaps = rows.length ? Math.max(...rows.map(r => r.race_laps)) : 0
  const segments: CautionSegment[] = []
  let open: CautionSegment | null = null

  for (const row of rows) {
    const kind = row.caution_status === 'green' ? null : (row.caution_status as CautionKind)
    if (open && (kind !== open.kind || row.lap_number !== open.endLap + 1)) {
      segments.push(open)
      open = null
    }
    if (kind === null) continue
    if (open) {
      open.endLap = row.lap_number
      open.laps += 1
    } else {
      open = { kind, startLap: row.lap_number, endLap: row.lap_number, laps: 1 }
    }
  }
  if (open) segments.push(open)

  const cautionLaps = rows.filter(r => r.caution_status !== 'green').length
  return { raceLaps, segments, cautionLaps, greenLaps: rows.length - cautionLaps }
}

/** Wilson score interval. Never a bare proportion on this page. */
export function wilson(successes: number, n: number, z = 1.96): [number, number] {
  if (n === 0) return [0, 0]
  const p = successes / n
  const d = 1 + (z * z) / n
  const centre = (p + (z * z) / (2 * n)) / d
  const half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / d
  return [Math.max(0, centre - half), Math.min(1, centre + half)]
}

export interface PooledSummary {
  races: number
  anyCaution: { rate: number; lo: number; hi: number; n: number }
  safetyCar: { rate: number; lo: number; hi: number; n: number }
  vsc: { rate: number; lo: number; hi: number; n: number }
  redFlag: { rate: number; lo: number; hi: number; n: number }
  /** Share of all race laps run under any caution. */
  cautionLapShare: number
  perSeason: Array<{ season: number; races: number; withCaution: number; rate: number }>
}

function rate(x: number, n: number) {
  const [lo, hi] = wilson(x, n)
  return { rate: n ? x / n : 0, lo, hi, n: x }
}

export function summarisePooled(rows: PooledRateRow[]): PooledSummary | null {
  const total = rows.find(r => r.race_year === null)
  if (!total) return null
  return {
    races: total.races,
    anyCaution: rate(total.races_with_caution, total.races),
    safetyCar: rate(total.races_with_sc, total.races),
    vsc: rate(total.races_with_vsc, total.races),
    redFlag: rate(total.races_with_red, total.races),
    cautionLapShare: total.total_laps ? total.caution_laps / total.total_laps : 0,
    perSeason: rows
      .filter(r => r.race_year !== null)
      .map(r => ({
        season: r.race_year as number,
        races: r.races,
        withCaution: r.races_with_caution,
        rate: r.races ? r.races_with_caution / r.races : 0,
      })),
  }
}

/**
 * The empirical-Bayes pseudo-count from int_sc_hazard_history
 * (`var('sc_hazard_prior_laps', 600)`). Shown, not hidden: the weight a row
 * puts on its own circuit is L / (L + 600), which over the 128 rows with a
 * prior season averages 0.178.
 */
export const EB_PRIOR_LAPS = 600

export interface HazardContext {
  /** null when there is no row at all for this venue+season. */
  row: HazardRow | null
  /** True when every rate is NULL, i.e. nothing prior exists to estimate from. */
  unmeasurable: boolean
  /** Share of the shown value that is this circuit's own data, in [0, 1]. */
  ownDataWeight: number
}

export function hazardContext(rows: HazardRow[]): HazardContext {
  const row = rows[0] ?? null
  if (!row) return { row: null, unmeasurable: true, ownDataWeight: 0 }
  const unmeasurable = row.any_hazard_per_lap_shrunk == null
  const laps = row.prior_racing_laps ?? 0
  return { row, unmeasurable, ownDataWeight: laps / (laps + EB_PRIOR_LAPS) }
}

export function toCsvRows(raceId: string, result: TimelineResult): Record<string, unknown>[] {
  return result.segments.map(s => ({
    race_id: raceId,
    event: KIND_LABEL[s.kind],
    start_lap: s.startLap,
    end_lap: s.endLap,
    laps: s.laps,
    race_laps: result.raceLaps,
  }))
}
