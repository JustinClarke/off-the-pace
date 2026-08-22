import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { CircuitAffinityRow } from './queries'

const mkRow = (
  driver_id: string,
  circuit_id: string,
  circuit_name: string,
  shrunk_affinity_s: number,
  n_obs = 3,
): CircuitAffinityRow => ({
  driver_id,
  circuit_id,
  circuit_name,
  shrunk_affinity_s,
  n_obs,
  seasons_observed_n: n_obs,
  affinity_confidence: n_obs / (n_obs + 5),
})

describe('transform', () => {
  it('returns empty for no rows', () => {
    const r = transform([])
    expect(r.xLabels).toEqual([])
    expect(r.yLabels).toEqual([])
    expect(r.cells).toEqual([])
  })

  it('produces correct grid dimensions', () => {
    const rows = [
      mkRow('VER', 'bahrain', 'Bahrain', -0.5),
      mkRow('VER', 'monza', 'Monza', 0.3),
      mkRow('HAM', 'bahrain', 'Bahrain', 0.1),
      mkRow('HAM', 'monza', 'Monza', -0.2),
    ]
    const r = transform(rows)
    expect(r.xLabels).toEqual(['Bahrain', 'Monza'])
    expect(r.yLabels).toHaveLength(2)
    expect(r.cells).toHaveLength(4)
  })

  it('sorts circuits alphabetically', () => {
    const rows = [
      mkRow('VER', 'silverstone', 'Silverstone', 0.1),
      mkRow('VER', 'bahrain', 'Bahrain', -0.2),
      mkRow('VER', 'monza', 'Monza', 0.0),
    ]
    const r = transform(rows)
    expect(r.xLabels).toEqual(['Bahrain', 'Monza', 'Silverstone'])
  })

  it('sorts drivers fastest median first', () => {
    const rows = [
      mkRow('HAM', 'bahrain', 'Bahrain', 0.8),
      mkRow('HAM', 'monza', 'Monza', 0.6),
      mkRow('VER', 'bahrain', 'Bahrain', -0.5),
      mkRow('VER', 'monza', 'Monza', -0.3),
    ]
    const r = transform(rows)
    // VER median = -0.4, HAM median = 0.7 → VER first (more negative = faster)
    expect(r.yLabels[0]).toBe('VER')
    expect(r.yLabels[1]).toBe('HAM')
  })

  it('cell x/y indices are consistent with xLabels/yLabels', () => {
    const rows = [
      mkRow('VER', 'bahrain', 'Bahrain', -0.5),
      mkRow('HAM', 'monza', 'Monza', 0.2),
    ]
    const r = transform(rows)
    for (const cell of r.cells) {
      expect(cell.x).toBeGreaterThanOrEqual(0)
      expect(cell.x).toBeLessThan(r.xLabels.length)
      expect(cell.y).toBeGreaterThanOrEqual(0)
      expect(cell.y).toBeLessThan(r.yLabels.length)
    }
  })

  it('reports correct min/max values', () => {
    const rows = [
      mkRow('VER', 'bahrain', 'Bahrain', -1.2),
      mkRow('HAM', 'monza', 'Monza', 0.8),
    ]
    const r = transform(rows)
    expect(r.minValue).toBe(-1.2)
    expect(r.maxValue).toBe(0.8)
  })
})
