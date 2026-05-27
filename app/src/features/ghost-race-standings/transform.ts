import type { EraAffinityRow } from './queries'

// Below this confidence the posterior is prior-dominated (≈1 race at prior_weight=5).
// Rows under it are shown amber so a thin sample never reads as a hard result.
export const CONFIDENCE_FLOOR = 0.3

export interface LeaderboardEntry {
  rank: number
  driverId: string
  /** car-removed pace at this circuit-era, shrunk. negative = faster than field. */
  affinityS: number
  /** unshrunk observed mean (negative = faster). */
  rawAffinityS: number
  ciLowS: number
  ciHighS: number
  seS: number
  /** n_obs / (n_obs + 5) ∈ [0,1]. */
  confidence: number
  /** number of races backing the estimate (n_obs). */
  races: number
  /** distinct seasons observed within the era. */
  seasons: number
  /** affinityS − leader's affinityS, in seconds (≥ 0; the leader's gap is 0). */
  gapToLeaderS: number
}

export interface LeaderboardResult {
  circuitId: string
  circuitName: string
  eraKey: string
  eraLabel: string
  entries: LeaderboardEntry[]
  /** total drivers before any min-races filtering (for provenance / empty state). */
  totalDrivers: number
}

/**
 * Build a ranked equal-car track-record leaderboard for one (circuit, era).
 * Rows are expected to already be a single (circuit, era) cohort; ranking and the
 * gap-to-leader are computed over exactly the rows passed in (so the caller can
 * pre-filter by a minimum race count and the leader is the fastest of the survivors).
 */
export function transform(rows: EraAffinityRow[]): LeaderboardResult | null {
  if (!rows.length) return null

  const sorted = [...rows].sort((a, b) => a.shrunk_affinity_s-b.shrunk_affinity_s)
  const leaderAffinity = sorted[0].shrunk_affinity_s
  const first = sorted[0]

  const entries: LeaderboardEntry[] = sorted.map((r, i) => ({
    rank: i + 1,
    driverId: r.driver_id,
    affinityS: r.shrunk_affinity_s,
    rawAffinityS: r.raw_affinity_s,
    ciLowS: r.shrunk_affinity_ci_low_s,
    ciHighS: r.shrunk_affinity_ci_high_s,
    seS: r.shrunk_affinity_se_s,
    confidence: r.affinity_confidence,
    races: r.n_obs,
    seasons: r.seasons_observed_n,
    gapToLeaderS: r.shrunk_affinity_s-leaderAffinity,
  }))

  return {
    circuitId: first.circuit_id,
    circuitName: first.circuit_name,
    eraKey: first.era_key,
    eraLabel: first.era_label,
    entries,
    totalDrivers: entries.length,
  }
}

export function toCsvRows(result: LeaderboardResult): Record<string, unknown>[] {
  return result.entries.map(e => ({
    rank: e.rank,
    driver_id: e.driverId,
    circuit: result.circuitName,
    era: result.eraLabel,
    affinity_s: e.affinityS.toFixed(3),
    raw_affinity_s: e.rawAffinityS.toFixed(3),
    ci_low_s: e.ciLowS.toFixed(3),
    ci_high_s: e.ciHighS.toFixed(3),
    se_s: e.seS.toFixed(3),
    gap_to_leader_s: e.gapToLeaderS.toFixed(3),
    races: e.races,
    seasons: e.seasons,
    confidence: e.confidence.toFixed(3),
  }))
}
