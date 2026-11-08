// AX-09 finding 1: a query_data result projected into a checker card.
import { describe, it, expect } from 'vitest'
import { checkAnswer } from './checker'
import { queryResultToCheckerCard, type QueryResultLike } from './queryCard'

const result: QueryResultLike = {
  result_id: 'a1b2c3d4e5f6',
  view: 'qv_laps',
  label: 'computed_not_card',
  aggregate: { fn: 'median', col: 'lap_time_s' },
  rows: [{ n: 41 }, { n: 7 }, { n: 55 }],
}

describe('queryResultToCheckerCard', () => {
  it('projects id, metric, label, n, n_unit and source_page', () => {
    expect(queryResultToCheckerCard(result)).toEqual({
      id: 'a1b2c3d4e5f6',
      metric: 'qv_laps.lap_time_s',
      label: 'computed_not_card',
      aggregate_fn: 'median',
      n: 7,
      n_unit: 'rows',
      source_page: 'qv_laps',
    })
  })

  it('uses 0 for n when there are no rows', () => {
    expect(queryResultToCheckerCard({ ...result, rows: [] }).n).toBe(0)
  })

  it('makes COMPUTED_NOT_CARD_WORDING fire', () => {
    const card = queryResultToCheckerCard(result)
    const bad = checkAnswer({ cards: [card], answer: 'His predicted lap time is 81.2 s.' })
    expect(bad.failed).toContain('COMPUTED_NOT_CARD_WORDING')
    const good = checkAnswer({
      cards: [card],
      answer: 'The plain median lap time was 81.2 s, computed from the published lap data [result a1b2c3d4e5f6].',
    })
    expect(good.ok).toBe(true)
    expect(good.results.find((r) => r.code === 'COMPUTED_NOT_CARD_WORDING')?.verdict).toBe('pass')
  })
})
