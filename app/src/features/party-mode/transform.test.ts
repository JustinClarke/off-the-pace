import { describe, it, expect } from 'vitest'
import { transform, toCsvRows, deltaSe, deltaInterval, classify } from './transform'
import type { PartyModeRow } from './queries'

const makeRow = (overrides: Partial<PartyModeRow> = {}): PartyModeRow => ({
  constructor_id: 'Ferrari',
  race_pace_s: -0.83,
  quali_pace_s: -0.67,
  delta_s: 0.16,
  race_se_s: 0.03,
  quali_se_s: 0.04,
  race_obs: 101,
  quali_obs: 12,
  ...overrides,
})

describe('transform', () => {
  it('classifies negative delta as party mode', () => {
    const entries = transform([makeRow({ delta_s: -0.38 })])
    expect(entries[0].mode).toBe('party')
  })

  it('classifies positive delta as race mode', () => {
    const entries = transform([makeRow({ delta_s: 0.59 })])
    expect(entries[0].mode).toBe('race')
  })

  it('classifies small delta as no_clear_gap', () => {
    const entries = transform([makeRow({ delta_s: 0.05 })])
    expect(entries[0].mode).toBe('no_clear_gap')
  })

  it('maps constructor_id to constructor', () => {
    const entries = transform([makeRow({ constructor_id: 'Red Bull Racing' })])
    expect(entries[0].constructor).toBe('Red Bull Racing')
  })

  it('returns empty for empty input', () => {
    expect(transform([])).toEqual([])
  })
})

describe('delta labels and season grain (AP-07)', () => {
  it('combines two known SEs as sqrt(se_q² + se_r²)', () => {
    expect(deltaSe(0.04, 0.03)).toBeCloseTo(0.05, 12)
    expect(deltaSe(null, 0.03)).toBeNull()
  })

  it('carries delta_se_s and a ±1.96·SE CI onto the entry and the CSV', () => {
    const [e] = transform([makeRow({ delta_s: 0.16 })])
    expect(e.delta_se_s).toBeCloseTo(0.05, 12)
    expect(e.delta_ci_low_s).toBeCloseTo(0.16 - 0.098, 12)
    expect(e.delta_ci_high_s).toBeCloseTo(0.16 + 0.098, 12)
    expect(e.delta_ci_covers_zero).toBe(false)
    const [row] = toCsvRows([e])
    expect(row.delta_se_s).toBe('0.050')
    expect(row.delta_ci_low_s).toBe('0.062')
    expect(row.delta_ci_high_s).toBe('0.258')
  })

  it('a -0.30 delta whose CI covers 0 is no_clear_gap, with the flag set', () => {
    // SE sqrt(0.2² + 0.1²) = 0.2236: CI [-0.738, 0.138]
    const [e] = transform([makeRow({ delta_s: -0.3, quali_se_s: 0.2, race_se_s: 0.1 })])
    expect(e.delta_ci_covers_zero).toBe(true)
    expect(e.mode).toBe('no_clear_gap')
    expect(toCsvRows([e])[0].delta_ci_covers_zero).toBe(true)
  })

  it('a -0.30 delta with CI wholly below 0 is party', () => {
    const [e] = transform([makeRow({ delta_s: -0.3, quali_se_s: 0.04, race_se_s: 0.03 })])
    expect(e.delta_ci_covers_zero).toBe(false)
    expect(e.mode).toBe('party')
  })

  it('null delta gives no label and null flags', () => {
    const [e] = transform([makeRow({ race_pace_s: null as unknown as number, delta_s: null as unknown as number, race_se_s: null })])
    expect(e.mode).toBeNull()
    expect(e.delta_ci_covers_zero).toBeNull()
  })

  it('season grain: SE from the query, t(k-1) multiplier, races_n carried', () => {
    // k = 16 -> t(15) = 2.1314
    const [e] = transform([makeRow({ delta_s: -0.3, race_se_s: null, quali_se_s: null, delta_se_s: 0.1, races_n: 16 })])
    expect(e.delta_ci_low_s).toBeCloseTo(-0.3 - 0.21314, 12)
    expect(e.delta_ci_high_s).toBeCloseTo(-0.3 + 0.21314, 12)
    expect(e.mode).toBe('party')
    expect(e.races_n).toBe(16)
    expect(toCsvRows([e])[0].races_n).toBe(16)
  })

  it('season grain with k < 3 (null SE) has no CI and no label', () => {
    const [e] = transform([makeRow({ delta_s: -0.3, race_se_s: null, quali_se_s: null, delta_se_s: null, races_n: 2 })])
    expect(e.delta_ci_low_s).toBeNull()
    expect(e.mode).toBeNull()
  })

  it('season SE where scatter dominates is larger than the estimation-error SE', () => {
    // per-race deltas 0, 0.4, 0.8, 1.2; se_d² each 0.02: var_samp = 0.2667 > 0.02
    const d = [0, 0.4, 0.8, 1.2]
    const mean = d.reduce((a, b) => a + b, 0) / 4
    const v = d.reduce((a, b) => a + (b - mean) ** 2, 0) / 3
    expect(Math.sqrt(Math.max(v, 0.02) / 4)).toBeCloseTo(Math.sqrt(v / 4), 12)
    expect(Math.sqrt(Math.max(v, 0.02) / 4)).toBeGreaterThan(Math.sqrt(0.02 / 4))
  })
})

