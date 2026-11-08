import { describe, it, expect } from 'vitest'
import { extractAnswerNumbers, findUngroundedNumbers } from './grounding'
import { demoCards, okQuery } from './core/testKit'
import type { Card } from './cards/card.types'

const gap = demoCards.find((c) => c.id === 'race.teammate_gap:2024_1:VER') as Card
// value -0.6219999, interval [-0.755, -0.39], n 46

describe('findUngroundedNumbers', () => {
  it('accepts card value, interval ends and n at the answer precision, sign-blind', () => {
    const a = 'Verstappen was 0.62 s a lap faster [race.teammate_gap:2024_1:VER], interval 0.39 to 0.75 s, over 46 paired laps.'
    expect(findUngroundedNumbers(a, { cards: [gap] })).toEqual([])
  })

  it('flags a number that is in no card', () => {
    const bad = findUngroundedNumbers('He was 0.71 s faster over 46 laps.', { cards: [gap] })
    expect(bad.map((b) => b.text)).toEqual(['0.71'])
    expect(bad[0].context).toContain('0.71')
  })

  it('a whole number must match a whole source exactly; it never rounds a small decimal', () => {
    const c = { id: 'x:1', metric: 'm', value: 0.8, n: 5 }
    expect(findUngroundedNumbers('It was 1 s.', { cards: [c] }).map((b) => b.text)).toEqual(['1'])
    expect(findUngroundedNumbers('It was 5 laps.', { cards: [c] })).toEqual([])
    const big = { id: 'x:2', metric: 'm', value: 46.8, n: 5 }
    expect(findUngroundedNumbers('About 47 laps.', { cards: [big] })).toEqual([])
  })

  it('percent matches the source x 100', () => {
    const c = { id: 'x:1', metric: 'm', value: 0.33, n: 12 }
    expect(findUngroundedNumbers('About 33% of them.', { cards: [c] })).toEqual([])
    expect(findUngroundedNumbers('About 34% of them.', { cards: [c] }).map((b) => b.text)).toEqual(['34%'])
  })

  it('an interval level grounds "95%" but never a decimal like 0.9', () => {
    const c = { id: 'x:1', metric: 'm', value: 5.5, n: 20, interval: { low: 4, high: 7, kind: 'ci_bayes', level: 0.95 } }
    expect(findUngroundedNumbers('A 95% interval of 4.0 to 7.0.', { cards: [c] })).toEqual([])
    expect(findUngroundedNumbers('It was 0.9 s.', { cards: [c] }).map((b) => b.text)).toEqual(['0.9'])
  })

  it('does not check years, ids, citations, list markers or numbers glued to letters', () => {
    const a = ['In 2024 (race 2024_1) see [card race.result:2024_1:VER] and race.result:2024_1:PER.', '1. first point', 'The F1 car on the v16 labels, 2018-2025.'].join('\n')
    expect(findUngroundedNumbers(a, { cards: [] })).toEqual([])
  })

  it('a bare year-like count with a decimal or percent is still checked', () => {
    expect(findUngroundedNumbers('It was 2024.5 s.', { cards: [] }).map((b) => b.text)).toEqual(['2024.5'])
  })

  it('accepts numbers in a query_data result (rows, n, counts) and rejects others', () => {
    const r = okQuery()
    expect(findUngroundedNumbers('Verstappen made 31 stints and Perez 29 [q0000000001].', { results: [r] })).toEqual([])
    expect(findUngroundedNumbers('Verstappen made 32 stints.', { results: [r] }).map((b) => b.text)).toEqual(['32'])
  })

  it('numbers the user typed in the question are sources; numbers only on a page summary are not', () => {
    expect(findUngroundedNumbers('You asked about lap 20; I have no card for it.', { texts: ['What if he pitted on lap 20?'] })).toEqual([])
    expect(findUngroundedNumbers('The page says 15 pages.', { cards: [], results: [], texts: ['How many pages?'] }).map((b) => b.text)).toEqual(['15'])
  })

  it('round N is accepted only when a source carries that race number', () => {
    expect(findUngroundedNumbers('That was round 1 of the season.', { cards: [gap] })).toEqual([])
    expect(findUngroundedNumbers('That was round 7 of the season.', { cards: [gap] }).map((b) => b.text)).toEqual(['7'])
  })

  it('thousands separators and P-positions are read as numbers', () => {
    const nums = extractAnswerNumbers('He finished P3 after 1,200 m.')
    expect(nums.map((n) => n.value)).toEqual([3, 1200])
  })

  it('an answer with no digits is grounded; an empty-result answer has no number to flag', () => {
    expect(findUngroundedNumbers('I have no data for that race.', { cards: [], results: [] })).toEqual([])
  })

  it('held and unavailable cards (value null, n 0) ground nothing but 0', () => {
    const held = { id: 'h:1', metric: 'm', value: null, n: 0 }
    expect(findUngroundedNumbers('It is worth 0.4 s.', { cards: [held] }).map((b) => b.text)).toEqual(['0.4'])
  })
})
