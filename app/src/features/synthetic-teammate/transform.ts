import type { SyntheticTmRow } from './queries'

export interface SyntheticTmPoint {
  driver_id: string
  teammate_driver_id: string
  constructor_id: string
  n_races: number
  avg_skill_proxy_s: number
  avg_quality_weight: number
  verdict: 'ahead' | 'behind' | 'even'
}

export interface TransformResult {
  points: SyntheticTmPoint[]
}

export function transform(rows: SyntheticTmRow[]): TransformResult {
  const points: SyntheticTmPoint[] = rows.map(r => ({
    ...r,
    verdict:
      r.avg_skill_proxy_s < -0.1 ? 'ahead'
      : r.avg_skill_proxy_s > 0.1 ? 'behind'
      : 'even',
  }))
  return { points }
}

export function toCsvRows(result: TransformResult): Record<string, unknown>[] {
  return result.points.map(p => ({
    driver_id: p.driver_id,
    teammate_driver_id: p.teammate_driver_id,
    constructor_id: p.constructor_id,
    n_races: p.n_races,
    avg_skill_proxy_s: p.avg_skill_proxy_s.toFixed(4),
    avg_quality_weight: p.avg_quality_weight.toFixed(3),
    verdict: p.verdict,
  }))
}
