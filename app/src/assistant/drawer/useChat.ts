// AX-14 chat state: one question at a time through the AX-10 loop and the Worker. The Worker returns ONE
// JSON reply per round (no streaming), so the drawer shows step progress, then the checked answer.
// Failures map to a small set of kinds the drawer words in plain language; none of them touches the rest of the app.
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Card } from '../cards/card.types'
import type { HistoryTurn } from '../core/budget'
import { ask, type AskResult } from '../core/loop'
import { createWorkerClient, EndpointError } from '../core/modelClient'
import type { PageContext } from '../core/preload'
import type { ModelClient, ModelReply, ModelRequest, ToolCall, ToolResult } from '../core/types'
import type { Dispatcher } from '../core/dispatcher'
import type { DrawerRuntime } from './runtime'

export type ChatErrorKind = 'network' | 'paused' | 'limit' | 'rounds' | 'updated' | 'abuse' | 'upstream' | 'data' | 'unconfigured'

export const ERROR_TEXT: Record<ChatErrorKind, string> = {
  network: 'The assistant could not be reached. The rest of the app is unaffected; try again in a moment.',
  paused: 'Answers are paused for today. The rest of the app is unaffected.',
  limit: 'The daily question limit has been reached. It resets tomorrow.',
  rounds: 'This question used up its allowed steps before it had an answer. Try asking it more narrowly.',
  updated: 'The app was updated. Reload to keep asking.',
  abuse: 'The check that confirms you are a person did not pass. Try again.',
  upstream: 'The assistant is having a problem right now. Try again in a moment.',
  data: 'The data the assistant reads could not be loaded. Try again in a moment.',
  unconfigured: 'The assistant is not connected to a server in this build.',
}

export function classifyError(e: unknown): ChatErrorKind {
  if (e instanceof EndpointError) {
    if (e.status === 409 || e.code === 'app_updated') return 'updated'
    if (e.status === 503 || e.code === 'paused') return 'paused'
    if (e.code === 'round_limit') return 'rounds'
    if (e.status === 429) return 'limit'
    if (e.status === 403) return 'abuse'
    return 'upstream'
  }
  if (e instanceof TurnstileFailure) return 'abuse'
  if (e instanceof TypeError) return 'network' // fetch rejects with TypeError when the network or CORS fails
  return 'data'
}

export class TurnstileFailure extends Error {}

export interface Turn {
  id: number
  question: string
  status: 'pending' | 'done' | 'error'
  /** Step progress while pending ("Looking up cards ..."), newest last. */
  steps: string[]
  result?: AskResult
  /** Cards and results this question's grounding was run against (render time uses the same set). */
  sources?: { cards: Card[]; results: unknown[]; texts: string[] }
  error?: { kind: ChatErrorKind; text: string }
}

const TOOL_STEP: Record<string, string> = {
  get_fact_cards: 'Looking up cards',
  query_data: 'Running a bounded query',
  list_values: 'Looking up names',
  compare_lap_times: 'Comparing lap times',
  make_chart: 'Drawing a chart',
  explain_page: 'Reading the page notes',
  navigate: 'Finding the page',
}

export interface UseChatOptions {
  /** The Worker chat URL. Empty = unconfigured. */
  endpoint: string
  loadRuntime: () => Promise<DrawerRuntime>
  getTurnstileToken?: () => Promise<string | undefined>
  /** The current page, for the page-card pre-load. */
  getPage?: () => PageContext | null
  fetchImpl?: typeof fetch
}

export function useChat(o: UseChatOptions) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const nextId = useRef(1)
  const history = useRef<HistoryTurn[]>([])
  const optsRef = useRef(o)
  useEffect(() => {
    optsRef.current = o
  })

  const patch = (id: number, f: (t: Turn) => Turn) => setTurns((ts) => ts.map((t) => (t.id === id ? f(t) : t)))

  const send = useCallback(async (question: string) => {
    const q = question.trim()
    if (!q || busy) return
    const id = nextId.current++
    const step = (s: string) => patch(id, (t) => ({ ...t, steps: [...t.steps, s] }))
    setTurns((ts) => [...ts, { id, question: q, status: 'pending', steps: [], }])
    setBusy(true)
    const opts = optsRef.current
    try {
      if (!opts.endpoint) throw Object.assign(new Error('unconfigured'), { kind: 'unconfigured' as const })
      step('Loading the data')
      const rt = await opts.loadRuntime().catch((e) => {
        throw Object.assign(new Error(String(e)), { kind: 'data' as const })
      })
      const dispatcher = rt.newDispatcher()
      const watched: Dispatcher = {
        session: dispatcher.session,
        async dispatch(call: ToolCall): Promise<ToolResult> {
          step(`${TOOL_STEP[call.name] ?? 'Using a tool'}...`)
          return dispatcher.dispatch(call)
        },
      }
      const wire = createWorkerClient({
        endpoint: opts.endpoint,
        catalogueVersion: rt.catalogueVersion,
        fetch: opts.fetchImpl as never,
        turnstileToken: async () => {
          if (!opts.getTurnstileToken) return undefined
          step('Checking you are a person')
          return opts.getTurnstileToken()
        },
      })
      const model: ModelClient = {
        async chat(req: ModelRequest): Promise<ModelReply> {
          step(req.round === 1 ? 'Reading the question...' : 'Checking what came back...')
          return wire.chat(req)
        },
      }
      const result = await ask(q, rt.loopDeps(model, watched), { page: opts.getPage?.() ?? null, history: history.current })
      step('Checking the numbers...')
      const cards = new Map<string, Card>()
      for (const id of result.onScreenIds) {
        const c = rt.store.byId(id)
        if (c) cards.set(c.id, c)
      }
      for (const c of dispatcher.session.cards.values()) cards.set(c.id, c)
      history.current = [...history.current, { question: q, answer: result.answer }].slice(-2)
      patch(id, (t) => ({
        ...t,
        status: 'done',
        result,
        sources: { cards: [...cards.values()], results: result.visibleResults, texts: [q] },
      }))
    } catch (e) {
      const kind = (e as { kind?: ChatErrorKind }).kind ?? classifyError(e)
      patch(id, (t) => ({ ...t, status: 'error', error: { kind, text: ERROR_TEXT[kind] } }))
    } finally {
      setBusy(false)
    }
  }, [busy])

  const clear = useCallback(() => {
    setTurns([])
    history.current = []
  }, [])

  return { turns, busy, send, clear }
}
