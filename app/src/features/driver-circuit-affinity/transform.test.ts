import { describe, it, expect } from 'vitest'
import { transform, toCsvRows } from './transform'
import type { CircuitAffinityRow } from './queries'

const mkRow = (
  driver_id: string,
  circuit_id: string,
  circuit_name: string,
  affinity_vs_driver_mean_s: number,
  global_driver_mean_s = 0,
  n_obs = 3,
): CircuitAffinityRow => ({
  driver_id,
  circuit_id,
  circuit_name,
  affinity_vs_driver_mean_s,
  global_driver_mean_s,
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

  it('sorts drivers by overall gap to teammates, biggest margin first', () => {
    const rows = [
      mkRow('HAM', 'bahrain', 'Bahrain', 0.1, 0.2),
      mkRow('HAM', 'monza', 'Monza', -0.1, 0.2),
      mkRow('VER', 'bahrain', 'Bahrain', 0.05, -0.4),
      mkRow('VER', 'monza', 'Monza', -0.05, -0.4),
    ]
    const r = transform(rows)
    // VER beats his teammates by 0.4s on average, HAM trails his by 0.2s
    expect(r.yLabels).toEqual(['VER', 'HAM'])
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

// T34 (F44, WI-14b): the heatmap draws a DEVIATION from the driver's own mean on a
// zero-centred diverging scale (negative = green = better against his teammate here
// than his own average). It used to draw the level shrunk_affinity_s, a gap to the
// teammate: every one of 667 cells was negative, so the page was entirely green.
// The fixture is the int_driver_circuit_affinity unit test's driver: he beats his
// teammate at every circuit (levels -0.421875 and -0.328125 around a mean of
// -0.375), which is exactly the case the level-drawing page got wrong.
describe('T34: cells are deviations from the driver\'s own mean (F44)', () => {
  const dominant = [
    mkRow('AAA', 'x', 'Circuit X', -0.421875 - -0.375, -0.375),
    mkRow('AAA', 'y', 'Circuit Y', -0.328125 - -0.375, -0.375),
  ]

  it('a driver who beats his teammate everywhere does not paint an all-green row', () => {
    const r = transform(dominant)
    const values = r.cells.map(c => c.value as number).sort((a, b) => a - b)
    expect(values).toEqual([-0.046875, 0.046875])
    expect(values.some(v => v < 0)).toBe(true)
    expect(values.some(v => v > 0)).toBe(true)
  })

  it('never draws the driver\'s overall level', () => {
    const r = transform(dominant)
    for (const cell of r.cells) expect(cell.value).not.toBe(-0.375)
  })

  it('about half of a realistic grid is green, not all of it', () => {
    // Deviations from each driver's own mean sum to ~0 per row by construction.
    const rows = [
      mkRow('VER', 'a', 'A', -0.2, -0.5), mkRow('VER', 'b', 'B', 0.1, -0.5), mkRow('VER', 'c', 'C', 0.1, -0.5),
      mkRow('PER', 'a', 'A', 0.15, 0.5), mkRow('PER', 'b', 'B', -0.05, 0.5), mkRow('PER', 'c', 'C', -0.1, 0.5),
    ]
    const r = transform(rows)
    const green = r.cells.filter(c => (c.value as number) < 0).length
    expect(green / r.cells.length).toBeGreaterThan(0.2)
    expect(green / r.cells.length).toBeLessThan(0.8)
  })

  it('CSV exports the drawn deviation and the driver\'s overall gap under distinct names', () => {
    const [row] = toCsvRows([dominant[0]])
    expect(row.affinity_vs_driver_mean_s).toBe('-0.047')
    expect(row.driver_mean_gap_to_teammate_s).toBe('-0.375')
    expect(row).not.toHaveProperty('shrunk_affinity_s')
  })
})
