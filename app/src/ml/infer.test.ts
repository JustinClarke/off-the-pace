import { describe, it, expect } from 'vitest'
import { postProcessScalars, classifyProbs } from './infer'

describe('postProcessScalars quantile trio', () => {
  it('row-sorts a crossed trio so p10 <= p50 <= p90', () => {
    const r = postProcessScalars(0.5, 0.2, 0.1, 10) // crossed: p10 > p50 > p90
    expect(r.degradation_jump_p10_s).toBeCloseTo(0.1)
    expect(r.degradation_jump_s).toBeCloseTo(0.2)
    expect(r.degradation_jump_p90_s).toBeCloseTo(0.5)
  })

  it('leaves an already-ordered trio untouched', () => {
    const r = postProcessScalars(-1, 0, 2, 5)
    expect([r.degradation_jump_p10_s, r.degradation_jump_s, r.degradation_jump_p90_s]).toEqual([-1, 0, 2])
  })

  it('clamps each quantile to the model bounds [-10, 10]', () => {
    const r = postProcessScalars(-99, 0, 99, 5)
    expect(r.degradation_jump_p10_s).toBe(-10)
    expect(r.degradation_jump_p90_s).toBe(10)
  })

  it('honours custom bounds', () => {
    const r = postProcessScalars(-5, 0, 5, 1, [-2, 2])
    expect(r.degradation_jump_p10_s).toBe(-2)
    expect(r.degradation_jump_p90_s).toBe(2)
  })
})

describe('postProcessScalars stint life', () => {
  it('clips negative remaining life to 0', () => {
    expect(postProcessScalars(0, 0, 0, -3).remaining_stint_life_laps).toBe(0)
  })

  it('passes positive remaining life through', () => {
    expect(postProcessScalars(0, 0, 0, 12.4).remaining_stint_life_laps).toBeCloseTo(12.4)
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
