import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { ChampionshipRow } from './queries'

const rows: ChampionshipRow[] = [
  { ego_driver_id: 'VER', ghost_points: 400, actual_points: 300, races_counted: 20, avg_confidence: 0.75 },
  { ego_driver_id: 'HAM', ghost_points: 350, actual_points: 280, races_counted: 20, avg_confidence: 0.70 },
  { ego_driver_id: 'ALO', ghost_points: 200, actual_points: 250, races_counted: 20, avg_confidence: 0.65 },
]

describe('transform', () => {
  it('assigns ghost rank in input order (already desc by ghost_points)', () => {
    const { ghostStandings } = transform(rows)
    expect(ghostStandings[0].ghostRank).toBe(1)
    expect(ghostStandings[0].driver).toBe('VER')
  })

  it('assigns actual rank by actual_points desc', () => {
    const { actualStandings } = transform(rows)
    expect(actualStandings[0].driver).toBe('VER')
    expect(actualStandings[2].driver).toBe('ALO')
  })

  it('computes delta as ghost minus actual', () => {
    const { ghostStandings } = transform(rows)
    expect(ghostStandings[0].delta).toBe(100)
  })

  it('sets coverageWarning when races < 15', () => {
    const sparse = rows.map(r => ({ ...r, races_counted: 10 }))
    expect(transform(sparse).coverageWarning).toBe(true)
    expect(transform(rows).coverageWarning).toBe(false)
  })
})
