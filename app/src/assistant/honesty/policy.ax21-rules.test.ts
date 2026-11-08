// AX-21: the playbook conclusion rules, the `where` filter on cards_distinct_values, the
// THIN_SAMPLE trigger fix (held and unavailable cards carry n = 0 by schema and must not fire it),
// and the single-card case of ONE_SKILL_MEASURE.
import { describe, it, expect } from 'vitest'
import { checkAnswer, checkRule, policy, type FactCard, type Rule } from './checker'

const AX21_RULES = ['RATING_TRUST_LABEL', 'RANK_WITHIN_CI', 'POOLED_SC_RATE_ONLY', 'NOT_INDEPENDENT_EVIDENCE', 'COUNT_NOT_CAUSE', 'ONE_SKILL_MEASURE_NAMED']
const rule = (code: string): Rule => policy.rules.find((r) => r.code === code)!

describe('AX-21 new rules', () => {
  it('are present once each, after the 25 rules present at start', () => {
    const codes = policy.rules.map((r) => r.code)
    for (const c of AX21_RULES) expect(codes.filter((x) => x === c), c).toHaveLength(1)
    expect(policy.rules.length).toBeGreaterThanOrEqual(31)
    expect(codes.indexOf('AIR_STATE_FILTER')).toBeLessThan(codes.indexOf('RATING_TRUST_LABEL'))
  })

  for (const code of AX21_RULES) {
    it(`${code} is active, cites a source and has fail, pass and not_fired examples that hold`, () => {
      const r = rule(code)
      expect(r.status).toBe('active')
      expect(r.sources.length).toBeGreaterThan(0)
      const expects = r.examples.map((e) => e.expect)
      for (const k of ['fail', 'pass', 'not_fired'] as const) expect(expects, `${code} ${k}`).toContain(k)
      for (const ex of r.examples) expect(checkRule(r, ex.input).verdict, `${code}: ${ex.name}`).toBe(ex.expect)
      for (const ex of r.examples.filter((e) => e.expect === 'pass')) {
        expect(checkAnswer(ex.input).ok, `${code}: ${ex.name} passes the whole policy`).toBe(true)
      }
    })
  }
})

describe('AX-21 cards_distinct_values where filter', () => {
  const r = rule('NOT_INDEPENDENT_EVIDENCE')
  const c = (id: string, kind: string, group?: string): FactCard => ({ id, kind, metric: 'm', ...(group ? { shared_input_group: group } : {}) })

  it('counts only cards in the named group', () => {
    const input = { answer: 'x', cards: [c('a:1', 'era_rating.season', 'race_rating'), c('b:1', 'race.result')] }
    expect(checkRule(r, input).verdict).toBe('not_fired')
  })
  it('fires on two kinds in one group, not on one kind in each of two groups', () => {
    expect(checkRule(r, { answer: 'x', cards: [c('a:1', 'era_rating.season', 'race_rating'), c('b:1', 'race.teammate_gap', 'race_rating')] }).verdict).toBe('fail')
    expect(
      checkRule(r, { answer: 'x', cards: [c('a:1', 'era_rating.season', 'race_rating'), c('b:1', 'party_mode.season', 'constructor_pace')] }).verdict,
    ).toBe('not_fired')
  })
  it('without where, ONE_SKILL_MEASURE still counts every card (existing trigger unchanged)', () => {
    const t = rule('ONE_SKILL_MEASURE').triggers[0]
    expect(t).toEqual({ cards_distinct_values: { field: 'skill_measure', min: 2 } })
  })
})

describe('AX-21 THIN_SAMPLE trigger', () => {
  const thin = rule('THIN_SAMPLE')
  const base = { metric: 'cliff_onset_lap', n_unit: 'stints' }

  it('trigger 2 gains only the held / unavailable exclusions', () => {
    expect(thin.triggers[1]).toEqual({
      card: [
        { field: 'n_unit', op: 'eq', value: 'stints' },
        { field: 'n', op: 'lt', value: 8 },
        { field: 'status', op: 'ne', value: 'held' },
        { field: 'label', op: 'ne', value: 'unavailable' },
      ],
    })
  })
  it('still fires on a real thin-sample card (no status, or status active)', () => {
    expect(checkRule(thin, { answer: 'clearly lap 14', cards: [{ id: 'c:1', ...base, value: 14, n: 5 }] }).verdict).toBe('fail')
    expect(checkRule(thin, { answer: 'x', cards: [{ id: 'c:2', ...base, value: 14, n: 5, status: 'active', label: 'modelled' }] }).fired_by).toHaveLength(1)
    expect(checkRule(thin, { answer: 'x', cards: [{ id: 'c:3', ...base, value: 14, n: 0, status: 'active', label: 'computed' }] }).fired_by).toHaveLength(1)
  })
  it('does not fire on a held stub or an unavailable card (n = 0 by schema)', () => {
    const heldStub = { id: 'pit_strategy.verdict:2024_1:VER:1', ...base, metric: 'strategy_verdict', value: null, n: 0, status: 'held', label: 'modelled' }
    const unavailable = { id: 'x.y:1', ...base, value: null, n: 0, status: 'active', label: 'unavailable' }
    expect(checkRule(thin, { answer: 'held', cards: [heldStub] }).verdict).toBe('not_fired')
    expect(checkRule(thin, { answer: 'no value', cards: [unavailable] }).verdict).toBe('not_fired')
  })
  it('the caveat trigger still fires on any card', () => {
    expect(checkRule(thin, { answer: 'x', cards: [{ id: 'c:4', metric: 'm', status: 'held', caveats: ['THIN_SAMPLE'] }] }).fired_by).toHaveLength(1)
  })
})

describe('AX-21 ONE_SKILL_MEASURE single-card case', () => {
  const named = rule('ONE_SKILL_MEASURE_NAMED')
  const gap: FactCard = { id: 'race.teammate_gap:2024_1:VER', metric: 'teammate_gap_s', value: -0.622, n: 46, n_unit: 'laps', skill_measure: 'teammate_paired_median' }
  it('one skill card fires the single-card rule but not the two-measure rule', () => {
    const input = { answer: 'Verstappen was 0.622 s per lap ahead of Perez.', cards: [gap] }
    expect(checkRule(named, input).verdict).toBe('fail')
    expect(checkRule(rule('ONE_SKILL_MEASURE'), input).verdict).toBe('not_fired')
  })
  it('naming the measure passes; calling a residual driver error fails', () => {
    expect(checkRule(named, { answer: "Verstappen's median gap to Perez on 46 paired laps was -0.622 s per lap.", cards: [gap] }).verdict).toBe('pass')
    const resid: FactCard = { id: 'race_driver.skill_components:2024_1:VER:rbr', metric: 'm', skill_measure: 'lap_residual', status: 'held' }
    expect(checkRule(named, { answer: 'His lap residual is driver error.', cards: [resid] }).verdict).toBe('fail')
    expect(checkRule(named, { answer: 'His lap residual is unexplained time, not driver error.', cards: [resid] }).verdict).toBe('pass')
  })
})
