// AX-09: the seven rules added on 2026-11-08 carry all three example kinds, and the policy shape
// still holds (codes unique, kinds declared).
import { describe, it, expect } from 'vitest'
import { checkRule, countByKind, policy } from './checker'

const AX09_RULES = [
  'COMPUTED_NOT_CARD_WORDING',
  'HELD_CARD_WORDING',
  'UNAVAILABLE_IS_NOT_ZERO',
  'LAP_MAP_GREY_CELL',
  'SURVIVAL_LOWER_BOUND',
  'GHOST_IS_COUNTERFACTUAL',
  'ONE_SKILL_MEASURE',
]

describe('AX-09 new rules', () => {
  it('are all present, once each', () => {
    const codes = policy.rules.map((r) => r.code)
    expect(new Set(codes).size).toBe(codes.length)
    for (const code of AX09_RULES) expect(codes.filter((c) => c === code), code).toHaveLength(1)
  })

  it('declares the two new kinds and uses only declared kinds', () => {
    expect(Object.keys(policy.kinds)).toEqual(expect.arrayContaining(['computed_not_card', 'held_card']))
    for (const r of policy.rules) expect(Object.keys(policy.kinds), r.code).toContain(r.kind)
    expect(countByKind().computed_not_card).toBe(1)
    expect(countByKind().held_card).toBe(1)
  })

  for (const code of AX09_RULES) {
    it(`${code} is active and has fail, pass and not_fired examples that hold`, () => {
      const rule = policy.rules.find((r) => r.code === code)!
      expect(rule.status).toBe('active')
      const expects = rule.examples.map((e) => e.expect)
      for (const k of ['fail', 'pass', 'not_fired'] as const) expect(expects, `${code} ${k}`).toContain(k)
      for (const ex of rule.examples) expect(checkRule(rule, ex.input).verdict, `${code}: ${ex.name}`).toBe(ex.expect)
    })
  }
})
