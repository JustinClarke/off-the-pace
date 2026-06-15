import { describe, it, expect } from 'vitest'
import { transform } from './transform'
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
