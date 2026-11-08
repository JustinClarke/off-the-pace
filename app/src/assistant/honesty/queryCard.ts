// AX-09 finding 1: the honesty checker only sees cards, and a query_data result (AX-06) is not a
// card. This projection turns a result into the flat FactCard the checker reads, so the rule
// COMPUTED_NOT_CARD_WORDING (trigger: label eq computed_not_card) can fire on it. AX-10 passes
// these alongside the fact cards in CheckInput.cards.
//
// The input is structural (the fields of AX-06's QueryResult this needs), so the checker does not
// depend on the query builder module.
import type { FactCard } from './checker'

export interface QueryResultLike {
  result_id: string
  view: string
  label: 'computed_not_card'
  /** The aggregated column (AX-06 carries it as aggregate.col; count(*) requests use the view's
   *  count measure name). */
  aggregate: { fn: string; col: string }
  rows: { n: number }[]
}

export function queryResultToCheckerCard(result: QueryResultLike): FactCard {
  const ns = result.rows.map((r) => r.n).filter((n) => typeof n === 'number' && Number.isFinite(n))
  return {
    id: result.result_id,
    metric: `${result.view}.${result.aggregate.col}`,
    label: 'computed_not_card',
    aggregate_fn: result.aggregate.fn,
    n: ns.length > 0 ? Math.min(...ns) : 0,
    n_unit: 'rows',
    source_page: result.view,
  }
}
