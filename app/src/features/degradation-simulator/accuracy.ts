/**
 * Accuracy metrics for the Degradation Simulator headline curve.
 * "Perfect" = MAE ≤ 0.5s and monotone violations = 0 on the basket cells.
 * Both functions are importable by transform tests and CDP verification scripts.
 */

/** One ground-truth sample from the accuracy basket (one lap of one cell). */
export interface BasketSample {
  lap_in_stint: number
  obs_deg_from_fresh_p50_s: number
}

/** One lap of the projected tyre curve (from LaptimePoint). */
export interface TyrePoint {
  x: number    // lap_in_stint (1-based)
  tyre: number // cumulative degradation from fresh (s)
}

/**
 * Mean absolute error of the projected tyre term vs the basket ground-truth p50 values,
 * over the laps where the basket has a sample. Call once per basket cell.
 *
 * Returns Infinity when there are no overlapping laps.
 */
export function projectedDegMAE(curve: TyrePoint[], samples: BasketSample[]): number {
  const byLap = new Map(curve.map(p => [p.x, p.tyre]))
  let sumAE = 0
  let count = 0
  for (const s of samples) {
    const projected = byLap.get(s.lap_in_stint)
    if (projected !== undefined) {
      sumAE += Math.abs(projected - s.obs_deg_from_fresh_p50_s)
      count++
    }
  }
  return count === 0 ? Infinity : sumAE / count
}

/**
 * Count laps where the tyre series decreases (tyre[i+1] < tyre[i]).
 * Zero means strictly monotone non-decreasing old rubber only ever adds time.
 */
export function monotoneViolations(tyreSeries: number[]): number {
  let violations = 0
  for (let i = 1; i < tyreSeries.length; i++) {
    if (tyreSeries[i] < tyreSeries[i - 1]) violations++
  }
  return violations
}
