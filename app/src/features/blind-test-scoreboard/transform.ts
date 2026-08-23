import type { ScoreboardRow } from './queries'

export const COMPOUND_COLORS: Record<string, string> = {
  SOFT: '#ef4444',
  MEDIUM: '#eab308',
  HARD: '#f3f4f6',
  INTERMEDIATE: '#22c55e',
  WET: '#3b82f6',
}

export const CLIFF_CLASSES = ['0_to_2', '3_to_5', '6_plus', 'none_in_stint'] as const
export type CliffClass = (typeof CLIFF_CLASSES)[number]

export interface ScatterPoint {
  x: number   // actual degradation jump (s)
  y: number   // predicted degradation jump p50 (s)
  p10: number
  p90: number
  isInEnvelope: boolean
  compound: string
  circuitKey: string
  driverId: string
  lapInStint: number
  label: string
}

/** One cell of the cliff-class confusion matrix: predicted row x actual column. */
export interface ConfusionCell {
  predicted: CliffClass
  actual: CliffClass
  count: number
  /** Share of all laps with this predicted class (row-normalised). */
  rowShare: number
}

/** Interval coverage rug: one entry per lap, true if actual falls within [p10, p90]. */
export interface RugEntry {
  lapIndex: number
  inEnvelope: boolean
}

/**
 * Stint-life accuracy for one population of laps. Censored and uncensored laps get
 * one of these each and are never pooled: on a censored lap the observed life is a
 * lower bound (the race ended before the tyre did), so an "error" against it is not
 * the same quantity as an error against an observed retirement. Pooling them is how
 * ml_headroom_ii.md #3's spurious "+12.4%" was produced.
 */
export interface StintLifeStat {
  n: number
  /** Median |predicted median - actual|, in laps. Uncensored only: on a censored
   *  lap this would measure the distance to a bound, not to the truth. */
  medianAbsErrorLaps: number | null
  /** Uncensored: share of laps where actual fell inside [p10, p90].
   *  Censored: share where p90 >= actual, i.e. the band is consistent with the
   *  tyre having lasted AT LEAST as long as we observed. */
  bandConsistentShare: number
}

export interface StintLifeReport {
  uncensored: StintLifeStat
  censored: StintLifeStat
  censoredShare: number
}

export interface ScoreboardResult {
  scatter: ScatterPoint[]
  confusion: ConfusionCell[]
  rug: RugEntry[]
  coverageStat: {
    empirical: number   // fraction of rows where actual is within [p10, p90]
    nominal: number     // 0.80-from model card
    n: number
  }
  compoundFilter: string[]  // distinct compounds present
  circuitFilter: string[]   // distinct circuit keys present
  stintLife: StintLifeReport
}

