import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { CircuitInteractionRow } from './queries'

const mkRow = (
  constructor_id: string,
  circuit_key: string,
  circuit_name: string,
  avg_interaction_s: number,
  n_races = 3,
): CircuitInteractionRow => ({ constructor_id, circuit_key, circuit_name, avg_interaction_s, n_races })

describe('transform', () => {
  it('returns empty for no rows', () => {
    const r = transform([])
    expect(r.cells).toEqual([])
    expect(r.xLabels).toEqual([])
    expect(r.yLabels).toEqual([])
  })

  it('produces correct grid dimensions', () => {
    const rows = [
      mkRow('ferrari', 'bahrain', 'Bahrain', 0.2),
      mkRow('ferrari', 'monza', 'Monza', -0.5),
      mkRow('mercedes', 'bahrain', 'Bahrain', -0.1),
      mkRow('mercedes', 'monza', 'Monza', 0.3),
    ]
    const r = transform(rows)
    expect(r.xLabels).toHaveLength(2)
    expect(r.yLabels).toHaveLength(2)
    expect(r.cells).toHaveLength(4)
  })

  it('sorts circuits alphabetically', () => {
    const rows = [
      mkRow('ferrari', 'silverstone', 'Silverstone', 0.1),
      mkRow('ferrari', 'bahrain', 'Bahrain', 0.2),
      mkRow('ferrari', 'monza', 'Monza', 0.3),
    ]
    const r = transform(rows)
    expect(r.xLabels).toEqual(['Bahrain', 'Monza', 'Silverstone'])
  })

  it('cell indices within bounds', () => {
    const rows = [
      mkRow('ferrari', 'bahrain', 'Bahrain', 0.3),
      mkRow('mercedes', 'monza', 'Monza', -0.2),
    ]
    const r = transform(rows)
    for (const cell of r.cells) {
      expect(cell.x).toBeGreaterThanOrEqual(0)
      expect(cell.x).toBeLessThan(r.xLabels.length)
      expect(cell.y).toBeGreaterThanOrEqual(0)
      expect(cell.y).toBeLessThan(r.yLabels.length)
    }
  })

  it('reports correct min/max', () => {
    const rows = [
      mkRow('ferrari', 'bahrain', 'Bahrain', -0.8),
      mkRow('mercedes', 'monza', 'Monza', 0.6),
    ]
    const r = transform(rows)
    expect(r.minValue).toBe(-0.8)
    expect(r.maxValue).toBe(0.6)
  })
})
