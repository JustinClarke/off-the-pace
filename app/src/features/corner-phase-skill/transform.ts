import type { CornerPhaseRow } from './queries'

export interface CornerPhaseResult {
  rank: number
  driver_id: string
  braking_skill_s: number
  mid_corner_skill_s: number
  exit_skill_s: number
  braking_skill_z: number
  mid_corner_skill_z: number
  exit_skill_z: number
  corner_skill_index: number
  mapped_corners: number
}

export function transform(rows: CornerPhaseRow[]): CornerPhaseResult[] {
  return rows.map((r, i) => ({ rank: i + 1, ...r }))
}

export function toCsvRows(results: CornerPhaseResult[]): Record<string, unknown>[] {
  return results.map(r => ({
    rank: r.rank,
    driver_id: r.driver_id,
    braking_skill_s: r.braking_skill_s.toFixed(4),
    mid_corner_skill_s: r.mid_corner_skill_s.toFixed(4),
    exit_skill_s: r.exit_skill_s.toFixed(4),
    braking_skill_z: r.braking_skill_z.toFixed(2),
    mid_corner_skill_z: r.mid_corner_skill_z.toFixed(2),
    exit_skill_z: r.exit_skill_z.toFixed(2),
    corner_skill_index: r.corner_skill_index.toFixed(2),
    mapped_corners: r.mapped_corners,
  }))
}
