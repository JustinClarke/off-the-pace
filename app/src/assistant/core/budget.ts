// AX-10 budget meter (design 2.6). Counts tokens per slot, truncates a tool result to its slot and
// emits one log line per question: slot -> tokens, total, rounds, neurons.
//
// Token source: usage.prompt_tokens / completion_tokens from the model reply when present, else
// chars/4 (marked estimated). The slot sizes are the proposed ones from the spec; AX-13 measures them.
import type { ModelUsage } from './types'

/** Proposed slots (design 2.6). Peak 13,100; the eval bar is 18,000 (AX-13). */
export const SLOTS = {
  instructions: 1200,
  tools: 1400,
  catalogue: 600,
  page_context: 600,
  history: 2000,
  tool_results: 4800,
  output: 2500,
} as const
export type SlotName = keyof typeof SLOTS
export const SLOT_NAMES = Object.keys(SLOTS) as SlotName[]
export const PEAK_TOKENS = SLOT_NAMES.reduce((a, k) => a + SLOTS[k], 0) // 13,100
/** One tool result may use at most this many tokens (4 x 1,200 = the tool_results slot). */
export const TOOL_RESULT_SLOT = 1200
export const MAX_TOOL_CALLS = 4
/** Last two turns are replayed as history. */
export const HISTORY_TURNS = 2

// Workers AI rates for gpt-oss-20b: worker/src/config.ts:16-17 (a test keeps these in step).
export const NEURONS_PER_M_INPUT = 18182
export const NEURONS_PER_M_OUTPUT = 27273

/** chars/4: the estimator the spec names. */
export const tokensOf = (text: string): number => Math.ceil(text.length / 4)

/** Same formula as worker/src/handler.ts:79 neuronsFor. */
export function neuronsFor(usage: ModelUsage | null | undefined): number {
  const i = Number(usage?.prompt_tokens ?? 0)
  const o = Number(usage?.completion_tokens ?? 0)
  return Math.ceil((i * NEURONS_PER_M_INPUT + o * NEURONS_PER_M_OUTPUT) / 1e6)
}

/** Split the Worker's system prompt into the instruction part and the query-catalogue part. */
export function splitSystemPrompt(system: string): { instructions: string; catalogue: string } {
  const at = system.indexOf('Data views for query_data')
  return at < 0 ? { instructions: system, catalogue: '' } : { instructions: system.slice(0, at), catalogue: system.slice(at) }
}

export interface FittedResult {
  result: Record<string, unknown>
  text: string
  tokens: number
  rows_dropped: number
  truncated: boolean
}

/** Array keys a tool result may carry rows in; the longest is trimmed first. */
const ROW_KEYS = ['rows', 'cards', 'steps', 'items']

/**
 * Truncate a tool result (a JSON object) to `limit` tokens. Trailing rows/cards are dropped and
 * `rows_dropped` records how many (added to any count the tool already set). A result with no row
 * list that is still too long is replaced by an explicit refusal, never cut mid-JSON.
 */
export function fitToolResult(result: Record<string, unknown>, limit = TOOL_RESULT_SLOT): FittedResult {
  let cur: Record<string, unknown> = { ...result }
  let text = JSON.stringify(cur)
  if (tokensOf(text) <= limit) return { result: cur, text, tokens: tokensOf(text), rows_dropped: 0, truncated: false }
  const key = ROW_KEYS.filter((k) => Array.isArray(cur[k])).sort((a, b) => (cur[b] as unknown[]).length - (cur[a] as unknown[]).length)[0]
  let dropped = 0
  if (key) {
    const rows = [...(cur[key] as unknown[])]
    const prior = typeof cur.rows_dropped === 'number' ? cur.rows_dropped : 0
    while (rows.length > 0) {
      rows.pop()
      dropped++
      cur = { ...result, [key]: rows, rows_dropped: prior + dropped, truncated: true }
      text = JSON.stringify(cur)
      if (tokensOf(text) <= limit) return { result: cur, text, tokens: tokensOf(text), rows_dropped: dropped, truncated: true }
    }
  }
  cur = { status: 'error', reason: 'result_too_large', rows_dropped: dropped, truncated: true }
  text = JSON.stringify(cur)
  return { result: cur, text, tokens: tokensOf(text), rows_dropped: dropped, truncated: true }
}

