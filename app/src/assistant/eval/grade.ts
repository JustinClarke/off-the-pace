// AX-13 grader. Rule-based, per answer (one run of one question). Reuses the AX-10 grounding check
// (findUngroundedNumbers) and the AI-02 checker (checkAnswer) as they are: nothing here forks them.
//
// Checks per run (true = pass, false = fail, null = not applicable to this question):
//   grounded         every number in the answer matches a card the model received or a query/chart result
//   expected_value   every quote:true card's value (read from the card table now, never typed in the
//                    question file) is stated in the answer
//   honesty          checkAnswer passes: required wording present, no forbidden claim, for every card received
//   rules_fired      every rules_should_fire code fired (the right cards were fetched)
//   refusal          refuse/hedge questions: refusal or hedge wording, every held_reason key, no must_not
//                    claim; refuse also: no number at all (numbers the user typed are allowed)
//   must_not         no must_not pattern in the answer (every question)
//   right_tool       the first expected tool was called (and the expected bundle, when one is named);
//                    a question with no expected tool passes only when no tool was called
//   all_tools        every expected tool was called (reported, not part of the bar)
//   budget           tokens for the run (prompt + completion summed over its rounds) <= 18,000
//   limits           no call refused by the 4-call limit, no ROUND_LIMIT, rounds <= 5
//   answered         the run ended with an answer (no endpoint error, no round-limit stop)
import type { Card } from '../cards/card.types'
import { toCheckerCard } from '../cards/project'
import { checkAnswer, type CheckReport, type FactCard } from '../honesty/checker'
import { queryResultToCheckerCard, type QueryResultLike } from '../honesty/queryCard'
import { extractAnswerNumbers, findUngroundedNumbers } from '../grounding'
import { playbook } from '../prompt/bundles'
import { MAX_TOOL_CALLS } from '../core/budget'
import { MAX_ROUNDS } from '../core/loop'
import type { ExpectedCard, Question } from './questions'

/** AI-07 / AX-13 Decided: no run over 18,000 tokens. */
export const RUN_TOKEN_LIMIT = 18000

/** Held / refusal reasons a refuse or hedge answer must give, by key (all keys of a question must match). */
export const HELD_REASON_PATTERNS: Record<string, RegExp> = {
  wake_calibration: /\bwake[- ]calibration\b|\bdirty[- ]air (work|calibration)\b/i,
  traffic_remeasure: /\bre-?measur|\bwake[- ]calibration\b|\bdirty[- ]air calibration\b/i,
  ml_redo: /\b(ML|model) redo\b/i,
  reproduction_rate: /\breproduc|\babout (a|one) third\b|\bone (in|time in) three\b|\b33\.9 ?%/i,
  suppressed: /\bno reliable (gap|value|rating|number)\b/i,
  unrated: /\bnot rated\b|\bno dry (paired )?laps\b|\bwet race\b/i,
  no_2026: /\bno 2026\b|\b2018[-– to]+2025\b|\bnot (yet )?(been )?ingested\b/i,
  pooled_only: /\bpooled\b[\s\S]*\bno (reliable |measurable )?difference between (circuits|tracks)\b|\bno (reliable |measurable )?difference between (circuits|tracks)\b[\s\S]*\bpooled\b/i,
  different_measures: /\bdifferent (skill )?(measures|definitions|metrics)\b|\bnot (on )?(one|a single|the same) scale\b/i,
  shared_inputs: /\bnot independent\b|\bshare (the same |their )?(inputs?|data|laps|rating)\b|\bsame (underlying )?(laps|data|rating|inputs?)\b/i,
  in_sample: /\bin[- ]sample\b|\bvalidation fold\b/i,
  grey_cell: /\b(clean|free)[- ]air\b[\s\S]{0,120}\b(missing|no|absent) (telemetry|gap data)\b|\b(missing|no|absent) (telemetry|gap data)\b[\s\S]{0,120}\b(clean|free)[- ]air\b/i,
  different_eras: /\bdifferent (regulation |fit )?eras\b|\bnot comparable across eras\b|\bacross eras\b|\bwithin (one|an|the same) era\b/i,
  link_only: /\bsimulator\b/i,
}

