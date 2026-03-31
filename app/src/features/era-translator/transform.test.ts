import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { EraTranslatorRow } from './queries'

const ROWS: EraTranslatorRow[] = [
  { driver_id: 'HAM', season: 2020, era_adjusted_rating: -4.3, era_adjusted_rating_ci_low_s: -5.0, era_adjusted_rating_ci_high_s: -3.6, rating_confidence: 0.9, n_races: 17, bridge_driver_anchor_flag: true },
  { driver_id: 'VER', season: 2020, era_adjusted_rating: -3.1, era_adjusted_rating_ci_low_s: -3.8, era_adjusted_rating_ci_high_s: -2.4, rating_confidence: 0.85, n_races: 17, bridge_driver_anchor_flag: true },
]

describe('transform', () => {
  it('assigns correct ranks', () => {
    const { rows } = transform(ROWS)
    expect(rows[0].rank).toBe(1)
    expect(rows[0].driver_id).toBe('HAM')
    expect(rows[1].rank).toBe(2)
  })

  it('computes ci_width', () => {
    const { rows } = transform(ROWS)
    expect(rows[0].ci_width).toBeCloseTo(1.4)
  })

  it('returns empty for empty input', () => {
    expect(transform([]).rows).toHaveLength(0)
  })
})
