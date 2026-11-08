// AX-13 eval runner: each question x repeats through the real AX-10 loop (dispatcher, checker, grounding,
// budget), recording what the grader needs (RunObservation), then grading. The model is injected: the
// STUB (eval/stubModel.ts) or an endpoint client (the Worker v2 contract, or an OpenAI-compatible one).
import { ask, type LoopDeps } from '../core/loop'
import { fitToolResult } from '../core/budget'
import { preloadPageCards } from '../core/preload'
import { EndpointError } from '../core/modelClient'
import type { Dispatcher } from '../core/dispatcher'
import type { CardStore } from '../core/cardStore'
import type { ModelClient, ToolResult } from '../core/types'
import type { QueryResultLike } from '../honesty/queryCard'
import { grade, type CardTable, type GradeResult, type RunObservation, type UsageRound } from './grade'
import type { Question } from './questions'

const VISIBLE = new Set(['query_data', 'compare_lap_times', 'make_chart'])

export interface RunDeps {
  /** A fresh LoopDeps (own dispatcher) per run, over `model`. */
  loopDeps(model: ModelClient): LoopDeps
  store: CardStore
}

function reasoningOf(raw: unknown): number | undefined {
  const u = raw as Record<string, unknown> | null | undefined
  if (!u || typeof u !== 'object') return undefined
  const d = (u.completion_tokens_details ?? u.output_tokens_details) as Record<string, unknown> | undefined
  const v = d?.reasoning_tokens ?? u.reasoning_tokens
  return typeof v === 'number' ? v : undefined
}

/** Run one question once and record the observation. Endpoint errors are recorded, never thrown. */
export async function runOnce(q: Question, repeat: number, model: ModelClient, deps: RunDeps, mode: string): Promise<RunObservation> {
  const usage: UsageRound[] = []
  const logged: ModelClient = {
    async chat(req) {
      const r = await model.chat(req)
      usage.push({
        prompt_tokens: r.usage?.prompt_tokens,
        completion_tokens: r.usage?.completion_tokens,
        reasoning_tokens: reasoningOf(r.raw_usage),
        visible_chars: (r.content ?? '').length + (r.tool_calls.length ? JSON.stringify(r.tool_calls).length : 0),
        ...(r.raw_usage ? { raw: r.raw_usage } : {}),
      })
      return r
    },
  }
  const base = deps.loopDeps(logged)
  const inner: Dispatcher = base.dispatcher
  const results: unknown[] = []
  const dispatcher: Dispatcher = {
    session: inner.session,
    async dispatch(call) {
      const r: ToolResult = await inner.dispatch(call)
      if (VISIBLE.has(call.name) && r.status === 'ok') results.push(fitToolResult(r).result)
      return r
    },
  }
  const loopDeps: LoopDeps = { ...base, model: logged, dispatcher }
  const pre = preloadPageCards(deps.store, q.page ?? null, loopDeps.specs ?? [])
  try {
    const r = await ask(q.text, loopDeps, { page: q.page ?? null })
    return {
      question_id: q.id,
      repeat,
      mode,
      status: r.status,
      answer: r.answer,
      tools: r.toolsCalled.map((t) => ({ name: t.name, arguments: t.arguments, status: t.status, ...(t.reason ? { reason: t.reason } : {}) })),
      cards_received: [...new Set([...pre.ids, ...inner.session.cards.keys()])],
      results,
      query_results: inner.session.queryResults as unknown as QueryResultLike[],
      budget: { total: r.budget.total, peak_context: r.budget.peak_context, rounds: r.budget.rounds, neurons: r.budget.neurons, estimated: r.budget.estimated, slots: { ...r.budget.slots } },
      rounds: r.rounds,
      repaired: r.repaired,
      repair_skipped: r.repairSkipped,
      first_draft_failed: [...(r.firstDraft?.failed ?? []), ...(r.firstDraft?.ungrounded ?? []).map((u) => `number ${u}`)],
      loop_notes: r.notes.map((n) => n.code),
      usage_rounds: usage,
    }
  } catch (e) {
    const msg = e instanceof EndpointError ? `${e.status} ${e.message}` : e instanceof Error ? e.message : String(e)
    return {
      question_id: q.id,
      repeat,
      mode,
      status: 'error',
      error: msg.slice(0, 300),
      answer: '',
      tools: [],
      cards_received: [],
      results: [],
      query_results: [],
      budget: { total: 0, peak_context: 0, rounds: usage.length, neurons: 0, estimated: true },
      rounds: usage.length,
      repaired: false,
      repair_skipped: false,
      first_draft_failed: [],
      loop_notes: [],
      usage_rounds: usage,
    }
  }
}

export interface EvalOptions {
  repeats: number
  mode: string
  /** The model for one run (stub: a fresh scripted model per run; endpoint: a shared client). */
  modelFor(q: Question, repeat: number): ModelClient
  deps: RunDeps
  table: CardTable
  /** Runs already done (resume): skipped. */
  done?: ReadonlySet<string>
  onRun?(obs: RunObservation, g: GradeResult): void
}

export const runKey = (id: string, repeat: number) => `${id}#${repeat}`

export async function runEval(questions: readonly Question[], o: EvalOptions): Promise<{ observations: RunObservation[]; grades: GradeResult[] }> {
  const observations: RunObservation[] = []
  const grades: GradeResult[] = []
  for (let rep = 1; rep <= o.repeats; rep++) {
    for (const q of questions) {
      if (o.done?.has(runKey(q.id, rep))) continue
      const obs = await runOnce(q, rep, o.modelFor(q, rep), o.deps, o.mode)
      const g = grade(q, obs, o.table)
      observations.push(obs)
      grades.push(g)
      o.onRun?.(obs, g)
    }
  }
  return { observations, grades }
}
