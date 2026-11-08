/**
 * Tooltip text for optimal_pit_lap_confidence (AP-03). The column is 0.0 both
 * where no cost curve exists (no optimum) and where a curve exists but no lap
 * is more than 1 s worse than the best (a flat curve), so 0.0 alone is not
 * "0% confident".
 */
export function pitConfidenceLabel(
  confidence: number | null,
  optimalPitLapInStint: number | null,
): string {
  if (confidence == null || (confidence === 0 && optimalPitLapInStint == null)) {
    return 'no cost curve'
  }
  const pct = `${Math.round(confidence * 100)}%`
  return confidence === 0 ? `${pct} (flat curve)` : `${pct} of laps >1 s worse`
}
