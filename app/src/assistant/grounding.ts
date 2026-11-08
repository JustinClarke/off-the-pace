// AX-10 grounding check: every number in an answer maps to a card returned this session or to a
// query_data result (design 2.5/2.8, AD3). AX-14 calls the same function at render time: do not fork it.
//
// What counts as a source number: a card's value, interval ends and level, n, display and reason texts; every number in a query result
// (rows, n, counts, filters, notes); numbers the user typed in the question. Matching is at the answer
// number's own precision (0.62 matches 0.6219), sign-blind ("0.62 s faster" for -0.62), and a number
// followed by % also matches the source x 100. A whole number must match a whole source number exactly
// (so "1" never matches 0.8); it may round a source of 10 or more ("47 laps" for 46.8).
//
// What is not checked: a 4-digit year 1950-2099, digits inside an id (race.result:2024_1:VER, 2024_1),
// a bracketed citation, a list marker at a line start, and a number glued to letters before it (F1, v16, CO-16).
// "round 5" / "race 5" is accepted when a source carries a race id ending in _5.
import type { Card } from './cards/card.types'
import type { FactCard } from './honesty/checker'

type CardLike = Card | FactCard

export interface GroundingSources {
  /** Cards returned this session (full cards or checker cards). */
  cards?: readonly CardLike[]
  /** query_data results returned this session (any object; every number in it is a source). */
  results?: readonly unknown[]
  /** Other text the model saw: the question, the page-context block. */
  texts?: readonly string[]
}

export interface AnswerNumber {
  text: string
  value: number
  decimals: number
  percent: boolean
  index: number
}

export interface UngroundedNumber {
  text: string
  index: number
  /** About 40 characters either side, for the repair message and the note under the answer. */
  context: string
}

const ID_TOKEN = /\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+:[A-Za-z0-9_:.*-]+/g
const RACE_ID = /\b(\d{4})_(\d{1,2})\b/g
const BRACKET_CITE = /\[[^\]\n]{0,160}\]/g

function blank(text: string, rx: RegExp): string {
  return text.replace(rx, (m) => ' '.repeat(m.length))
}

/** Numbers the checker looks at, with their position in `answer`. */
export function extractAnswerNumbers(answer: string): AnswerNumber[] {
  // Blank (not delete) the exempt spans so indices stay valid.
  let t = blank(answer, BRACKET_CITE)
  t = blank(t, ID_TOKEN)
  t = blank(t, RACE_ID)
  t = t.replace(/^[ \t]*\d{1,2}[.)](?=\s)/gm, (m) => ' '.repeat(m.length))
  const out: AnswerNumber[] = []
  const rx = /(?<![A-Za-z0-9_.])(?<![A-Za-z]-)(P)?(\d[\d,]*)(?:\.(\d+))?(%)?/g
  let m: RegExpExecArray | null
  while ((m = rx.exec(t)) !== null) {
    const prefix = m[1] ?? ''
    const intPart = m[2].replace(/,/g, '')
    const frac = m[3]
    // A bare P is a position marker only when a digit follows; the lookbehind already ruled out words.
    const text = `${prefix}${m[2]}${frac !== undefined ? '.' + frac : ''}${m[4] ?? ''}`
    const value = Number(frac !== undefined ? `${intPart}.${frac}` : intPart)
    if (!Number.isFinite(value)) continue
    // Trailing decimal point of a sentence ("... 46.") is not part of the number: regex needs digits after '.'.
    const isYear = frac === undefined && !m[4] && !prefix && /^\d{4}$/.test(intPart) && value >= 1950 && value <= 2099
    if (isYear) continue
    out.push({ text, value, decimals: frac?.length ?? 0, percent: !!m[4], index: m.index })
  }
  return out
}

function pushNumber(into: number[], v: unknown): void {
  if (typeof v === 'number' && Number.isFinite(v)) into.push(Math.abs(v))
}

function numbersInText(text: string, into: number[]): void {
  const t = blank(blank(blank(text, BRACKET_CITE), ID_TOKEN), RACE_ID)
  for (const m of t.matchAll(/(?<![A-Za-z0-9_.])(?<![A-Za-z]-)(\d[\d,]*)(?:\.(\d+))?/g)) {
    pushNumber(into, Number(m[2] !== undefined ? `${m[1].replace(/,/g, '')}.${m[2]}` : m[1].replace(/,/g, '')))
  }
}

