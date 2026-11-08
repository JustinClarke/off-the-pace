// AX-09: the cards_distinct_values trigger.
import { describe, it, expect } from 'vitest'
import { checkRule, type Rule, type FactCard } from './checker'

const rule = (min: number, field = 'skill_measure'): Rule => ({
  code: 'T_DISTINCT',
  kind: 'known_gap',
  status: 'active',
  applies_to: { pages: [], metrics: [] },
  condition: 'test',
  triggers: [{ cards_distinct_values: { field, min } }],
  required_wording: { description: 'say different', all_of: [['\\bdifferent\\b']] },
  forbidden_claim: { description: 'none', patterns: [] },
  sources: [],
  examples: [],
})

const c = (id: string, skill_measure: unknown): FactCard => ({ id, metric: 'm', skill_measure })

describe('cards_distinct_values trigger', () => {
  it('fires at 2 distinct values', () => {
    const r = checkRule(rule(2), { answer: 'x', cards: [c('a', 'loro'), c('b', 'era')] })
    expect(r.verdict).toBe('fail')
    expect(r.fired_by[0]).toMatch(/a, b carry 2 distinct skill_measure/)
  })

  it('does not fire at 1 distinct value, however many cards carry it', () => {
    const r = checkRule(rule(2), { answer: 'x', cards: [c('a', 'loro'), c('b', 'loro'), c('c', 'loro')] })
    expect(r.verdict).toBe('not_fired')
  })

  it('ignores null and missing values', () => {
    const cards = [c('a', 'loro'), c('b', null), { id: 'c', metric: 'm' }]
    expect(checkRule(rule(2), { answer: 'x', cards }).verdict).toBe('not_fired')
  })

  it('reads a dotted path and honours min', () => {
    const cards: FactCard[] = [
      { id: 'a', metric: 'm', policy_fields: { skill_measure: 'x' } },
      { id: 'b', metric: 'm', policy_fields: { skill_measure: 'y' } },
      { id: 'c', metric: 'm', policy_fields: { skill_measure: 'z' } },
    ]
    expect(checkRule(rule(3, 'policy_fields.skill_measure'), { answer: 'x', cards }).verdict).toBe('fail')
    expect(checkRule(rule(4, 'policy_fields.skill_measure'), { answer: 'x', cards }).verdict).toBe('not_fired')
  })

  it('passes when fired and the wording is present', () => {
    const r = checkRule(rule(2), { answer: 'These are different measures.', cards: [c('a', 'loro'), c('b', 'era')] })
    expect(r.verdict).toBe('pass')
  })
})
