import type { CompoundProfileRow, StintSummaryRow } from './queries'
import type { KMPoint, StintObservation } from '../../ui/charts/SurvivalCurve'

export interface SurvivalTransformResult {
  /** Kaplan-Meier step function points */
  kmCurve: KMPoint[]
  /** Per-stint scatter overlay points */
  stintObservations: StintObservation[]
  /** Model fitted cliff onset lap (from dim_compounds_season) */
  cliffOnsetLap: number | null
  /** Model fitted cliff severity (s) */
  cliffSeverity: number | null
  /** Fit provenance */
  fitDate: string | null
  dataWindow: string | null
  /** Number of stints used to fit the model (parsed from notes) */
  nStints: number | null
  /** Compound name */
  compound: string
  /** Number of actual stints in the selected race */
  actualStintCount: number
}

/**
 * Kaplan-Meier estimator for cliff-onset survival.
 *
 * Each stint contributes:
 *-An event at `stint_length` if `cliffed = true`
 *-A censored observation at `stint_length` if `cliffed = false`
 *
 * S(t) = product over all t_i <= t of (1-d_i / n_i)
 * where d_i = events at t_i, n_i = subjects at risk just before t_i.
 */
export function computeKM(stints: StintSummaryRow[]): KMPoint[] {
  if (!stints.length) return []

  // Collect all unique event times (cliffed stints only)
  const eventTimes = Array.from(
    new Set(stints.filter(s => s.cliffed).map(s => s.stint_length))
  ).sort((a, b) => a-b)

  if (!eventTimes.length) {
    // No events observed-survival stays at 1.0 across all observed lengths
    const maxLap = Math.max(...stints.map(s => s.stint_length))
    return [
      { lap: 0, survival: 1 },
      { lap: maxLap, survival: 1 },
    ]
  }

  // Starting point
  const points: KMPoint[] = [{ lap: 0, survival: 1 }]
  let survival = 1.0

  for (const t of eventTimes) {
    // n_at_risk: stints that have not yet ended (cliffed or censored) before time t
    const atRisk = stints.filter(s => s.stint_length >= t).length
    const events = stints.filter(s => s.cliffed && s.stint_length === t).length

    if (atRisk === 0) break
    survival = survival * (1-events / atRisk)
    points.push({ lap: t, survival: Math.max(0, survival) })
  }

  return points
}

/**
 * Parses "fitted from N stints via ..." out of the notes field.
 * Returns null if the notes field doesn't match or is absent.
 */
export function parseNStints(notes: string | null): number | null {
  if (!notes) return null
  const match = notes.match(/fitted from (\d+) stints/i)
  return match ? parseInt(match[1], 10) : null
}

export function transform(
  profile: CompoundProfileRow | null,
  stints: StintSummaryRow[],
  compound: string,
): SurvivalTransformResult {
  const kmCurve = computeKM(stints)

  const stintObservations: StintObservation[] = stints.map(s => ({
    endLap: s.stint_length,
    cliffed: s.cliffed,
    degradation_s: s.degradation_s,
    driver_id: s.driver_id ?? undefined,
  }))

  return {
    kmCurve,
    stintObservations,
    cliffOnsetLap: profile?.compound_cliff_onset_laps ?? null,
    cliffSeverity: profile?.compound_cliff_severity ?? null,
    fitDate: profile?.fit_date ?? null,
    dataWindow: profile?.data_window ?? null,
    nStints: profile ? parseNStints(profile.notes) : null,
    compound,
    actualStintCount: stints.length,
  }
}

export function toCsvRows(result: SurvivalTransformResult): Record<string, unknown>[] {
  return result.stintObservations.map(s => ({
    driver_id: s.driver_id ?? '',
    end_lap: s.endLap,
    cliffed: s.cliffed,
    degradation_s: s.degradation_s.toFixed(4),
    compound: result.compound,
  }))
}
