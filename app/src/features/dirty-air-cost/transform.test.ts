import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { DirtyAirCostRow } from './queries'

const mkRow = (driver_id: string, total: number, avg: number, taxed = 10, total_laps = 50): DirtyAirCostRow => ({
  driver_id,
  total_dirty_air_cost_s: total,
  avg_tax_s: avg,
  taxed_laps: taxed,
  total_laps,
})

describe('transform', () => {
  it('returns empty for no rows', () => {
    expect(transform([])).toEqual([])
  })

  it('assigns rank 1 to highest total cost', () => {
    const rows = [mkRow('LEC', 8.0, 0.16), mkRow('VER', 2.0, 0.04)]
    const result = transform(rows)
    expect(result[0].driver_id).toBe('LEC')
    expect(result[0].rank).toBe(1)
    expect(result[1].rank).toBe(2)
  })

  it('sorts by total cost descending regardless of input order', () => {
    const rows = [mkRow('ALO', 2.0, 0.05), mkRow('LEC', 8.0, 0.16), mkRow('HAM', 5.0, 0.10)]
    const result = transform(rows)
    expect(result.map(r => r.driver_id)).toEqual(['LEC', 'HAM', 'ALO'])
  })

  it('does not mutate input', () => {
    const rows = [mkRow('VER', 1.0, 0.02), mkRow('NOR', 3.0, 0.06)]
    const original = rows.map(r => ({ ...r }))
    transform(rows)
    expect(rows).toEqual(original)
  })
})
