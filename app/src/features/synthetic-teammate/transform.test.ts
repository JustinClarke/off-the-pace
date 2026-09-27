import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { SyntheticTmRow } from './queries'

const ROWS: SyntheticTmRow[] = [
  { driver_id: 'VER', teammate_driver_id: 'PER', constructor_id: 'Red Bull', n_races: 20, avg_skill_proxy_s:  0.8, avg_quality_weight: 0.85 },
  { driver_id: 'PER', teammate_driver_id: 'VER', constructor_id: 'Red Bull', n_races: 20, avg_skill_proxy_s: -0.2, avg_quality_weight: 0.85 },
  { driver_id: 'HAM', teammate_driver_id: 'RUS', constructor_id: 'Mercedes', n_races: 18, avg_skill_proxy_s:  0.0, avg_quality_weight: 0.80 },
]

describe('transform', () => {
  it('returns empty for empty input', () => {
    expect(transform([]).points).toHaveLength(0)
  })

  it('classifies verdict correctly', () => {
    const { points } = transform(ROWS)
    const map = Object.fromEntries(points.map(p => [p.driver_id, p.verdict]))
    expect(map['VER']).toBe('ahead')
    expect(map['PER']).toBe('behind')
    expect(map['HAM']).toBe('even')
  })

  it('sign convention: positive skill proxy = ahead (ego faster)', () => {
    // F50 fixture test: verify driver_skill_proxy_s sign convention.
    // SQL defines: positive = ego is faster than synthetic teammate.
    // The verdict logic must respect this convention.
    const { points } = transform([
      {
        driver_id: 'FASTER',
        teammate_driver_id: 'TM',
        constructor_id: 'Test',
        n_races: 5,
        avg_skill_proxy_s: 0.5,  // positive = ego faster
        avg_quality_weight: 0.8,
      },
      {
        driver_id: 'SLOWER',
        teammate_driver_id: 'TM',
        constructor_id: 'Test',
        n_races: 5,
        avg_skill_proxy_s: -0.5,  // negative = ego slower
        avg_quality_weight: 0.8,
      },
    ])
    const map = Object.fromEntries(points.map(p => [p.driver_id, p.verdict]))
    // Positive proxy (ego faster) must be 'ahead'
    expect(map['FASTER']).toBe('ahead')
    // Negative proxy (ego slower) must be 'behind'
    expect(map['SLOWER']).toBe('behind')
  })
})
