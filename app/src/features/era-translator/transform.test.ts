import { describe, it, expect } from 'vitest'
import { transform, ratingClass } from './transform'
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

// T34 (era pages, WI-14b): the rating is a gap to the teammate (F40), negative =
// faster, typically within ±0.4s. The colour must follow that sign on that scale.
// The pre-fix bands (< -3s green, > 0.5s red) were tuned to the old -1.8s level
// bias: on the honest scale they leave every season uncoloured, and a driver 0.2s
// slower than his teammate would not read as slower.
describe('T34: rating colour follows the sign of the gap to the teammate', () => {
  it('faster than the teammate is green, slower is red', () => {
    expect(ratingClass(-0.35)).toMatch(/green/)
    expect(ratingClass(-0.15)).toMatch(/green/)
    expect(ratingClass(0.2)).toMatch(/red/)
  })

  it('a near-zero gap is neutral, neither green nor red', () => {
    expect(ratingClass(0.0)).not.toMatch(/green|red/)
    expect(ratingClass(-0.05)).not.toMatch(/green|red/)
    expect(ratingClass(0.05)).not.toMatch(/green|red/)
  })

  it('no positive rating is ever green and no negative one red', () => {
    for (let v = -1; v <= 1; v += 0.05) {
      if (v > 0) expect(ratingClass(v)).not.toMatch(/green/)
      if (v < 0) expect(ratingClass(v)).not.toMatch(/red/)
    }
  })
})