export function transform(
  rows: ScoreboardRow[],
  compoundFilter: string | null = null,
  circuitFilter: string | null = null,
): ScoreboardResult {
  const filtered = rows.filter(r =>
    (compoundFilter === null || r.compound === compoundFilter) &&
    (circuitFilter === null || r.circuit_key === circuitFilter)
  )

  // Scatter: predicted p50 vs actual, colouring by envelope membership
  const scatter: ScatterPoint[] = filtered
    .filter(r => r.actual_degradation_jump_s !== null)
    .map((r) => ({
      x: r.actual_degradation_jump_s as number,
      y: r.predicted_degradation_jump_s,
      p10: r.predicted_degradation_jump_p10_s,
      p90: r.predicted_degradation_jump_p90_s,
      isInEnvelope: r.is_in_envelope,
      compound: r.compound,
      circuitKey: r.circuit_key,
      driverId: r.driver_id,
      lapInStint: r.lap_in_stint,
      label: `${r.driver_id} lap ${r.lap_in_stint} (${r.compound})`,
    }))

  // Confusion matrix for cliff class
  const counts: Record<string, number> = {}
  const rowTotals: Record<string, number> = {}
  for (const r of filtered) {
    if (!r.actual_cliff_class || !r.predicted_cliff_class) continue
    const key = `${r.predicted_cliff_class}__${r.actual_cliff_class}`
    counts[key] = (counts[key] ?? 0) + 1
    rowTotals[r.predicted_cliff_class] = (rowTotals[r.predicted_cliff_class] ?? 0) + 1
  }
  const confusion: ConfusionCell[] = []
  for (const predicted of CLIFF_CLASSES) {
    for (const actual of CLIFF_CLASSES) {
      const count = counts[`${predicted}__${actual}`] ?? 0
      const rowTotal = rowTotals[predicted] ?? 0
      confusion.push({ predicted, actual, count, rowShare: rowTotal > 0 ? count / rowTotal : 0 })
    }
  }

  // Coverage rug: was actual inside [p10, p90]?
  const rugRows = filtered.filter(r => r.actual_degradation_jump_s !== null)
  const rug: RugEntry[] = rugRows.map((r, i) => ({
    lapIndex: i,
    inEnvelope: r.is_in_envelope,
  }))
  const coveredCount = rug.filter(r => r.inEnvelope).length
  const coverageStat = {
    empirical: rug.length > 0 ? coveredCount / rug.length : 0,
    nominal: 0.80,
    n: rug.length,
  }

  // Stint life, split by censoring.
  const lifeRows = filtered.filter(r => r.actual_remaining_stint_life_laps !== null)
  const stintLife = buildStintLifeReport(lifeRows)

  // Filter options (always over unfiltered rows)
  const compoundFilter_ = [...new Set(rows.map(r => r.compound))].filter(Boolean).sort()
  const circuitFilter_ = [...new Set(rows.map(r => r.circuit_key))].sort()

  return {
    scatter, confusion, rug, coverageStat,
    compoundFilter: compoundFilter_, circuitFilter: circuitFilter_, stintLife,
  }
}

function median(xs: number[]): number | null {
  if (xs.length === 0) return null
  const a = [...xs].sort((x, y) => x - y)
  const m = a.length >> 1
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2
}

function buildStintLifeReport(rows: ScoreboardRow[]): StintLifeReport {
  const stat = (pop: ScoreboardRow[], censored: boolean): StintLifeStat => {
    if (pop.length === 0) return { n: 0, medianAbsErrorLaps: null, bandConsistentShare: 0 }
    const consistent = pop.filter(r => {
      const actual = r.actual_remaining_stint_life_laps as number
      return censored
        // Censored: the tyre lasted at least `actual`, so the band only has to reach it.
        ? r.predicted_remaining_stint_life_p90_laps >= actual
        // Uncensored: the life was observed, so the band should contain it.
        : actual >= r.predicted_remaining_stint_life_p10_laps
          && actual <= r.predicted_remaining_stint_life_p90_laps
    }).length
    return {
      n: pop.length,
      medianAbsErrorLaps: censored ? null : median(pop.map(r =>
        Math.abs(r.predicted_remaining_stint_life_laps - (r.actual_remaining_stint_life_laps as number)))),
      bandConsistentShare: consistent / pop.length,
    }
  }
  const censoredRows = rows.filter(r => r.is_censored_stint)
  const uncensoredRows = rows.filter(r => !r.is_censored_stint)
  return {
    uncensored: stat(uncensoredRows, false),
    censored: stat(censoredRows, true),
    censoredShare: rows.length > 0 ? censoredRows.length / rows.length : 0,
  }
}

export function toCsvRows(result: ScoreboardResult): Record<string, unknown>[] {
  return result.scatter.map(p => ({
    driver_id: p.driverId,
    circuit_key: p.circuitKey,
    compound: p.compound,
    lap_in_stint: p.lapInStint,
    actual_degradation_jump_s: p.x,
    predicted_degradation_jump_p50_s: p.y,
    predicted_degradation_jump_p10_s: p.p10,
    predicted_degradation_jump_p90_s: p.p90,
    is_in_envelope: p.isInEnvelope,
  }))
}
