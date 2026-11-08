// AX-10 headless CLI logic (the launcher is app/scripts/assistant-cli.mjs). Runs questions through the
// real loop, dispatcher, checker and grounding check, against a model that is either a scripted stub
// (deterministic, no network: tests and the evidence runs) or an HTTP endpoint (local Ollama, or the
// AX-12 preview Worker). It prints, for each question: answer, tools called, cards cited, checker
// report and the budget line.
import { ask, type AskOptions, type AskResult, type LoopDeps } from './loop'
import type { ModelClient } from './types'
import type { ScriptEntry } from './modelClient'
import type { PageContext } from './preload'
import type { Dispatcher } from './dispatcher'

export interface QuestionSpec {
  id: string
  /** The class of question, for the evidence table. */
  kind: string
  question: string
  page?: PageContext
  /** Stub mode only: the scripted rounds. */
  script?: ScriptEntry[]
}

export interface RunRecord {
  id: string
  kind: string
  question: string
  page: PageContext | null
  status: AskResult['status']
  answer: string
  tools: { name: string; arguments: unknown; status: string; reason?: string }[]
  cards_cited: string[]
  on_screen: string[]
  checker: { ok: boolean; failed: string[]; pending: string[]; fired: { code: string; verdict: string }[] }
  grounding: { ungrounded: string[] }
  notes: { kind: string; code: string; detail: string }[]
  repaired: boolean
  first_draft: AskResult['firstDraft']
  rounds: number
  links: string[]
  chart_ids: string[]
  budget: AskResult['budget']
  budget_line: string
}

export function toRecord(spec: QuestionSpec, r: AskResult): RunRecord {
  return {
    id: spec.id,
    kind: spec.kind,
    question: spec.question,
    page: spec.page ?? null,
    status: r.status,
    answer: r.answer,
    tools: r.toolsCalled.map((t) => ({ name: t.name, arguments: t.arguments, status: t.status, ...(t.reason ? { reason: t.reason } : {}) })),
    cards_cited: r.cardsCited,
    on_screen: r.onScreenIds,
    checker: {
      ok: r.check.ok,
      failed: r.check.failed,
      pending: r.check.pending,
      fired: r.check.results.filter((x) => x.verdict !== 'not_fired').map((x) => ({ code: x.code, verdict: x.verdict })),
    },
    grounding: { ungrounded: r.ungrounded.map((u) => u.text) },
    notes: r.notes,
    repaired: r.repaired,
    first_draft: r.firstDraft,
    rounds: r.rounds,
    links: r.links,
    chart_ids: r.chartIds,
    budget: r.budget,
    budget_line: r.budgetText,
  }
}

export function formatRecord(rec: RunRecord): string {
  const tools = rec.tools.length ? rec.tools.map((t) => `${t.name}(${JSON.stringify(t.arguments)}) -> ${t.status}${t.reason ? ` [${t.reason}]` : ''}`).join('\n    ') : '(none)'
  return [
    `Q [${rec.kind}] ${rec.question}${rec.page ? `   (page ${rec.page.route} ${JSON.stringify(rec.page.params)})` : ''}`,
    `  answer: ${rec.answer}`,
    `  tools:  ${tools}`,
    `  cards cited: ${rec.cards_cited.join(', ') || '(none)'}${rec.on_screen.length ? `   on-screen pre-load: ${rec.on_screen.join(', ')}` : ''}`,
    `  checker: ${rec.checker.ok ? 'pass' : `FAIL ${rec.checker.failed.join(',')}`}${rec.checker.pending.length ? ` pending ${rec.checker.pending.join(',')}` : ''}   fired: ${rec.checker.fired.map((f) => `${f.code}:${f.verdict}`).join(' ') || '(none)'}`,
    `  grounding: ${rec.grounding.ungrounded.length ? `UNGROUNDED ${rec.grounding.ungrounded.join(', ')}` : 'ok'}${rec.repaired ? `   (one repair turn used; first draft failed ${[...(rec.first_draft?.failed ?? []), ...(rec.first_draft?.ungrounded ?? []).map((u) => `number ${u}`)].join(',')})` : ''}${rec.notes.length ? `   notes: ${rec.notes.map((n) => `${n.code}`).join(',')}` : ''}`,
    `  ${rec.budget_line}`,
  ].join('\n')
}

export interface RunOptions {
  /** Build the model for one question (stub: from spec.script; real: one shared HTTP client). */
  modelFor(spec: QuestionSpec): ModelClient
  /** A loop deps factory; a fresh dispatcher per question keeps runs independent. */
  depsFor(model: ModelClient): LoopDeps
  onRecord?(rec: RunRecord): void
}

export async function runQuestions(specs: QuestionSpec[], o: RunOptions): Promise<RunRecord[]> {
  const out: RunRecord[] = []
  for (const spec of specs) {
    const opts: AskOptions = { page: spec.page ?? null }
    const result = await ask(spec.question, o.depsFor(o.modelFor(spec)), opts)
    const rec = toRecord(spec, result)
    out.push(rec)
    o.onRecord?.(rec)
  }
  return out
}

/** Run one tool directly through a dispatcher (CLI --call): the explain_page evidence. */
export async function callTool(d: Dispatcher, name: string, args: unknown): Promise<unknown> {
  return d.dispatch({ id: 'cli', name, arguments: args })
}
