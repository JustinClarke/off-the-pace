// AX-10 loop: one question -> at most 4 tool calls, at most 5 model rounds, one repair turn.
//
//   1. page-card pre-load into the page-context block (0 tool calls for an on-screen number)
//   2. model round; tool calls go to the dispatcher; each result is fitted to its 1,200-token slot
//   3. calls beyond the 4th get {status:'error', reason:'tool_call_limit'} and the model is told to answer
//      from what it has; the 4th result carries the same note
//   4. the draft goes through checkAnswer + findUngroundedNumbers; a failure sends ONE repair message
//      (failed codes, missing wording, ungrounded numbers). A second failure returns the second draft
//      with the failures attached as notes: never silently passed.
//
// The Worker's ticket allows 5 model rounds in all (worker/src/config.ts MAX_ROUNDS), so the repair turn
// shares them: a question that used all 5 for tool calls and the answer cannot be repaired, and says so.
import type { Card } from '../cards/card.types'
import { toCheckerCard } from '../cards/project'
import { checkAnswer, policy, type CheckReport, type FactCard } from '../honesty/checker'
import { queryResultToCheckerCard } from '../honesty/queryCard'
import { findUngroundedNumbers, type UngroundedNumber } from '../grounding'
import type { QueryResult } from '../queryBuilder/types'
import { BudgetMeter, MAX_TOOL_CALLS, fitHistory, fitToolResult, formatBudgetLine, type BudgetLine, type HistoryTurn } from './budget'
import type { CardStore } from './cardStore'
import type { Dispatcher } from './dispatcher'
import { preloadPageCards, type OnScreenSpec, type PageContext } from './preload'
import type { ChatMessage, ModelClient, ModelReply, ToolCall, ToolResult } from './types'

export const MAX_ROUNDS = 5

export interface LoopDeps {
  model: ModelClient
  dispatcher: Dispatcher
  store: CardStore
  /** The Worker's system prompt and tool schemas: used for the budget meter only (the Worker injects them). */
  system: string
  toolsJson: string
  /** Registry specs for the pre-load (spec.onScreen). */
  specs?: readonly OnScreenSpec[]
  /** Swappable for tests. */
  check?: typeof checkAnswer
}

export interface AskOptions {
  page?: PageContext | null
  history?: HistoryTurn[]
}

export interface Note {
  kind: 'rule' | 'ungrounded' | 'loop'
  code: string
  detail: string
}

export interface ToolLogEntry {
  name: string
  arguments: unknown
  status: ToolResult['status']
  reason?: string
}

export interface AskResult {
  status: 'answered' | 'no_answer'
  answer: string
  toolsCalled: ToolLogEntry[]
  cardsCited: string[]
  onScreenIds: string[]
  /** Failures left on the returned answer (empty = it passed the checker and the grounding check). */
  notes: Note[]
  repaired: boolean
  repairSkipped: boolean
  /** When a repair turn ran: what the first draft failed on (the evidence the repair had something to fix). */
  firstDraft: { answer: string; failed: string[]; ungrounded: string[] } | null
  check: CheckReport
  ungrounded: UngroundedNumber[]
  budget: BudgetLine
  budgetText: string
  rounds: number
  links: string[]
  chartIds: string[]
  /** The tool results whose numbers the model could quote (query_data, charts); the render-time grounding check uses the same set. */
  visibleResults: unknown[]
}

const NO_ANSWER = 'I could not finish this question within the tool limit, so I have no answer to give from the data.'
export const LIMIT_NOTE = 'Tool-call limit reached (4). Do not call more tools: answer from what you have, or say you have no data.'
const RETRY_HINT = 'You may retry once with different arguments; otherwise say you have no data. Do not state a number you did not receive.'

function wireCalls(calls: ToolCall[]): unknown {
  return calls.map((c) => ({ id: c.id, type: 'function', function: { name: c.name, arguments: JSON.stringify(c.arguments ?? {}) } }))
}

function charsOf(messages: ChatMessage[], extra: number): number {
  return messages.reduce((a, m) => a + m.content.length + (m.tool_calls ? JSON.stringify(m.tool_calls).length : 0), extra)
}

export function repairMessage(report: CheckReport, ungrounded: UngroundedNumber[]): string {
  const lines: string[] = ['Your draft did not pass the checks. Rewrite the answer once, fixing exactly these points. Do not call tools.']
  for (const r of report.results) {
    if (r.verdict !== 'fail') continue
    const rule = policy.rules.find((x) => x.code === r.code)
    if (r.missing_wording.length) lines.push(`- ${r.code}: missing wording. ${rule?.required_wording.description ?? ''}`.trim())
    for (const h of r.forbidden_hits) lines.push(`- ${r.code}: remove "${h.text}". ${rule?.forbidden_claim.description ?? ''}`.trim())
  }
  if (ungrounded.length) {
    lines.push(`- Numbers with no source (no card id or query result): ${ungrounded.map((u) => u.text).join(', ')}. Remove them or replace them with a number from a card or result.`)
  }
  return lines.join('\n')
}

