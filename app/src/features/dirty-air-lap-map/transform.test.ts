import { describe, it, expect } from 'vitest'
import { transform, toCsvRows } from './transform'
import { buildLapAirStateSql } from './queries'
import type { LapAirStateRow } from './queries'

const mkRow = (
  driver_id: string,
  lap_number: number,
  air_state_dominant: string,
  dirty_air_thermal_load_surface = 0,
  gap_ahead_min_s: number | null = null,
): LapAirStateRow => ({ driver_id, lap_number, air_state_dominant, dirty_air_thermal_load_surface, gap_ahead_min_s })

describe('transform', () => {
  it('returns empty for no rows', () => {
    const r = transform([])
    expect(r.xLabels).toEqual([])
    expect(r.yLabels).toEqual([])
    expect(r.cells).toEqual([])
  })

  it('produces correct x/y dimensions', () => {
    const rows = [
      mkRow('VER', 1, 'free_air'),
      mkRow('VER', 2, 'dirty_air'),
      mkRow('HAM', 1, 'dirty_air'),
      mkRow('HAM', 2, 'free_air'),
    ]
    const r = transform(rows)
    expect(r.xLabels).toEqual(['1', '2'])
    expect(r.yLabels).toHaveLength(2)
    expect(r.cells).toHaveLength(4)
  })

  it('sorts lap numbers ascending', () => {
    const rows = [
      mkRow('VER', 5, 'free_air'),
      mkRow('VER', 2, 'dirty_air'),
      mkRow('VER', 10, 'tow_zone'),
    ]
    const r = transform(rows)
    expect(r.xLabels).toEqual(['2', '5', '10'])
  })

  it('sorts drivers most dirty-air first', () => {
    const rows = [
      mkRow('HAM', 1, 'free_air'),
      mkRow('HAM', 2, 'free_air'),
      mkRow('VER', 1, 'dirty_air'),
      mkRow('VER', 2, 'dirty_air'),
    ]
    const r = transform(rows)
    expect(r.yLabels[0]).toBe('VER')
    expect(r.yLabels[1]).toBe('HAM')
  })

  it('cell indices are within bounds', () => {
    const rows = [
      mkRow('VER', 1, 'dirty_air', 0.5),
      mkRow('HAM', 3, 'free_air', 0.0),
    ]
    const r = transform(rows)
    for (const cell of r.cells) {
      expect(cell.x).toBeGreaterThanOrEqual(0)
      expect(cell.x).toBeLessThan(r.xLabels.length)
      expect(cell.y).toBeGreaterThanOrEqual(0)
      expect(cell.y).toBeLessThan(r.yLabels.length)
    }
  })

  it('assigns color overrides per air state', () => {
    const rows = [
      mkRow('VER', 1, 'dirty_air'),
      mkRow('HAM', 1, 'tow_zone'),
      mkRow('LEC', 1, 'drs_train'),
      mkRow('SAI', 1, 'free_air'),
    ]
    const r = transform(rows)
    const byDriver = (id: string) => r.cells.find(c => r.yLabels[c.y] === id)
    expect(byDriver('VER')?.color).toContain('194')    // orange-red
    expect(byDriver('HAM')?.color).toContain('128')    // green
    expect(byDriver('LEC')?.color).toContain('83')     // amber
    expect(byDriver('SAI')?.color).toContain('0.04')   // near-transparent
  })
})

// DD7 / DA-01: the gap label is the crossing-time gap (int_lap_proximity via
// fct_cliff_prediction_features), never int_lap_air_state.min_gap_s, which is
// distance-to-driver-ahead / point speed and biased above 1 s.
describe('gap label source (DD7)', () => {
  it('reads the crossing-time gap, not the distance / speed gap', () => {
    const sql = buildLapAirStateSql(2024)
    expect(sql).toContain('f.gap_ahead_min_s')
    expect(sql).toMatch(/LEFT JOIN fct_cliff_prediction_features_2024 AS f\s+ON f\.lap_id = a\.lap_id/)
    expect(sql).not.toMatch(/\bmin_gap_s\b/)
    const [csv] = toCsvRows([mkRow('VER', 3, 'dirty_air', 0, 0.8765)])
    expect(csv.gap_ahead_min_s).toBe('0.88')
    expect(csv).not.toHaveProperty('min_gap_s')
  })
})
