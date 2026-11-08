// AX-01 acceptance: both projections, the two checker triggers, the token bound.
import { describe, it, expect } from 'vitest'
import { toModelProjection, toCheckerCard } from './project'
import { validCards, makeCard } from './card.fixture'
import { checkRule, policy } from '../honesty/checker'
import { estimateTokens } from '../../nav/pageSummaries.mjs'

const rule = (code: string) => {
  const r = policy.rules.find((x) => x.code === code)
  if (!r) throw new Error(`no rule ${code}`)
  return r
}

describe('AX-01 toModelProjection', () => {
  it.each(validCards.map((c) => [c.id, c] as const))('%s fits in 70 tokens and hides links and versions', (_id, card) => {
    const text = JSON.stringify(toModelProjection(card))
    expect(estimateTokens(text), text).toBeLessThanOrEqual(70)
    for (const banned of ['route', 'params', 'source_columns', 'versions']) expect(text).not.toContain(banned)
  })

  it('uses the compact keys of design 2.2', () => {
    const p = toModelProjection(validCards[1])
    expect(p).toEqual({
      id: 'race_lost.component:2024_8:LEC:compound',
      m: 'compound component s total',
      v: -3.412,
      u: 's',
      lbl: 'modelled',
      n: '51 laps',
      iv: [-3.9, -2.9, 'lap_noise_band'],
      cav: ['THIN_SAMPLE'],
      pg: 'race-lost',
    })
  })

  it('adds why only when the value is null', () => {
    expect(toModelProjection(validCards[0])).not.toHaveProperty('why')
    expect(toModelProjection(validCards[5]).why).toBe('no paired teammate lap this season')
    const why = toModelProjection(validCards[6]).why ?? ''
    expect(why).toMatch(/^PIT_CALL_REPRODUCTION_RATE/)
    expect(why.length).toBeLessThanOrEqual(64)
    expect(why.endsWith('…')).toBe(true)
  })

  it('AX-07 ruling 4: trust, rank_sep and cov appear only when the card carries them', () => {
    const base = toModelProjection(makeCard())
    expect(base).not.toHaveProperty('trust')
    expect(base).not.toHaveProperty('rank_sep')
    expect(base).not.toHaveProperty('cov')
    const p = toModelProjection(makeCard({ policy_fields: { rating_trust_label: 'thin', rank_separated_from_next: false, coverage_reason: 'OK' } }))
    expect(p).toMatchObject({ trust: 'thin', rank_sep: false, cov: 'OK' })
    // about 40 chars per card, well inside the 70-token cap
    expect(estimateTokens(JSON.stringify(p))).toBeLessThanOrEqual(70)
    // null values are not emitted
    const n = toModelProjection(makeCard({ policy_fields: { rating_trust_label: null, rank_separated_from_next: null } }))
    expect(n).not.toHaveProperty('trust')
    expect(n).not.toHaveProperty('rank_sep')
  })

  it('gives iv null for no interval or kind none', () => {
    expect(toModelProjection(validCards[2]).iv).toBeNull()
    expect(toModelProjection(validCards[3]).iv).toBeNull()
  })
})

describe('AX-01 toCheckerCard', () => {
  it('flattens n, page, source, versions and policy fields', () => {
    const c = toCheckerCard(validCards[7])
    expect(c).toMatchObject({ n: 24, n_unit: 'races', source_page: 'era-ratings-timeline', model_version: 'm7', is_in_envelope: true })
    expect(c.source_table).toBe('int_era_normalized_driver_rating')
    expect(c.label).toBe('modelled')
    expect(c.status).toBe('active')
    expect(c).not.toHaveProperty('policy_fields')
  })

  it('a card with n = 5 stints fires THIN_SAMPLE', () => {
    const card = makeCard({ n: { count: 5, unit: 'stints' } })
    const r = checkRule(rule('THIN_SAMPLE'), { answer: 'x', cards: [toCheckerCard(card)] })
    expect(r.fired_by.some((f) => f.includes('n_unit eq "stints"'))).toBe(true)
    expect(r.verdict).not.toBe('not_fired')
    // and does not fire on 24 races
    expect(checkRule(rule('THIN_SAMPLE'), { answer: 'x', cards: [toCheckerCard(makeCard())] }).verdict).toBe('not_fired')
  })

  it('a blind-test-scoreboard card with sample in_sample fires IN_SAMPLE_FIT', () => {
    const card = makeCard({
      sample: 'in_sample',
      page: { route: '/ml/blind-test-scoreboard', params: {}, docs_slug: 'blind-test-scoreboard' },
    })
    const r = checkRule(rule('IN_SAMPLE_FIT'), { answer: 'x', cards: [toCheckerCard(card)] })
    expect(r.fired_by.some((f) => f.includes('source_page'))).toBe(true)
    expect(r.fired_by.some((f) => f.includes('sample eq "in_sample"'))).toBe(true)
    expect(r.verdict).toBe('fail')
  })
})
