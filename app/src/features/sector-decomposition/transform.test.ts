import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { SectorRow } from './queries'

const rows: SectorRow[] = [
  { driver_id: 'HAM', sector: 1, avg_pace_delta_s: -0.1, avg_skill_residual_s: -0.05, avg_total_explained_s: -0.05, avg_consistency_index: 0.03, lap_count: 50 },
  { driver_id: 'VER', sector: 1, avg_pace_delta_s: 0.05, avg_skill_residual_s: 0.02, avg_total_explained_s: 0.03, avg_consistency_index: 0.02, lap_count: 52 },
  { driver_id: 'VER', sector: 2, avg_pace_delta_s: -0.12, avg_skill_residual_s: -0.06, avg_total_explained_s: -0.06, avg_consistency_index: 0.02, lap_count: 52 },
  { driver_id: 'HAM', sector: 2, avg_pace_delta_s: 0.08, avg_skill_residual_s: 0.04, avg_total_explained_s: 0.04, avg_consistency_index: 0.05, lap_count: 50 },
]

describe('transform', () => {
  it('splits rows by sector', () => {
    const result = transform(rows)
    expect(result.s1).toHaveLength(2)
    expect(result.s2).toHaveLength(2)
    expect(result.s3).toHaveLength(0)
  })

  it('assigns ranks starting at 1 per sector', () => {
    const result = transform(rows)
    expect(result.s1[0].rank).toBe(1)
    expect(result.s1[1].rank).toBe(2)
    expect(result.s2[0].rank).toBe(1)
  })

  it('preserves sort order from query (fastest pace delta first)', () => {
    const result = transform(rows)
    expect(result.s1[0].driver_id).toBe('HAM')
    expect(result.s2[0].driver_id).toBe('VER')
  })
})
