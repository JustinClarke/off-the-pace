// AX-13 question set: types, the loaded file, and its hash (the bar records it; a run refuses to count
// when the question file it used is not the one the bar was recorded for).
import data from './questions.json'
import { sha256Hex } from '../cards/sha256'
import type { PageContext } from '../core/preload'

export type QuestionClass = 'T' | 'T*' | 'WC' | 'ML' | 'X' | 'nav' | 'whatif'
export const QUESTION_CLASSES: readonly QuestionClass[] = ['T', 'T*', 'WC', 'ML', 'X', 'nav', 'whatif']
export type Expect = 'answer' | 'refuse' | 'hedge'

export interface ExpectedCard {
  kind: string
  /** Scope keys the card must carry. season "all" means the card has no season (pooled over every season). */
  scope: { season?: number | 'all'; race_id?: string; driver_id?: string; constructor_id?: string }
  /** The card id must end with ":<id_suffix>" (picks one of several cards in a scope, e.g. a pooled rate). */
  id_suffix?: string
  /** A correct answer states this card's value (read from the card table at grade time). */
  quote?: boolean
}

export interface Question {
  id: string
  group: 'a' | 'b' | 'c' | 'd' | 'e'
  text: string
  type: string
  class: QuestionClass
  family: string
  seasons: number[]
  page?: PageContext
  expected_tools: string[]
  expected_bundle?: string
  expected_cards: ExpectedCard[]
  expect: Expect
  held_reason?: string[]
  must_not?: string[]
  rules_should_fire: string[]
  demo?: boolean
  human_read?: boolean
}

export interface QuestionFile {
  version: number
  questions: Question[]
}

export const questionFile = data as unknown as QuestionFile
export const QUESTIONS: readonly Question[] = questionFile.questions

export interface QuestionCounts {
  questions: number
  by_tool: Record<string, number>
  query_data: number
  refuse_or_hedge: number
  families: string[]
  seasons: number[]
  by_class: Record<string, number>
  by_type: Record<string, number>
  by_group: Record<string, number>
  demo: number
  human_read: number
}

/** The method step 1 counts (every tool in 5+ questions, 15+ query_data, 8+ refuse/hedge, 4+ families, 3+ seasons). */
export function countQuestions(qs: readonly Question[] = QUESTIONS): QuestionCounts {
  const tally = (f: (q: Question) => string[]) => {
    const o: Record<string, number> = {}
    for (const q of qs) for (const k of new Set(f(q))) o[k] = (o[k] ?? 0) + 1
    return Object.fromEntries(Object.entries(o).sort(([a], [b]) => (a < b ? -1 : 1)))
  }
  const by_tool = tally((q) => q.expected_tools)
  return {
    questions: qs.length,
    by_tool,
    query_data: by_tool.query_data ?? 0,
    refuse_or_hedge: qs.filter((q) => q.expect !== 'answer').length,
    families: [...new Set(qs.map((q) => q.family))].sort(),
    seasons: [...new Set(qs.flatMap((q) => q.seasons))].filter((s) => s >= 2018 && s <= 2025).sort(),
    by_class: tally((q) => [q.class]),
    by_type: tally((q) => [q.type]),
    by_group: tally((q) => [q.group]),
    demo: qs.filter((q) => q.demo).length,
    human_read: qs.filter((q) => q.human_read).length,
  }
}

/**
 * Hash of the question file as it is versioned: the canonical JSON of the parsed file (stable across
 * whitespace-only edits, changes on any content edit). The bar records this value; the run checks it.
 */
export function questionsHash(file: QuestionFile = questionFile): string {
  return sha256Hex(JSON.stringify(file))
}
