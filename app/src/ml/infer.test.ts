import { describe, it, expect } from 'vitest'
import { postProcessScalars, classifyProbs } from './infer'
import type { SurvivalOutput } from './manifest'

// The AFT contract the manifest ships. margin_offset is -ln(2) in practice (AFT
// applies log(base_score) as its intercept and base_score is 0.5); the exact value
// is measured at export, so these tests pin the ARITHMETIC, not the constant.
const LIFE_OUT: SurvivalOutput = {
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
/** Margin that decodes to exactly `laps` under LIFE_OUT. */
const marginFor = (laps: number) => Math.log(laps + LIFE_OUT.label_shift)

describe('postProcessScalars quantile trio', () => {
  it('row-sorts a crossed trio so p10 <= p50 <= p90', () => {
    const r = postProcessScalars(0.5, 0.2, 0.1, marginFor(10), LIFE_OUT) // crossed: p10 > p50 > p90
    expect(r.degradation_jump_p10_s).toBeCloseTo(0.1)
    expect(r.degradation_jump_s).toBeCloseTo(0.2)
    expect(r.degradation_jump_p90_s).toBeCloseTo(0.5)
  })

  it('leaves an already-ordered trio untouched', () => {
    const r = postProcessScalars(-1, 0, 2, marginFor(5), LIFE_OUT)
    expect([r.degradation_jump_p10_s, r.degradation_jump_s, r.degradation_jump_p90_s]).toEqual([-1, 0, 2])
  })

  it('clamps each quantile to the model bounds [-10, 10]', () => {
    const r = postProcessScalars(-99, 0, 99, marginFor(5), LIFE_OUT)
    expect(r.degradation_jump_p10_s).toBe(-10)
    expect(r.degradation_jump_p90_s).toBe(10)
  })

  it('honours custom bounds', () => {
    const r = postProcessScalars(-5, 0, 5, marginFor(1), LIFE_OUT, [-2, 2])
    expect(r.degradation_jump_p10_s).toBe(-2)
    expect(r.degradation_jump_p90_s).toBe(2)
  })
})

describe('postProcessScalars stint life (AFT)', () => {
  it('clips negative remaining life to 0', () => {
    // A margin below log(label_shift) decodes to a negative life before clipping.
    expect(postProcessScalars(0, 0, 0, -3, LIFE_OUT).remaining_stint_life_laps).toBe(0)
  })

  it('decodes the margin back to laps', () => {
    expect(postProcessScalars(0, 0, 0, marginFor(12.4), LIFE_OUT).remaining_stint_life_laps)
      .toBeCloseTo(12.4)
  })

  it('brackets the median with p10 <= median <= p90', () => {
    const r = postProcessScalars(0, 0, 0, marginFor(12), LIFE_OUT)
    expect(r.remaining_stint_life_p10_laps).toBeLessThan(r.remaining_stint_life_laps)
    expect(r.remaining_stint_life_p90_laps).toBeGreaterThan(r.remaining_stint_life_laps)
  })

  it('widens the band as the fitted scale grows', () => {
    const narrow = postProcessScalars(0, 0, 0, marginFor(12), { ...LIFE_OUT, aft_scale: 0.2 })
    const wide = postProcessScalars(0, 0, 0, marginFor(12), { ...LIFE_OUT, aft_scale: 0.9 })
    const w = (r: typeof narrow) => r.remaining_stint_life_p90_laps - r.remaining_stint_life_p10_laps
    expect(w(wide)).toBeGreaterThan(w(narrow))
  })

  it('applies margin_offset', () => {
    // offset shifts on the LOG scale, so laps+shift scales by exp(offset).
    const r = postProcessScalars(0, 0, 0, marginFor(7), { ...LIFE_OUT, margin_offset: Math.log(2) })
    expect(r.remaining_stint_life_laps).toBeCloseTo((7 + 1) * 2 - 1)
  })
})

describe('classifyProbs', () => {
  const order = ['0_to_2', '3_to_5', '6_plus', 'none_in_stint']

  it('returns the argmax label and maps probs to class_order', () => {
    const r = classifyProbs([0.1, 0.6, 0.2, 0.1], order)
    expect(r.label).toBe('3_to_5')
    expect(r.probabilities).toEqual({ '0_to_2': 0.1, '3_to_5': 0.6, '6_plus': 0.2, none_in_stint: 0.1 })
  })

  it('breaks ties toward the first (lowest-index) class', () => {
    const r = classifyProbs([0.4, 0.4, 0.1, 0.1], order)
    expect(r.label).toBe('0_to_2')
  })

  it('handles the last class winning', () => {
    expect(classifyProbs([0.1, 0.1, 0.1, 0.7], order).label).toBe('none_in_stint')
  })

  it('reads from a subarray view correctly', () => {
    const flat = new Float32Array([0, 0, 0, 0, 0.05, 0.05, 0.8, 0.1])
    const r = classifyProbs(flat.subarray(4, 8), order)
    expect(r.label).toBe('6_plus')
  })
})
