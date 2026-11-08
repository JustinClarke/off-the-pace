// AX-01 acceptance: validateCard accepts the ten fixture cards and rejects the ten bad ones.
import { describe, it, expect } from 'vitest'
import { validateCard, cardSchema, keywordsUsed, SUPPORTED_KEYWORDS, ANNOTATION_KEYWORDS } from './validate'
import { validCards, badCards, makeCard } from './card.fixture'

describe('AX-01 validateCard', () => {
  it('has ten valid and ten bad fixtures', () => {
    expect(validCards).toHaveLength(10)
    expect(badCards).toHaveLength(10)
    expect(new Set(validCards.map((c) => c.id)).size).toBe(10)
  })

  it.each(validCards.map((c) => [c.id, c] as const))('accepts %s', (_id, card) => {
    const r = validateCard(card, card.interval ? { expectedIntervalKind: card.interval.kind } : {})
    expect(r.errors).toEqual([])
    expect(r.ok).toBe(true)
  })

  it.each(badCards.map((b) => [b.name, b] as const))('rejects: %s', (_name, b) => {
    const r = validateCard(b.card, b.expectedIntervalKind ? { expectedIntervalKind: b.expectedIntervalKind } : {})
    expect(r.ok).toBe(false)
    expect(r.errors.length).toBeGreaterThan(0)
  })

  it('names the reason for each bad card', () => {
    const want: Record<string, RegExp> = {
      'no n': /^n: required/,
      'modelled with no interval': /interval: expected object/,
      'experimental with kind none': /interval\.kind: must not match/,
      'unavailable with a value': /value: expected null/,
      'held with a value': /value: expected null/,
      'unavailable with no reason': /unavailable_reason: expected string/,
      'n.unit outside the enum': /n\.unit: "seasons" is not one of/,
      'label outside the vocabulary': /label: "estimated" is not one of/,
      'relabelled interval kind': /relabelled interval kind/,
      'low above high': /low 0\.2 is above high -0\.2/,
    }
    for (const b of badCards) {
      const r = validateCard(b.card, b.expectedIntervalKind ? { expectedIntervalKind: b.expectedIntervalKind } : {})
      expect(r.errors.some((e) => want[b.name].test(e)), `${b.name}: ${r.errors.join(' / ')}`).toBe(true)
    }
  })

  it('also rejects: null value on an active non-unavailable card, unknown field, id not starting with kind, held with n > 0', () => {
    expect(validateCard(makeCard({ value: null })).ok).toBe(false)
    expect(validateCard({ ...makeCard(), extra: 1 }).ok).toBe(false)
    expect(validateCard(makeCard({ id: 'other.kind:2024:LEC' })).ok).toBe(false)
    expect(
      validateCard(makeCard({ status: 'held', value: null, held_reason: 'x', n: { count: 3, unit: 'stints' }, interval: null })).ok,
    ).toBe(false)
    expect(validateCard(makeCard({ value: Number.NaN })).ok).toBe(false)
  })

  it('allows a null interval on held and unavailable cards (finding 3)', () => {
    expect(validateCard(validCards[5]).ok).toBe(true)
    expect(validateCard(validCards[6]).ok).toBe(true)
  })

  it('uses only JSON Schema keywords the interpreter implements', () => {
    const known = new Set<string>([...SUPPORTED_KEYWORDS, ...ANNOTATION_KEYWORDS])
    const unknown = [...keywordsUsed(cardSchema)].filter((k) => !known.has(k))
    expect(unknown).toEqual([])
  })
})
