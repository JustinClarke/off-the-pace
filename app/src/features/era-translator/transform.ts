import type { EraTranslatorRow } from './queries'

/**
 * Colour for a season rating (seconds, negative = faster than his teammate(s)).
 * The rating is a gap to the teammate (F40, WI-14b), typically within ±0.4s, so the
 * bands sit on that scale: green for faster than the teammate, red for slower.
 * The old bands (< -3s, < -1.5s, > 0.5s) were tuned to the pre-fix level bias
 * (every rating near -1.8s) and would leave every honest rating uncoloured.
 */
export function ratingClass(v: unknown): string {
  const s = v as number
  if (s < -0.3) return 'text-green-300'
  if (s < -0.1) return 'text-green-400'
  if (s > 0.1)  return 'text-red-400'
  return 'text-[rgb(var(--color-text))]'
}

export interface EraRankRow {
  rank: number
  driver_id: string
  season: number
  era_adjusted_rating: number
  ci_low: number
  ci_high: number
  ci_width: number
  rating_confidence: number
  n_races: number
  bridge_driver_anchor_flag: boolean
}

export interface TransformResult {
  rows: EraRankRow[]
}

export function transform(data: EraTranslatorRow[]): TransformResult {
  const rows: EraRankRow[] = data.map((r, i) => ({
    rank: i + 1,
    driver_id: r.driver_id,
    season: r.season,
    era_adjusted_rating: r.era_adjusted_rating,
    ci_low: r.era_adjusted_rating_ci_low_s,
    ci_high: r.era_adjusted_rating_ci_high_s,
    ci_width: r.era_adjusted_rating_ci_high_s - r.era_adjusted_rating_ci_low_s,
    rating_confidence: r.rating_confidence,
    n_races: r.n_races,
    bridge_driver_anchor_flag: r.bridge_driver_anchor_flag,
  }))
  return { rows }
}

export function toCsvRows(result: TransformResult): Record<string, unknown>[] {
  return result.rows.map(r => ({
    rank: r.rank,
    driver_id: r.driver_id,
    season: r.season,
    era_adjusted_rating_s: r.era_adjusted_rating.toFixed(4),
    ci_low_s: r.ci_low.toFixed(4),
    ci_high_s: r.ci_high.toFixed(4),
    rating_confidence: r.rating_confidence.toFixed(3),
    n_races: r.n_races,
    bridge_anchor: r.bridge_driver_anchor_flag,
  }))
}
