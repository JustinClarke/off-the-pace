import type { SectorRow } from './queries'

export interface SectorDriverResult {
  rank: number
  driver_id: string
  avg_pace_delta_s: number
  avg_skill_residual_s: number
  avg_total_explained_s: number
  avg_consistency_index: number
  lap_count: number
}

export interface SectorDecompositionResult {
  s1: SectorDriverResult[]
  s2: SectorDriverResult[]
  s3: SectorDriverResult[]
}

export function transform(rows: SectorRow[]): SectorDecompositionResult {
  function toRanked(sectorRows: SectorRow[]): SectorDriverResult[] {
    return sectorRows.map((r, i) => ({ rank: i + 1, ...r }))
  }

  return {
    s1: toRanked(rows.filter(r => r.sector === 1)),
    s2: toRanked(rows.filter(r => r.sector === 2)),
    s3: toRanked(rows.filter(r => r.sector === 3)),
  }
}

export function toCsvRows(rows: SectorRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    driver_id: r.driver_id,
    sector: r.sector,
    avg_pace_delta_s: r.avg_pace_delta_s.toFixed(4),
    avg_skill_residual_s: r.avg_skill_residual_s.toFixed(4),
    avg_total_explained_s: r.avg_total_explained_s.toFixed(4),
    avg_consistency_index: r.avg_consistency_index.toFixed(4),
    lap_count: r.lap_count,
  }))
}