function walk(v: unknown, into: number[], depth = 0): void {
  if (depth > 8) return
  if (typeof v === 'number') pushNumber(into, v)
  else if (typeof v === 'string') numbersInText(v, into)
  else if (Array.isArray(v)) for (const x of v) walk(x, into, depth + 1)
  else if (v && typeof v === 'object') for (const x of Object.values(v)) walk(x, into, depth + 1)
}

/** The numbers one card grounds (value, interval ends, n, numbers in its display and reason texts). */
export function sourceNumbersOfCard(c: CardLike): number[] {
  const out: number[] = []
  cardNumbers(c, out)
  return out
}

function cardNumbers(c: CardLike, into: number[]): void {
  const o = c as Record<string, unknown>
  if (typeof o.value === 'number') pushNumber(into, o.value)
  const iv = o.interval as { low?: unknown; high?: unknown; level?: unknown } | null | undefined
  if (iv) {
    pushNumber(into, iv.low)
    pushNumber(into, iv.high)
    // "a 95% interval" is the card's own interval level: a source only for a percent figure (see levels()).
  }
  for (const f of ['display', 'unavailable_reason', 'held_reason']) if (typeof o[f] === 'string') numbersInText(o[f] as string, into)
  const n = o.n
  if (typeof n === 'number') pushNumber(into, n)
  else if (n && typeof n === 'object') pushNumber(into, (n as { count?: unknown }).count)
}

/** Interval levels (0.95): they ground "95%" and nothing else (0.95 must not ground "0.9"). */
function levels(sources: GroundingSources): number[] {
  const out: number[] = []
  for (const c of sources.cards ?? []) {
    const iv = (c as { interval?: { level?: unknown; kind?: unknown } | null }).interval
    if (!iv) continue
    if (typeof iv.level === 'number') out.push(iv.level)
    else if (/_95$/.test(String(iv.kind ?? ''))) out.push(0.95)
  }
  return out
}

function raceNumbers(sources: GroundingSources): Set<number> {
  const out = new Set<number>()
  const scan = (s: string) => {
    for (const m of s.matchAll(RACE_ID)) out.add(Number(m[2]))
  }
  for (const c of sources.cards ?? []) {
    scan(String((c as { id?: unknown }).id ?? ''))
    const rid = (c as { scope?: { race_id?: unknown } }).scope?.race_id
    if (typeof rid === 'string') scan(rid)
  }
  for (const r of sources.results ?? []) scan(JSON.stringify(r))
  for (const t of sources.texts ?? []) scan(t)
  return out
}

/** All source numbers (absolute values). */
export function collectSourceNumbers(sources: GroundingSources): number[] {
  const nums: number[] = []
  for (const c of sources.cards ?? []) cardNumbers(c, nums)
  for (const r of sources.results ?? []) walk(r, nums)
  for (const t of sources.texts ?? []) numbersInText(t, nums)
  return nums
}

/** True when the source number s grounds the answer number a (same rule findUngroundedNumbers uses). AX-14 uses it to pick the card behind a chip. */
export function numberMatches(a: AnswerNumber, s: number): boolean {
  const candidates = a.percent ? [s, s * 100] : [s]
  return candidates.some((c) => {
    if (a.decimals >= 1) return Math.abs(c - a.value) <= 0.5 * 10 ** -a.decimals + 1e-9
    if (Number.isInteger(c) || Math.abs(c - Math.round(c)) < 1e-9) return Math.round(c) === a.value
    return c >= 10 && Math.round(c) === a.value
  })
}

/**
 * Numbers in `answer` that match no source. Empty means grounded. AX-14 reuses it at render time.
 */
export function findUngroundedNumbers(answer: string, sources: GroundingSources): UngroundedNumber[] {
  const src = collectSourceNumbers(sources)
  const lv = levels(sources)
  const races = raceNumbers(sources)
  const bad: UngroundedNumber[] = []
  for (const a of extractAnswerNumbers(answer)) {
    const abs: AnswerNumber = { ...a, value: Math.abs(a.value) }
    if (src.some((s) => numberMatches(abs, s))) continue
    if (a.percent && lv.some((l) => numberMatches(abs, l))) continue
    const before = answer.slice(Math.max(0, a.index - 14), a.index)
    if (a.decimals === 0 && !a.percent && races.has(a.value) && /\b(round|race|grand prix|gp)\s*$/i.test(before)) continue
    bad.push({
      text: a.text,
      index: a.index,
      context: answer.slice(Math.max(0, a.index - 40), a.index + a.text.length + 40).replace(/\s+/g, ' ').trim(),
    })
  }
  return bad
}
