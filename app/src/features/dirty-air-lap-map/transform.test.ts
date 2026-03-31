import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { LapAirStateRow } from './queries'

const mkRow = (
  driver_id: string,
  lap_number: number,
  air_state_dominant: string,
  dirty_air_thermal_load_surface = 0,
  min_gap_s: number | null = null,
): LapAirStateRow => ({ driver_id, lap_number, air_state_dominant, dirty_air_thermal_load_surface, min_gap_s })

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