/** A refuse answer says it is not giving the figure. */
export const REFUSAL_MARKER =
  /\b(held|not (yet )?(available|published|measured|rated|computed)|unavailable|no (reliable )?(data|value|gap|figure|number|card|estimate)|cannot|can't|can not|do not|don't|will not|won't|is not (a|an)|not a verdict|only a link)\b/i

export type CheckName = 'grounded' | 'expected_value' | 'honesty' | 'rules_fired' | 'refusal' | 'must_not' | 'right_tool' | 'all_tools' | 'budget' | 'limits' | 'answered'
export const CHECK_NAMES: readonly CheckName[] = ['grounded', 'expected_value', 'honesty', 'rules_fired', 'refusal', 'must_not', 'right_tool', 'all_tools', 'budget', 'limits', 'answered']

export interface ToolEntry {
  name: string
  arguments: unknown
  status: string
  reason?: string
}

export interface UsageRound {
  prompt_tokens?: number
  completion_tokens?: number
  /** From the endpoint's usage when it reports one (completion_tokens_details.reasoning_tokens or similar). */
  reasoning_tokens?: number
  /** Characters of the visible reply (content + tool calls): completion_tokens far above chars/4 of this means hidden (reasoning) tokens are billed as output. */
  visible_chars?: number
  raw?: unknown
}

/** What one run of one question produced: everything the grader needs, nothing it must recompute from the model. */
export interface RunObservation {
  question_id: string
  repeat: number
  mode: string
  status: 'answered' | 'no_answer' | 'error'
  error?: string
  answer: string
  tools: ToolEntry[]
  /** Ids of every card the model received: page pre-load and get_fact_cards results. Resolved from the card table at grade time. */
  cards_received: string[]
  /** query_data / compare_lap_times / make_chart ok results, as fitted to the tool slot (the numbers the model saw). */
  results: unknown[]
  /** Query results the checker sees as cards (COMPUTED_NOT_CARD_WORDING). */
  query_results: QueryResultLike[]
  budget: { total: number; peak_context: number; rounds: number; neurons: number; estimated: boolean; slots?: Record<string, number> }
  rounds: number
  repaired: boolean
  repair_skipped: boolean
  first_draft_failed: string[]
  loop_notes: string[]
  usage_rounds: UsageRound[]
}

export interface CardTable {
  byId(id: string): Card | undefined
  ofKind(kind: string): readonly Card[]
  readonly size: number
}

export function createCardTable(cards: readonly Card[]): CardTable {
  const ids = new Map<string, Card>()
  const kinds = new Map<string, Card[]>()
  for (const c of cards) {
    ids.set(c.id, c)
    let k = kinds.get(c.kind)
    if (!k) kinds.set(c.kind, (k = []))
    k.push(c)
  }
  return { byId: (id) => ids.get(id), ofKind: (kind) => kinds.get(kind) ?? [], size: ids.size }
}

export const PENDING_KINDS: readonly string[] = Object.keys((playbook as unknown as { pending_kinds?: Record<string, unknown> }).pending_kinds ?? {})

/** Cards of the table that an expected-card entry names. A pending kind (no registry entry yet) resolves to []. */
export function resolveExpected(table: CardTable, e: ExpectedCard): Card[] {
  return table.ofKind(e.kind).filter((c) => {
    for (const [k, v] of Object.entries(e.scope)) {
      const have = (c.scope as unknown as Record<string, unknown>)[k]
      if (v === 'all') {
        if (have !== null && have !== undefined) return false
      } else if (have !== v) return false
    }
    return !e.id_suffix || c.id.endsWith(`:${e.id_suffix}`)
  })
}

export interface CheckResult {
  pass: boolean | null
  detail: string
}

export interface GradeResult {
  question_id: string
  repeat: number
  checks: Record<CheckName, CheckResult>
  /** Every applicable check passed. */
  all_pass: boolean
  failures: string[]
  checker: { failed: string[]; fired: string[] }
}

const na = (detail = 'n/a'): CheckResult => ({ pass: null, detail })
const ok = (detail = ''): CheckResult => ({ pass: true, detail })
const bad = (detail: string): CheckResult => ({ pass: false, detail })

function numbersStated(answer: string, card: Card): boolean {
  if (typeof card.value !== 'number') return true
  const only = [{ id: card.id, metric: card.metric, value: card.value } as FactCard]
  const all = extractAnswerNumbers(answer)
  if (all.length === 0) return false
  return findUngroundedNumbers(answer, { cards: only }).length < all.length
}

export function checkerCardsFor(obs: RunObservation, table: CardTable): { cards: Card[]; checker: FactCard[]; unknown: string[] } {
  const cards: Card[] = []
  const unknown: string[] = []
  for (const id of new Set(obs.cards_received)) {
    const c = table.byId(id)
    if (c) cards.push(c)
    else unknown.push(id)
  }
  const checker: FactCard[] = cards.map(toCheckerCard)
  for (const r of obs.query_results) checker.push(queryResultToCheckerCard(r))
  return { cards, checker, unknown }
}

/** Grade one run. `table` is the published card table the run used (expected values are read from it now). */
export function grade(q: Question, obs: RunObservation, table: CardTable): GradeResult {
  const answer = obs.answer ?? ''
  const errored = obs.status === 'error'
  const { cards, checker, unknown } = checkerCardsFor(obs, table)

  // honesty (the same input the loop gives the checker)
  const report: CheckReport = checkAnswer({ question: q.text, answer, cards: checker })
  const fired = report.results.filter((r) => r.verdict !== 'not_fired').map((r) => r.code)

  const checks = {} as Record<CheckName, CheckResult>

  checks.answered = errored ? bad(`endpoint error: ${obs.error ?? ''}`) : obs.status === 'no_answer' ? bad('no answer (round limit)') : ok()

  // grounded
  const ungrounded = findUngroundedNumbers(answer, { cards, results: obs.results, texts: [q.text] })
  checks.grounded = errored
    ? na('errored run')
    : unknown.length
      ? bad(`cards not in the table: ${unknown.slice(0, 3).join(', ')}`)
      : ungrounded.length
        ? bad(`ungrounded: ${ungrounded.map((u) => u.text).join(', ')}`)
        : ok()

  // expected_value
  const quotes = q.expected_cards.filter((e) => e.quote)
  if (errored || q.expect === 'refuse' || quotes.length === 0) checks.expected_value = na()
  else {
    const missing: string[] = []
    for (const e of quotes) {
      const hits = resolveExpected(table, e)
      if (hits.length === 0) {
        missing.push(`${e.kind} ${JSON.stringify(e.scope)} not in the card table`)
        continue
      }
      for (const c of hits) if (c.value !== null && !numbersStated(answer, c)) missing.push(`${c.id} value not stated`)
    }
    checks.expected_value = missing.length ? bad(missing.join('; ')) : ok()
  }

  checks.honesty = errored ? na('errored run') : report.ok ? ok() : bad(`failed ${report.failed.join(',')}`)

  const notFired = q.rules_should_fire.filter((c) => !fired.includes(c))
  checks.rules_fired = errored || q.rules_should_fire.length === 0 ? na() : notFired.length ? bad(`did not fire: ${notFired.join(',')}`) : ok()

  // must_not (every question)
  const mustNotHits = (q.must_not ?? []).flatMap((p) => {
    const m = new RegExp(p, 'iu').exec(answer)
    return m ? [m[0]] : []
  })
  checks.must_not = errored ? na('errored run') : mustNotHits.length ? bad(`forbidden claim: ${mustNotHits.join(' | ')}`) : ok()

  // refusal
  if (q.expect === 'answer' || errored) checks.refusal = na()
  else {
    const why: string[] = []
    if (q.expect === 'refuse' && !REFUSAL_MARKER.test(answer)) why.push('no refusal wording')
    for (const key of q.held_reason ?? []) {
      const rx = HELD_REASON_PATTERNS[key]
      if (!rx) why.push(`unknown held_reason key ${key}`)
      else if (!rx.test(answer)) why.push(`held reason "${key}" not given`)
    }
    if (q.expect === 'refuse') {
      const nums = findUngroundedNumbers(answer, { texts: [q.text] })
      if (nums.length) why.push(`gave a number for a refused question: ${nums.map((n) => n.text).join(', ')}`)
    }
    if (mustNotHits.length) why.push(`forbidden claim: ${mustNotHits.join(' | ')}`)
    checks.refusal = why.length ? bad(why.join('; ')) : ok()
  }

  // right_tool / all_tools
  const called = obs.tools.map((t) => t.name)
  if (errored) {
    checks.right_tool = na('errored run')
    checks.all_tools = na('errored run')
  } else if (q.expected_tools.length === 0) {
    checks.right_tool = called.length === 0 ? ok() : bad(`no tool expected, called ${called.join(',')}`)
    checks.all_tools = na()
  } else {
    const first = q.expected_tools[0]
    const bundleOk =
      !q.expected_bundle ||
      obs.tools.some((t) => t.name === 'get_fact_cards' && (t.arguments as { bundle?: unknown } | null)?.bundle === q.expected_bundle)
    checks.right_tool = !called.includes(first)
      ? bad(`expected ${first}, called ${called.join(',') || 'none'}`)
      : !bundleOk
        ? bad(`expected bundle ${q.expected_bundle}`)
        : ok()
    const missingTools = q.expected_tools.filter((t) => !called.includes(t))
    checks.all_tools = missingTools.length ? bad(`not called: ${missingTools.join(',')}`) : ok()
  }

  checks.budget = errored ? na('errored run') : obs.budget.total <= RUN_TOKEN_LIMIT ? ok(`${obs.budget.total}`) : bad(`${obs.budget.total} tokens > ${RUN_TOKEN_LIMIT}`)

  const limitHits = obs.tools.filter((t) => t.reason === 'tool_call_limit').length
  const dispatched = obs.tools.length - limitHits
  checks.limits = errored
    ? na('errored run')
    : obs.rounds > MAX_ROUNDS || dispatched > MAX_TOOL_CALLS || limitHits > 0 || obs.loop_notes.includes('ROUND_LIMIT')
      ? bad(`rounds ${obs.rounds}, calls ${obs.tools.length} (${limitHits} over the limit)${obs.loop_notes.includes('ROUND_LIMIT') ? ', ROUND_LIMIT' : ''}`)
      : ok()

  const failures = CHECK_NAMES.filter((k) => checks[k].pass === false && k !== 'all_tools').map((k) => `${k}: ${checks[k].detail}`)
  return {
    question_id: q.id,
    repeat: obs.repeat,
    checks,
    all_pass: failures.length === 0,
    failures,
    checker: { failed: report.failed, fired },
  }
}
