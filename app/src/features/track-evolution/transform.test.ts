import { describe, it, expect } from 'vitest'
import { transform, toCsvRows } from './transform'
import type { TrackEvolutionRow } from './queries'

const ROWS: TrackEvolutionRow[] = [
  { lap_number: 1, rubber_component_s: 0.05, ambient_component_s: -0.01, track_state_index_s: 95.5, rainfall_flag: false },
  { lap_number: 2, rubber_component_s: 0.04, ambient_component_s: -0.01, track_state_index_s: 95.3, rainfall_flag: false },
  { lap_number: 3, rubber_component_s: 0.03, ambient_component_s: -0.02, track_state_index_s: 95.1, rainfall_flag: true },
]

describe('transform', () => {
  it('returns empty for empty input', () => {
    const r = transform([])
    expect(r.rubberPoints).toHaveLength(0)
    expect(r.hasRain).toBe(false)
  })

  it('detects rainfall', () => {
    const r = transform(ROWS)
    expect(r.hasRain).toBe(true)
  })

  it('maps lap_number to x', () => {
    const r = transform(ROWS)
    expect(r.rubberPoints[0].x).toBe(1)
    expect(r.rubberPoints[2].x).toBe(3)
  })

  it('computes peakRubber', () => {
    const r = transform(ROWS)
    expect(r.peakRubber).toBeCloseTo(0.05)
  })
})

const NULL_ROWS: TrackEvolutionRow[] = [
  { lap_number: 1, rubber_component_s: 0.05, ambient_component_s: -0.01, track_state_index_s: 95.5, rainfall_flag: false },
  { lap_number: 2, rubber_component_s: null, ambient_component_s: 0, track_state_index_s: 95.3, rainfall_flag: null },
  { lap_number: 3, rubber_component_s: -0.03, ambient_component_s: null, track_state_index_s: null, rainfall_flag: null },
]

describe('transform with NULL measurements', () => {
  it('does not throw and keeps NULL as null, never 0', () => {
    const r = transform(NULL_ROWS)
    expect(r.rubberPoints[1].y).toBeNull()
    expect(r.rubberPoints[1].lo).toBeNull()
    expect(r.rubberPoints[1].hi).toBeNull()
    expect(r.rubberPoints[1].y2).toBe(0)
    expect(r.rubberPoints[2].y2).toBeNull()
    expect(r.ambientPoints[2].y).toBeNull()
  })

  it('peakRubber ignores NULL rows', () => {
    expect(transform(NULL_ROWS).peakRubber).toBeCloseTo(0.05)
  })

  it('peakRubber is null, not 0, when no lap has a rubber component', () => {
    const rows = NULL_ROWS.map(r => ({ ...r, rubber_component_s: null }))
    expect(transform(rows).peakRubber).toBeNull()
  })

  it('NULL rainfall_flag is not rain', () => {
    const rows = NULL_ROWS.map(r => ({ ...r, rainfall_flag: null }))
    expect(transform(rows).hasRain).toBe(false)
  })
})

describe('toCsvRows with NULL measurements', () => {
  it('does not throw; NULL becomes an empty cell, measured values keep 4 dp', () => {
    const csv = toCsvRows(NULL_ROWS)
    expect(csv[0].rubber_component_s).toBe('0.0500')
    expect(csv[1].rubber_component_s).toBe('')
    expect(csv[1].ambient_component_s).toBe('0.0000')
    expect(csv[1].rainfall_flag).toBe('')
    expect(csv[2].ambient_component_s).toBe('')
    expect(csv[2].track_state_index_s).toBe('')
  })
})