export async function ask(question: string, deps: LoopDeps, opts: AskOptions = {}): Promise<AskResult> {
  const { model, dispatcher, store } = deps
  const check = deps.check ?? checkAnswer
  const meter = new BudgetMeter()
  meter.setStatic(deps.system, deps.toolsJson)

  const pre = preloadPageCards(store, opts.page, deps.specs ?? [])
  meter.setPageContext(pre.text)
  const hist = fitHistory(opts.history ?? [])
  meter.setHistory(hist.tokens)

  const messages: ChatMessage[] = []
  for (const t of hist.turns) {
    messages.push({ role: 'user', content: t.question }, { role: 'assistant', content: t.answer })
  }
  messages.push({ role: 'user', content: pre.text ? `${pre.text}\n\nQuestion: ${question}` : question })

  const link0 = dispatcher.session.links.length
  const chart0 = dispatcher.session.chartIds.length
  const toolsCalled: ToolLogEntry[] = []
  const visible: unknown[] = [] // tool results whose numbers the model may quote (query_data, charts)
  const staticChars = deps.system.length + deps.toolsJson.length
  let rounds = 0
  let calls = 0
  let draft: string | null = null
  let firstDraft: AskResult['firstDraft'] = null

  const modelRound = async (): Promise<ModelReply> => {
    const reply = await model.chat({ messages, round: rounds + 1 })
    rounds++
    meter.recordRound(reply.usage, charsOf(messages, staticChars), (reply.content ?? '') + JSON.stringify(reply.tool_calls))
    return reply
  }

  while (rounds < MAX_ROUNDS) {
    const reply = await modelRound()
    if (reply.tool_calls.length === 0) {
      draft = reply.content ?? ''
      break
    }
    messages.push({ role: 'assistant', content: reply.content ?? '', tool_calls: wireCalls(reply.tool_calls) })
    for (const call of reply.tool_calls) {
      let result: ToolResult
      if (calls >= MAX_TOOL_CALLS) {
        result = { status: 'error', reason: 'tool_call_limit', allowed: LIMIT_NOTE }
      } else {
        calls++
        result = await dispatcher.dispatch(call)
        if (result.status !== 'ok' && result.reason !== 'held') result = { ...result, retry_hint: RETRY_HINT }
        if (calls === MAX_TOOL_CALLS) result = { ...result, tool_budget: LIMIT_NOTE }
      }
      const fitted = fitToolResult(result)
      meter.addToolResult(fitted)
      toolsCalled.push({ name: call.name, arguments: call.arguments, status: result.status, ...(result.reason ? { reason: String(result.reason) } : {}) })
      if (result.status === 'ok' && ['query_data', 'compare_lap_times', 'make_chart'].includes(call.name)) visible.push(fitted.result)
      messages.push({ role: 'tool', content: fitted.text, tool_call_id: call.id })
    }
  }

  const session = dispatcher.session
  const evaluate = (answer: string) => {
    const cardMap = new Map<string, Card>()
    for (const c of pre.cards) cardMap.set(c.id, c)
    for (const c of session.cards.values()) cardMap.set(c.id, c)
    const cards = [...cardMap.values()]
    const checkerCards: FactCard[] = cards.map(toCheckerCard)
    for (const r of session.queryResults) checkerCards.push(queryResultToCheckerCard(r as QueryResult))
    const report = check({ question, answer, cards: checkerCards })
    const ungrounded = findUngroundedNumbers(answer, {
      cards,
      results: visible,
      texts: [question, ...hist.turns.map((t) => t.question)],
    })
    return { report, ungrounded, cards }
  }
  const notesOf = (report: CheckReport, ungrounded: UngroundedNumber[]): Note[] => [
    ...report.results
      .filter((r) => r.verdict === 'fail')
      .map((r) => ({
        kind: 'rule' as const,
        code: r.code,
        detail: [r.missing_wording.length ? `missing wording (${r.missing_wording.length})` : '', ...r.forbidden_hits.map((h) => `forbidden "${h.text}"`)].filter(Boolean).join('; '),
      })),
    ...ungrounded.map((u) => ({ kind: 'ungrounded' as const, code: 'UNGROUNDED_NUMBER', detail: `${u.text} in "${u.context}"` })),
  ]

  const finish = (answer: string, status: AskResult['status'], notes: Note[], ev: ReturnType<typeof evaluate>, repaired: boolean, repairSkipped: boolean): AskResult => {
    const budget = meter.line()
    return {
      status,
      answer,
      toolsCalled,
      cardsCited: ev.cards.map((c) => c.id).filter((id) => answer.includes(id)),
      onScreenIds: pre.ids,
      notes,
      repaired,
      repairSkipped,
      firstDraft,
      check: ev.report,
      ungrounded: ev.ungrounded,
      budget,
      budgetText: formatBudgetLine(budget),
      rounds: budget.rounds,
      links: session.links.slice(link0),
      chartIds: session.chartIds.slice(chart0),
      visibleResults: visible,
    }
  }

  if (draft === null) {
    const ev = evaluate(NO_ANSWER)
    return finish(NO_ANSWER, 'no_answer', [{ kind: 'loop', code: 'ROUND_LIMIT', detail: `the model kept asking for tools through round ${MAX_ROUNDS}` }], ev, false, false)
  }

  let ev = evaluate(draft)
  if (ev.report.ok && ev.ungrounded.length === 0) return finish(draft, 'answered', [], ev, false, false)

  // One repair turn, if the ticket has a round left.
  if (rounds >= MAX_ROUNDS) {
    return finish(draft, 'answered', [...notesOf(ev.report, ev.ungrounded), { kind: 'loop', code: 'REPAIR_SKIPPED', detail: 'all 5 rounds were used before the answer' }], ev, false, true)
  }
  firstDraft = { answer: draft, failed: ev.report.failed, ungrounded: ev.ungrounded.map((u) => u.text) }
  messages.push({ role: 'assistant', content: draft }, { role: 'user', content: repairMessage(ev.report, ev.ungrounded) })
  const second = await modelRound()
  if (second.tool_calls.length > 0 || !second.content) {
    return finish(draft, 'answered', [...notesOf(ev.report, ev.ungrounded), { kind: 'loop', code: 'REPAIR_FAILED', detail: 'the repair turn returned no answer text' }], ev, true, false)
  }
  draft = second.content
  ev = evaluate(draft)
  return finish(draft, 'answered', notesOf(ev.report, ev.ungrounded), ev, true, false)
}
