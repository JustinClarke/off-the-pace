import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { QualiVsRaceRow } from './queries'

const ROWS: QualiVsRaceRow[] = [
  { driver_id: 'VER', quali_skill_s: -0.9, race_skill_s:  0.8, delta_s: -1.7, n_races: 20 },
  { driver_id: 'HAM', quali_skill_s: -0.3, race_skill_s: -0.3, delta_s:  0.0, n_races: 20 },
  { driver_id: 'COL', quali_skill_s:  1.1, race_skill_s:  0.4, delta_s:  0.7, n_races:  8 },
]

describe('transform', () => {
  it('returns empty result for empty input', () => {
    const r = transform([])
    expect(r.points).toHaveLength(0)
  })

  it('classifies specialists correctly', () => {
    const r = transform(ROWS)
    const map = Object.fromEntries(r.points.map(p => [p.driver_id, p.specialist]))
    expect(map['VER']).toBe('quali')
    expect(map['HAM']).toBe('balanced')
    expect(map['COL']).toBe('race')
  })

  it('preserves driver_id and n_races', () => {
    const r = transform(ROWS)
    const ver = r.points.find(p => p.driver_id === 'VER')!
    expect(ver.n_races).toBe(20)
    expect(ver.quali_skill_s).toBeCloseTo(-0.9)
  })
})
