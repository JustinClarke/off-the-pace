import { describe, it, expect } from 'vitest'
import { checkAnswer, checkRule, countByKind, policy } from './checker'

describe('AI-02 policy shape', () => {
  it('has unique rule codes and only declared kinds', () => {
    const codes = policy.rules.map((r) => r.code)
    expect(new Set(codes).size).toBe(codes.length)
    for (const r of policy.rules) expect(Object.keys(policy.kinds)).toContain(r.kind)
  })

  it('cites at least one source file for every rule and contradiction claim', () => {
    for (const r of policy.rules) expect(r.sources.length, r.code).toBeGreaterThan(0)
    for (const c of policy.contradictions) expect(c.claims.length, c.id).toBeGreaterThanOrEqual(2)
  })

  it('gives every active rule a failing and a passing example, and every pending rule a pending one', () => {
    for (const r of policy.rules) {
      const expects = r.examples.map((e) => e.expect)
      if (r.status === 'active') {
        expect(expects, r.code).toContain('fail')
        expect(expects, r.code).toContain('pass')
      } else {
        expect(expects, r.code).toContain('pending')
        expect(r.options?.length ?? 0, r.code).toBeGreaterThan(1)
      }
    }
  })

  it('compiles every pattern', () => {
    for (const r of policy.rules) {
      const pats = [
        ...r.required_wording.all_of.flat(),
        ...r.forbidden_claim.patterns,
        ...r.triggers.flatMap((t) => ('question' in t ? [t.question] : 'answer' in t ? [t.answer] : [])),
      ]
      for (const p of pats) expect(() => new RegExp(p, 'iu'), `${r.code}: ${p}`).not.toThrow()
    }
  })

  it('counts rules by kind', () => {
    const counts = countByKind()
    expect(Object.values(counts).reduce((a, b) => a + b, 0)).toBe(policy.rules.length)
  })
})

describe('AI-02 rule examples', () => {
  for (const rule of policy.rules) {
    for (const ex of rule.examples) {
      it(`${rule.code}: ${ex.name} -> ${ex.expect}`, () => {
        const res = checkRule(rule, ex.input)
        expect(res.verdict, JSON.stringify(res)).toBe(ex.expect)
      })
    }
  }

  // Passing examples should be clean against the whole policy, not only their own rule,
  // so they can serve as model answers in AI-07.
  for (const rule of policy.rules) {
    for (const ex of rule.examples.filter((e) => e.expect === 'pass')) {
      it(`${rule.code}: "${ex.name}" passes the whole policy`, () => {
        const report = checkAnswer(ex.input)
        expect(report.failed, JSON.stringify(report.results.filter((r) => r.verdict === 'fail'))).toEqual([])
      })
    }
  }
})

describe('AI-02 acceptance', () => {
  const card = {
    id: 'cov24',
    metric: 'interval_coverage',
    value: 0.83,
    source_page: '/app/blind-test-scoreboard',
    model_version: 'v14',
    caveats: ['IN_SAMPLE_FIT'],
    scope: { season: 2024 },
  }

  it('fails an answer that states an in-sample result as proof', () => {
    const report = checkAnswer({
      cards: [card],
      answer: 'The v14 band covered 83% of 2024 laps [card cov24]. That proves the intervals are honest.',
    })
    expect(report.ok).toBe(false)
    expect(report.failed).toContain('IN_SAMPLE_FIT')
  })

  it('passes an answer that quotes the same number with the required wording', () => {
    const report = checkAnswer({
      cards: [card],
      answer:
        'The v14 band covered 83% of 2024 laps [card cov24]. That is in-sample fit, since 2024 was part of the training set, not proof the intervals hold on new races.',
    })
    expect(report.ok).toBe(true)
    expect(report.results.find((r) => r.code === 'IN_SAMPLE_FIT')?.verdict).toBe('pass')
  })

  it('fires on the field fallback when a card has no caveat code yet', () => {
    const report = checkAnswer({
      cards: [{ id: 'x', metric: 'interval_coverage', value: 0.83, sample: 'in_sample' }],
      answer: 'Coverage was 83% [card x].',
    })
    expect(report.failed).toContain('IN_SAMPLE_FIT')
  })

  it('reports the chance-line rule as pending rather than passing or failing it', () => {
    const report = checkAnswer({
      cards: [{ id: 'c', metric: 'flag_chance', value: 0.62 }],
      answer: 'The experimental chance to reach the flag is 62% [card c]; it failed its 2025 acceptance bar.',
    })
    expect(report.ok).toBe(true)
    expect(report.pending).toEqual(['CHANCE_LINE_QUOTABLE'])
  })
})
