import type { WetRaceRow } from './queries'

export interface WetSpecialistRow {
  driver_id: string
  wet_races: number
  dry_races: number
  wet_skill_s: number
  dry_skill_s: number
  /** positive = better (faster) in wet vs dry; shrunk toward 0 by sample size */
  wet_advantage_s: number
  /** wet_races / (wet_races + k); closer to 1 = more reliable */
  sample_weight: number
  tier: 'specialist' | 'slight-edge' | 'dry-preferred'
}

export interface TransformResult {
  rows: WetSpecialistRow[]
  threshold: number
}

const SHRINK_K = 6

export function transform(data: WetRaceRow[]): TransformResult {
  if (!data.length) return { rows: [], threshold: 0.2 }

  const shrunk = data.map(r => r.wet_advantage_s * r.wet_races / (r.wet_races + SHRINK_K))
  const mean = shrunk.reduce((a, b) => a + b, 0) / shrunk.length
  const threshold = Math.max(
    Math.sqrt(shrunk.reduce((s, v) => s + (v - mean) ** 2, 0) / shrunk.length) * 0.5,
    0.2
  )

  const rows: WetSpecialistRow[] = data.map((r, i) => {
    const adv = shrunk[i]
    const weight = r.wet_races / (r.wet_races + SHRINK_K)
    return {
      driver_id: r.driver_id,
      wet_races: r.wet_races,
      dry_races: r.dry_races,
      wet_skill_s: r.wet_skill_s,
      dry_skill_s: r.dry_skill_s,
      wet_advantage_s: adv,
      sample_weight: weight,
      tier:
        adv >= threshold  ? 'specialist'
        : adv <= -threshold ? 'dry-preferred'
        : 'slight-edge',
    }
  })

  return { rows, threshold }
}

export function toCsvRows(result: TransformResult): Record<string, unknown>[] {
  return result.rows.map(r => ({
    driver_id: r.driver_id,
    wet_races: r.wet_races,
    dry_races: r.dry_races,
    wet_skill_s: r.wet_skill_s.toFixed(4),
    dry_skill_s: r.dry_skill_s.toFixed(4),
    wet_advantage_s: r.wet_advantage_s.toFixed(4),
    sample_weight: r.sample_weight.toFixed(3),
    tier: r.tier,
  }))
}
