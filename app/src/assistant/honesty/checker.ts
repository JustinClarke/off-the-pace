// AI-02 honesty checker. Given a drafted answer and the fact cards it used, report which
// policy rules fired and whether each answer carries the required wording and avoids the
// forbidden claim. The rules are data (policy.json); this file only evaluates them.
//
// Verdicts per rule:
//   not_fired  no trigger held
//   pass       fired; every required group matched and no forbidden pattern matched
//   fail       fired; a required group is missing or a forbidden pattern matched
//   pending    fired, but the rule waits on an owner ruling (status pending_ruling)
// An answer passes overall when no active rule fails. Pending hits are listed separately.
import policyData from './policy.json'

/** A fact card as AI-01 defines it, plus the optional flags the triggers read. Loose on purpose
 *  until AI-01 lands its schema: unknown fields are allowed and read by dotted path. */
export interface FactCard {
  id: string
  metric: string
  value?: number | string | boolean | null
  unit?: string
  n?: number | null
  n_unit?: string
  interval?: { low: number; high: number; kind: string } | null
  scope?: Record<string, unknown>
  source_table?: string
  source_page?: string
  model_version?: string
  caveats?: string[]
  [field: string]: unknown
}

export interface CheckInput {
  question?: string
  answer: string
  cards: FactCard[]
}

type Op = 'eq' | 'ne' | 'lt' | 'lte' | 'gt' | 'gte' | 'in' | 'has' | 'matches'

export interface CardPredicate {
  field: string
  op: Op
  value: unknown
}

export type Trigger =
  | { card: CardPredicate[] }
  | { question: string }
  | { answer: string }
  | {
      cards_span_eras: {
        metric_matches: string
        season_field: string
        eras: [number, number][]
      }
    }

export interface SourceRef {
  file: string
  line: number | null
  quote: string
  /** The quote lives only in an uncommitted file. It is checked against git HEAD, and is
   *  reported as todo (not failed) until it is committed. Only allowed on pending_ruling rules. */
  pending_commit?: boolean
}

export type Verdict = 'not_fired' | 'pass' | 'fail' | 'pending'

export interface PolicyExample {
  name: string
  expect: Verdict
  input: CheckInput
}

export interface Rule {
  code: string
  kind: string
  status: 'active' | 'pending_ruling'
  ruling?: string
  applies_to: { pages: string[]; metrics: string[] }
  condition: string
  parameters?: Record<string, unknown>
  options?: string[]
  triggers: Trigger[]
  required_wording: { description: string; all_of: string[][] }
  forbidden_claim: { description: string; patterns: string[] }
  sources: SourceRef[]
  examples: PolicyExample[]
}

export interface Contradiction {
  id: string
  topic: string
  claims: SourceRef[]
  note: string
}

export interface Policy {
  schema_version: number
  policy_id: string
  kinds: Record<string, string>
  rules: Rule[]
  contradictions: Contradiction[]
}

export const policy = policyData as unknown as Policy

export interface RuleResult {
  code: string
  kind: string
  status: Rule['status']
  verdict: Verdict
  /** Human-readable reasons the rule fired (trigger and card id). */
  fired_by: string[]
  /** Required groups with no match, as their description plus the group's patterns. */
  missing_wording: string[][]
  /** Forbidden patterns that matched, with the matched text. */
  forbidden_hits: { pattern: string; text: string }[]
}

export interface CheckReport {
  ok: boolean
  failed: string[]
  pending: string[]
  results: RuleResult[]
}

const rx = (pattern: string): RegExp => new RegExp(pattern, 'iu')

function getPath(obj: unknown, path: string): unknown {
  let cur: unknown = obj
  for (const key of path.split('.')) {
    if (cur === null || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[key]
  }
  return cur
}

function testPredicate(card: FactCard, p: CardPredicate): boolean {
  const v = getPath(card, p.field)
  switch (p.op) {
    case 'eq':
      return v === p.value
    case 'ne':
      return v !== p.value
    case 'lt':
      return typeof v === 'number' && v < (p.value as number)
    case 'lte':
      return typeof v === 'number' && v <= (p.value as number)
    case 'gt':
      return typeof v === 'number' && v > (p.value as number)
    case 'gte':
      return typeof v === 'number' && v >= (p.value as number)
    case 'in':
      return Array.isArray(p.value) && (p.value as unknown[]).includes(v)
    case 'has':
      return Array.isArray(v) && (v as unknown[]).includes(p.value)
    case 'matches':
      return typeof v === 'string' && rx(String(p.value)).test(v)
  }
}

function eraOf(season: number, eras: [number, number][]): number {
  return eras.findIndex(([lo, hi]) => season >= lo && season <= hi)
}

function evalTrigger(t: Trigger, input: CheckInput): string[] {
  if ('card' in t) {
    return input.cards
      .filter((c) => t.card.every((p) => testPredicate(c, p)))
      .map((c) => `card ${c.id}: ${t.card.map((p) => `${p.field} ${p.op} ${JSON.stringify(p.value)}`).join(' and ')}`)
  }
  if ('question' in t) {
    return input.question && rx(t.question).test(input.question) ? ['question matches'] : []
  }
  if ('answer' in t) {
    return rx(t.answer).test(input.answer) ? ['answer matches'] : []
  }
  const { metric_matches, season_field, eras } = t.cards_span_eras
  const hit = input.cards.filter((c) => rx(metric_matches).test(c.metric))
  const seen = new Map<number, string>()
  for (const c of hit) {
    const season = getPath(c, season_field)
    if (typeof season !== 'number') continue
    const era = eraOf(season, eras)
    if (era >= 0 && !seen.has(era)) seen.set(era, c.id)
  }
  return seen.size > 1 ? [`cards ${[...seen.values()].join(', ')} span ${seen.size} eras`] : []
}

export function checkRule(rule: Rule, input: CheckInput): RuleResult {
  const fired_by = rule.triggers.flatMap((t) => evalTrigger(t, input))
  const base = { code: rule.code, kind: rule.kind, status: rule.status, fired_by, missing_wording: [], forbidden_hits: [] }
  if (fired_by.length === 0) return { ...base, verdict: 'not_fired' }
  if (rule.status === 'pending_ruling') return { ...base, verdict: 'pending' }

  const missing_wording = rule.required_wording.all_of.filter((group) => !group.some((p) => rx(p).test(input.answer)))
  const forbidden_hits = rule.forbidden_claim.patterns.flatMap((p) => {
    const m = rx(p).exec(input.answer)
    return m ? [{ pattern: p, text: m[0] }] : []
  })
  const verdict: Verdict = missing_wording.length === 0 && forbidden_hits.length === 0 ? 'pass' : 'fail'
  return { ...base, verdict, missing_wording, forbidden_hits }
}

/** Check a drafted answer against every rule in the policy (or a supplied rule list). */
export function checkAnswer(input: CheckInput, rules: Rule[] = policy.rules): CheckReport {
  const results = rules.map((r) => checkRule(r, input))
  const failed = results.filter((r) => r.verdict === 'fail').map((r) => r.code)
  const pending = results.filter((r) => r.verdict === 'pending').map((r) => r.code)
  return { ok: failed.length === 0, failed, pending, results }
}

/** Rule count by kind, for the AI-02 output. */
export function countByKind(rules: Rule[] = policy.rules): Record<string, number> {
  const out: Record<string, number> = {}
  for (const r of rules) out[r.kind] = (out[r.kind] ?? 0) + 1
  return out
}
