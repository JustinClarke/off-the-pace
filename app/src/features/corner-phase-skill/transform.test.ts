import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { CornerPhaseRow } from './queries'

const rows: CornerPhaseRow[] = [
  {
    driver_id: 'HAM',
    braking_skill_s: -0.02,
    mid_corner_skill_s: -0.01,
    exit_skill_s: -0.03,
    braking_skill_z: -0.5,
    mid_corner_skill_z: -0.3,
    exit_skill_z: -0.7,
    corner_skill_index: -1.5,
    mapped_corners: 500,
  },
  {
    driver_id: 'VER',
    braking_skill_s: 0.01,
    mid_corner_skill_s: -0.02,
    exit_skill_s: 0.00,
    braking_skill_z: 0.2,
    mid_corner_skill_z: -0.5,
    exit_skill_z: 0.0,
    corner_skill_index: -0.3,
    mapped_corners: 480,
  },
]

describe('transform', () => {
  it('assigns ranks starting at 1', () => {
    const result = transform(rows)
    expect(result[0].rank).toBe(1)
    expect(result[1].rank).toBe(2)
  })

  it('preserves driver order (lowest corner_skill_index first)', () => {
    const result = transform(rows)
    expect(result[0].driver_id).toBe('HAM')
    expect(result[0].corner_skill_index).toBeCloseTo(-1.5)
  })

  it('passes all fields through', () => {
    const result = transform(rows)
    expect(result[0].mapped_corners).toBe(500)
    expect(result[0].braking_skill_z).toBeCloseTo(-0.5)
    expect(result[0].exit_skill_s).toBeCloseTo(-0.03)
  })
})
