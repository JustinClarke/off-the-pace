import { describe, it, expect } from 'vitest'
import { probit, lapsFromMargin, stintLifeBand } from './survival'
import type { SurvivalOutput } from './manifest'

const OUT: SurvivalOutput = {
  index: 0,
  meaning: 'aft_margin (log remaining_stint_life_laps + shift)',
  postprocess: 'exp(x + margin_offset) - label_shift, clip(>=0)',
  margin_offset: 0,
  label_shift: 1,
  aft_distribution: 'normal',
  aft_scale: 0.5,
  quantiles: { p10: 0.1, p50: 0.5, p90: 0.9 },
  censored_share_train: 0.4625,
  c_index_cv: 0.746,
}

describe('probit', () => {
  // Reference values from scipy.stats.norm.ppf, the implementation ml/src/survival.py
  // uses. These two have to agree or the p10/p90 band drifts between the parquet and
  // the browser while the median stays identical -- a divergence the median-only
  // parity check could never see.
  const REFERENCE: Array<[number, number]> = [
    [0.01, -2.326347874040841],
    [0.05, -1.644853626951473],
    [0.10, -1.281551565544600],
    [0.25, -0.674489750196082],
    [0.50, 0.0],
    [0.75, 0.674489750196082],
    [0.90, 1.281551565544600],
    [0.95, 1.644853626951472],
    [0.99, 2.326347874040841],
  ]

  it.each(REFERENCE)('matches scipy at q=%s', (q, expected) => {
    expect(probit(q)).toBeCloseTo(expected, 8)
  })

  it('is antisymmetric about 0.5', () => {
    for (const q of [0.02, 0.15, 0.3, 0.44]) {
      expect(probit(q) + probit(1 - q)).toBeCloseTo(0, 8)
    }
  })

  it('rejects values outside (0,1)', () => {
    for (const bad of [0, 1, -0.1, 1.5]) expect(() => probit(bad)).toThrow(RangeError)
  })
})

describe('lapsFromMargin', () => {
  it('inverts the label shift', () => {
    expect(lapsFromMargin(Math.log(9), OUT)).toBeCloseTo(8)
  })

  it('clips a negative decoded life at 0', () => {
    // exp(-5) - 1 is negative; remaining life cannot be.
    expect(lapsFromMargin(-5, OUT)).toBe(0)
  })

  it('applies margin_offset on the log scale', () => {
    const shifted = { ...OUT, margin_offset: Math.log(3) }
    expect(lapsFromMargin(Math.log(9), shifted)).toBeCloseTo(9 * 3 - 1)
  })
})

describe('stintLifeBand', () => {
  it('orders p10 <= median <= p90', () => {
    const b = stintLifeBand(Math.log(13), OUT)
    expect(b.p10).toBeLessThan(b.median)
    expect(b.median).toBeLessThan(b.p90)
  })

  it('median is exp(margin) - shift, independent of scale', () => {
    const a = stintLifeBand(Math.log(13), OUT)
    const b = stintLifeBand(Math.log(13), { ...OUT, aft_scale: 1.4 })
    expect(a.median).toBeCloseTo(12)
    expect(b.median).toBeCloseTo(a.median)
  })

  it('a wider scale widens the band symmetrically in log space', () => {
    const narrow = stintLifeBand(Math.log(13), { ...OUT, aft_scale: 0.25 })
    const wide = stintLifeBand(Math.log(13), { ...OUT, aft_scale: 0.75 })
    expect(wide.p90 - wide.p10).toBeGreaterThan(narrow.p90 - narrow.p10)
    // log-symmetry: p10 * p90 == median^2 once the shift is undone
    for (const b of [narrow, wide]) {
      expect((b.p10 + 1) * (b.p90 + 1)).toBeCloseTo((b.median + 1) ** 2, 6)
    }
  })

  it('falls back to 0.1/0.9 when the manifest omits the quantiles', () => {
    const bare = { ...OUT, quantiles: {} as Record<string, number> }
    const b = stintLifeBand(Math.log(13), bare)
    expect(b.p10).toBeCloseTo(stintLifeBand(Math.log(13), OUT).p10)
  })
})
