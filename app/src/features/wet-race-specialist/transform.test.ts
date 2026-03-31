import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { WetRaceRow } from './queries'

const ROWS: WetRaceRow[] = [
  { driver_id: 'HAM', wet_races: 5, dry_races: 50, wet_skill_s: -1.5, dry_skill_s: -0.5, wet_advantage_s: 1.0 },
  { driver_id: 'VER', wet_races: 3, dry_races: 60, wet_skill_s: -0.5, dry_skill_s: -0.5, wet_advantage_s: 0.0 },
  { driver_id: 'ALO', wet_races: 4, dry_races: 45, wet_skill_s:  0.3, dry_skill_s: -0.2, wet_advantage_s: -0.5 },
]

describe('transform', () => {
  it('returns empty result for empty input', () => {
    expect(transform([]).rows).toHaveLength(0)
  })

  it('classifies tiers correctly', () => {
    const { rows } = transform(ROWS)
    const map = Object.fromEntries(rows.map(r => [r.driver_id, r.tier]))
    expect(map['HAM']).toBe('specialist')
    expect(map['VER']).toBe('slight-edge')
    expect(map['ALO']).toBe('dry-preferred')
  })

  it('preserves counts', () => {
    const { rows } = transform(ROWS)
    expect(rows.find(r => r.driver_id === 'HAM')?.wet_races).toBe(5)
  })
})
