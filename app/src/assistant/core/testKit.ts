// AX-10 test helpers: the real generated tool schemas, a card store over the AX-21 demo cards, and
// stubbed query/list functions. No network, no wasm.
import fixture from '../prompt/__fixtures__/demo-cards.json'
import type { Card } from '../cards/card.types'
import { SYSTEM_PROMPT, TOOLS } from '../../../../worker/src/generated/tools'
import { createCardStore } from './cardStore'
import { createDispatcher, type DispatcherDeps } from './dispatcher'
import type { ToolDef } from './validateArgs'
import type { QueryOutcome, QueryResult } from '../queryBuilder/types'
import type { ListValuesResult } from '../listValues'
import type { LoopDeps } from './loop'
import type { ModelClient } from './types'

export const demoCards = (fixture as unknown as { cards: Card[] }).cards
export const tools = TOOLS as ToolDef[]
export const system = SYSTEM_PROMPT
export const toolsJson = JSON.stringify(TOOLS)

export function demoStore() {
  return createCardStore(demoCards)
}

export const okQuery = (id = 'q0000000001'): QueryResult => ({
  status: 'ok',
  view: 'qv_stints',
  filters_applied: [{ col: 'season', op: 'eq', val: 2024 }],
  grain: 'stint',
  aggregate: { fn: 'count', col: 'stint' },
  group_by: ['driver_id'],
  rows: [
    { driver_id: 'VER', value: 31, n: 31 },
    { driver_id: 'PER', value: 29, n: 29 },
  ],
  row_count: 2,
  rows_shown: 2,
  rows_dropped: 0,
  label: 'computed_not_card',
  notes: ['A plain aggregate computed from published data, not a fact card, rating or model output.'],
  result_id: id,
})

export function testDeps(over: Partial<DispatcherDeps> = {}): DispatcherDeps {
  return {
    tools,
    cards: demoStore(),
    listValues: async (): Promise<ListValuesResult> => ({ status: 'ok', rows: [{ code: 'PER', display: 'Sergio Perez', aliases_matched: ['checo'], seasons: '2018-2024' }] }),
    queryData: async (): Promise<QueryOutcome> => okQuery(),
    ...over,
  }
}

export function loopDeps(model: ModelClient, over: Partial<DispatcherDeps> = {}): LoopDeps & { dispatcher: ReturnType<typeof createDispatcher> } {
  const d = testDeps(over)
  const dispatcher = createDispatcher(d)
  return { model, dispatcher, store: d.cards, system, toolsJson }
}
