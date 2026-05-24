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

  // Filter options (always over unfiltered rows)
  const compoundFilter_ = [...new Set(rows.map(r => r.compound))].filter(Boolean).sort()
  const circuitFilter_ = [...new Set(rows.map(r => r.circuit_key))].sort()

  return { scatter, confusion, rug, coverageStat, compoundFilter: compoundFilter_, circuitFilter: circuitFilter_ }
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