describe('classify edges (AP-07)', () => {
  it('exactly -0.15 and +0.15 are not labelled', () => {
    expect(classify(-0.15, -0.5, -0.1)).toBe('no_clear_gap')
    expect(classify(0.15, 0.1, 0.5)).toBe('no_clear_gap')
  })
  it('just past the threshold with a clear CI is labelled', () => {
    expect(classify(-0.1501, -0.5, -0.01)).toBe('party')
    expect(classify(0.1501, 0.01, 0.5)).toBe('race')
  })
  it('a CI touching 0 is not clear', () => {
    expect(classify(-0.3, -0.6, 0)).toBe('no_clear_gap')
    expect(classify(0.3, 0, 0.6)).toBe('no_clear_gap')
  })
  it('null delta or null CI gives null', () => {
    expect(classify(null, -1, 1)).toBeNull()
    expect(classify(-0.3, null, null)).toBeNull()
  })
})

describe('delta SE and CI (AP-03)', () => {
  it('combines two known SEs as sqrt(se_q² + se_r²)', () => {
    expect(deltaSe(0.04, 0.03)).toBeCloseTo(0.05, 12)
    expect(deltaSe(null, 0.03)).toBeNull()
  })

  it('carries delta_se_s and a ±1.96·SE CI onto the entry and the CSV', () => {
    const [e] = transform([makeRow({ delta_s: 0.16 })])
    expect(e.delta_se_s).toBeCloseTo(0.05, 12)
    expect(e.delta_ci_low_s).toBeCloseTo(0.16 - 0.098, 12)
    expect(e.delta_ci_high_s).toBeCloseTo(0.16 + 0.098, 12)
    const [row] = toCsvRows([e])
    expect(row.delta_se_s).toBe('0.050')
    expect(row.delta_ci_low_s).toBe('0.062')
    expect(row.delta_ci_high_s).toBe('0.258')
    expect(deltaInterval(0.3, 0.1).coversZero).toBe(false)
    expect(deltaInterval(null, 0.1).coversZero).toBeNull()
  })

  it('CSV does not throw on a race with no race-pace estimate', () => {
    const row = makeRow({ race_pace_s: null as unknown as number, delta_s: null as unknown as number, race_se_s: null })
    const [csv] = toCsvRows(transform([row]))
    expect(csv.delta_quali_minus_race_s).toBeNull()
    expect(csv.delta_se_s).toBeNull()
  })
})