export interface HistoryTurn {
  question: string
  /** The final answer, with cards cited by id (tool results are never replayed). */
  answer: string
}

/** Keep the last two turns, then drop the oldest until the history slot fits. */
export function fitHistory(turns: HistoryTurn[], limit: number = SLOTS.history): { turns: HistoryTurn[]; tokens: number; dropped: number } {
  let kept = turns.slice(-HISTORY_TURNS)
  const size = (t: HistoryTurn[]) => t.reduce((a, x) => a + tokensOf(x.question) + tokensOf(x.answer), 0)
  while (kept.length > 0 && size(kept) > limit) kept = kept.slice(1)
  return { turns: kept, tokens: size(kept), dropped: turns.length - kept.length }
}

export interface BudgetLine {
  slots: Record<SlotName, number>
  /** Sum of the slots: the largest context any one round can carry. */
  peak_context: number
  /** Prompt + completion tokens summed over the rounds (what neurons are charged on). */
  total: number
  rounds: number
  neurons: number
  /** true when any figure comes from chars/4 rather than usage. */
  estimated: boolean
  over_slot: SlotName[]
  rows_dropped: number
}

/** Per-question meter. */
export class BudgetMeter {
  private slots: Record<SlotName, number> = { instructions: 0, tools: 0, catalogue: 0, page_context: 0, history: 0, tool_results: 0, output: 0 }
  private promptTotal = 0
  private completionTotal = 0
  private rounds = 0
  private estimated = false
  private rowsDropped = 0

  setStatic(system: string, toolsJson: string): void {
    const s = splitSystemPrompt(system)
    this.slots.instructions = tokensOf(s.instructions)
    this.slots.catalogue = tokensOf(s.catalogue)
    this.slots.tools = tokensOf(toolsJson)
  }

  setPageContext(text: string): void {
    this.slots.page_context = tokensOf(text)
  }

  setHistory(tokens: number): void {
    this.slots.history = tokens
  }

  addToolResult(f: FittedResult): void {
    this.slots.tool_results += f.tokens
    this.rowsDropped += f.rows_dropped
  }

  /** One model round. `promptChars` and `outputText` feed the estimate when usage is missing. */
  recordRound(usage: ModelUsage | null | undefined, promptChars: number, outputText: string): void {
    this.rounds++
    const out = usage?.completion_tokens ?? tokensOf(outputText)
    const inp = usage?.prompt_tokens ?? Math.ceil(promptChars / 4)
    if (usage?.completion_tokens === undefined || usage?.prompt_tokens === undefined) this.estimated = true
    this.slots.output += out
    this.promptTotal += inp
    this.completionTotal += out
  }

  line(): BudgetLine {
    const slots = { ...this.slots }
    return {
      slots,
      peak_context: SLOT_NAMES.reduce((a, k) => a + slots[k], 0),
      total: this.promptTotal + this.completionTotal,
      rounds: this.rounds,
      neurons: neuronsFor({ prompt_tokens: this.promptTotal, completion_tokens: this.completionTotal }),
      estimated: this.estimated,
      over_slot: SLOT_NAMES.filter((k) => slots[k] > SLOTS[k]),
      rows_dropped: this.rowsDropped,
    }
  }
}

/** The one log line per question: slot -> tokens, total, rounds, neurons. */
export function formatBudgetLine(b: BudgetLine): string {
  const slots = SLOT_NAMES.map((k) => `${k}=${b.slots[k]}/${SLOTS[k]}`).join(' ')
  return `budget ${slots} | peak_context=${b.peak_context}/${PEAK_TOKENS} total=${b.total} rounds=${b.rounds} neurons=${b.neurons}${b.estimated ? ' (estimated chars/4)' : ''}${b.over_slot.length ? ` OVER:${b.over_slot.join(',')}` : ''}`
}
