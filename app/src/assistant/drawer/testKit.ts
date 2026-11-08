// AX-14 test helpers: a DrawerRuntime over the AX-21 demo cards (no wasm, no network) and a canned Worker fetch.
import { createDispatcher } from '../core/dispatcher'
import { demoCards, demoStore, system, tools, toolsJson, okQuery } from '../core/testKit'
import type { DrawerRuntime } from './runtime'
import type { Card } from '../cards/card.types'

export { demoCards }

export const card = (id: string): Card => {
  const c = demoCards.find((x) => x.id === id)
  if (!c) throw new Error(`no demo card ${id}`)
  return c
}

export function fakeRuntime(catalogueVersion = 'cat-1'): DrawerRuntime {
  const store = demoStore()
  return {
    store,
    catalogueVersion,
    newDispatcher: () =>
      createDispatcher({
        tools,
        cards: store,
        listValues: async () => ({ status: 'ok', rows: [] }),
        queryData: async () => okQuery(),
      }),
    loopDeps: (model, dispatcher) => ({ model, dispatcher, store, system, toolsJson }),
  }
}

type Reply = { status?: number; body: unknown } | (() => never)

/** A fetch that answers with the queued replies in order (the last one repeats) and records the requests. */
export function cannedFetch(replies: Reply[]) {
  const calls: { url: string; headers: Record<string, string>; body: { messages: { role: string; content: string }[] } }[] = []
  let i = 0
  const f = (async (url: string, init: { headers: Record<string, string>; body: string }) => {
    calls.push({ url, headers: init.headers, body: JSON.parse(init.body) })
    const r = replies[Math.min(i++, replies.length - 1)]
    if (typeof r === 'function') r()
    const rr = r as { status?: number; body: unknown }
    const status = rr.status ?? 200
    return { ok: status < 400, status, json: async () => rr.body }
  }) as unknown as typeof fetch
  return { fetch: f, calls }
}

export const answer = (content: string, ticket = 'T1') => ({ body: { message: { role: 'assistant', content }, usage: { prompt_tokens: 100, completion_tokens: 20 }, ticket } })
