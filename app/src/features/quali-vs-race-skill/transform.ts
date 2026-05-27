import type { QualiVsRaceRow } from './queries'

export interface QualiRacePoint {
  driver_id: string
  quali_skill_s: number
  race_skill_s: number
  delta_s: number
  n_races: number
  /** negative = better in quali; positive = better in race */
  specialist: 'quali' | 'race' | 'balanced'
}

export interface TransformResult {
  points: QualiRacePoint[]
  /** threshold for calling a driver a specialist (±1 stddev of delta) */
  deltaThreshold: number
}

function stddev(values: number[]): number {
  const m = values.reduce((a, b) => a + b, 0) / values.length
  return Math.sqrt(values.reduce((s, v) => s + (v - m) ** 2, 0) / values.length)
}

export function transform(rows: QualiVsRaceRow[]): TransformResult {
  if (!rows.length) return { points: [], deltaThreshold: 0.3 }

  const deltas = rows.map(r => r.delta_s)
  const threshold = Math.max(stddev(deltas) * 0.5, 0.3)

  const points: QualiRacePoint[] = rows.map(r => ({
    driver_id: r.driver_id,
    quali_skill_s: r.quali_skill_s,
    race_skill_s: r.race_skill_s,
    delta_s: r.delta_s,
    n_races: r.n_races,
    specialist:
      r.delta_s < -threshold ? 'quali'
      : r.delta_s > threshold ? 'race'
      : 'balanced',
  }))

  return { points, deltaThreshold: threshold }
}

export function toCsvRows(result: TransformResult): Record<string, unknown>[] {
  return result.points.map(p => ({
    driver_id: p.driver_id,
    quali_skill_s: p.quali_skill_s.toFixed(4),
    race_skill_s: p.race_skill_s.toFixed(4),
    quali_vs_race_delta_s: p.delta_s.toFixed(4),
    n_races: p.n_races,
    specialist: p.specialist,
  }))
}
