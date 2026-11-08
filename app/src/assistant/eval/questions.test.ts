// AX-13 question file: schema, method step 1 counts, no typed expected numbers, every expected card kind is in
// the registry or declared held (playbook pending_kinds), every question has a STUB plan, and (authoring check,
// no model) the rules a question says should fire do fire on the cards its correct tool calls return.
// The full-table part runs only with AX10_CARDS set (a build-cards cards.json).
// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'

import { QUESTIONS, QUESTION_CLASSES, countQuestions, questionsHash, questionFile } from './questions'
import { HELD_REASON_PATTERNS, PENDING_KINDS, createCardTable, resolveExpected } from './grade'
import { STUB_PLANS } from './stubModel'
import { registry } from '../cards/registry'
import { playbook } from '../prompt/bundles'
import { TOOL_NAMES, createDispatcher } from '../core/dispatcher'
import { createCardStore } from '../core/cardStore'
import { testDeps, demoCards } from '../core/testKit'
import { toCheckerCard } from '../cards/project'
import { checkAnswer, policy } from '../honesty/checker'
import type { Card } from '../cards/card.types'

const CODES = new Set(policy.rules.map((r) => r.code))
const KINDS = new Set(registry.map((s) => s.kind))
const TYPES = new Set(playbook.types.map((t) => t.type))

describe('AX-13 questions.json schema', () => {
  it('every question has the fields of method step 1, with known values', () => {
    const ids = new Set<string>()
    for (const q of QUESTIONS) {
      expect(ids.has(q.id), `duplicate ${q.id}`).toBe(false)
      ids.add(q.id)
      expect(q.text.length, q.id).toBeGreaterThan(8)
      expect(TYPES.has(q.type), `${q.id} type ${q.type}`).toBe(true)
      expect(QUESTION_CLASSES).toContain(q.class)
      expect(['a', 'b', 'c', 'd', 'e']).toContain(q.group)
      expect(['answer', 'refuse', 'hedge']).toContain(q.expect)
      for (const t of q.expected_tools) expect(TOOL_NAMES as readonly string[], `${q.id} tool ${t}`).toContain(t)
      if (q.expected_bundle) expect(playbook.types.find((t) => t.type === q.expected_bundle)?.bundle, `${q.id} bundle`).toBe(true)
      for (const c of q.rules_should_fire) expect(CODES.has(c), `${q.id} rule ${c}`).toBe(true)
      for (const p of q.must_not ?? []) expect(() => new RegExp(p, 'iu'), `${q.id} must_not ${p}`).not.toThrow()
      if (q.expect !== 'answer') {
        expect(q.held_reason?.length, `${q.id} refuse/hedge needs held_reason`).toBeGreaterThan(0)
        for (const k of q.held_reason ?? []) expect(HELD_REASON_PATTERNS[k], `${q.id} held_reason ${k}`).toBeInstanceOf(RegExp)
      }
      if (q.expect === 'refuse') expect(q.expected_cards.some((e) => e.quote), `${q.id}: a refusal quotes nothing`).toBe(false)
    }
  })

  it('every expected_cards kind is in the registry or declared held (playbook pending_kinds)', () => {
    for (const q of QUESTIONS) for (const e of q.expected_cards) expect(KINDS.has(e.kind) || PENDING_KINDS.includes(e.kind), `${q.id} ${e.kind}`).toBe(true)
    expect(PENDING_KINDS).toEqual(['ml.cliff_probability', 'ml.prediction_band'])
  })

  it('no typed expected numbers: outside the question text and the season fields, the file carries no number', () => {
    for (const q of QUESTIONS) {
      const rest = {
        ...q,
        text: undefined,
        seasons: undefined,
        page: q.page ? { ...q.page, params: { ...q.page.params, season: undefined } } : undefined,
        expected_cards: q.expected_cards.map((e) => ({ ...e, scope: { ...e.scope, season: undefined } })),
      }
      const s = JSON.stringify(rest)
      // ids like 2024_1 and race scopes are keys, not values: strip them, then no digit run may remain outside ids.
      const stripped = s.replace(/\b\d{4}_\d{1,2}\b/g, '').replace(/"(must_not)":\[[^\]]*\]/g, '')
      expect(stripped, q.id).not.toMatch(/\d+\.\d+/)
      expect(stripped, q.id).not.toMatch(/:\s*-?\d+(?:[,}\]])/)
    }
  })

  it('every question has a STUB plan, and every plan a question', () => {
    expect(Object.keys(STUB_PLANS).sort()).toEqual(QUESTIONS.map((q) => q.id).sort())
  })

  it('the hash is stable and changes with any content edit', () => {
    expect(questionsHash()).toMatch(/^[0-9a-f]{64}$/)
    expect(questionsHash()).toBe(questionsHash())
    const edited = JSON.parse(JSON.stringify(questionFile))
    edited.questions[0].text += '?'
    expect(questionsHash(edited)).not.toBe(questionsHash())
  })
})

describe('AX-13 method step 1 counts', () => {
  const c = countQuestions()
  it('every one of the 7 tools in at least 5 questions', () => {
    for (const t of TOOL_NAMES) expect(c.by_tool[t] ?? 0, t).toBeGreaterThanOrEqual(5)
  })
  it('at least 15 need query_data, at least 8 refuse or hedge', () => {
    expect(c.query_data).toBeGreaterThanOrEqual(15)
    expect(c.refuse_or_hedge).toBeGreaterThanOrEqual(8)
  })
  it('at least 4 families and 3 seasons', () => {
    expect(c.families.length).toBeGreaterThanOrEqual(4)
    expect(c.seasons.length).toBeGreaterThanOrEqual(3)
  })
  it('the groups of method step 2 are all present: live kinds, every v1 type twice, chains, held classes, nav', () => {
    const live = registry.filter((s) => s.class === 'T' && !String(s.kind).startsWith('pit_strategy.') && s.kind !== 'race_lost.component').map((s) => s.kind)
    const quoted = new Set(QUESTIONS.flatMap((q) => q.expected_cards.map((e) => e.kind)))
    for (const k of live) expect(quoted.has(k), `live kind ${k} has a question`).toBe(true)
    for (const t of ['teammate_race', 'why_slow', 'season_standing', 'stint_describe', 'safety_car_rate', 'tyre_life', 'corner_phase', 'observed_count'])
      expect(c.by_type[t] ?? 0, t).toBeGreaterThanOrEqual(2)
    for (const g of ['a', 'b', 'c', 'd', 'e']) expect(c.by_group[g] ?? 0, g).toBeGreaterThan(0)
    for (const k of ['T', 'T*', 'WC', 'ML', 'X', 'nav', 'whatif']) expect(c.by_class[k] ?? 0, k).toBeGreaterThan(0)
    expect(c.demo).toBe(5)
    expect(c.human_read).toBe(10)
  })
  it('the forbidden chains of the audit each have a question (group c)', () => {
    const c2 = QUESTIONS.filter((q) => q.group === 'c').map((q) => q.id)
    for (const id of ['x-sc-monaco', 'x-skill-mix-2024', 'x-affinity-era', 'x-would-have-won-2022', 'x-blind-test', 'x-lap-map-grey', 'x-sector-2023_10-VER', 'x-2026', 'x-cross-era', 'x-chance-line'])
      expect(c2, id).toContain(id)
  })
})

/** The cards the question's correct get_fact_cards calls (its STUB plan) return, through the real dispatcher. */
async function cardsFor(id: string, cards: readonly Card[]): Promise<Card[]> {
  const deps = testDeps({ cards: createCardStore(cards) })
  const d = createDispatcher(deps)
  const q = QUESTIONS.find((x) => x.id === id)!
  if (q.page) for (const c of deps.cards.onPage(q.page.route, q.page.params)) d.session.cards.set(c.id, c)
  for (const round of STUB_PLANS[id].rounds)
    for (const call of round) {
      if (call.name !== 'get_fact_cards') continue
      const a = call.arguments as { bundle?: string; kinds?: string[]; scopes?: Record<string, unknown>[] }
      // A bundle goes through the dispatcher. A kinds call is resolved on the store directly: the worker's checked-in
      // tools.ts carries an older kinds enum (AX-10 finding 4); the CLI and the eval regenerate it from the registry.
      if (a.bundle) await d.dispatch({ id: 'a', name: call.name, arguments: call.arguments })
      else for (const sc of a.scopes ?? []) for (const c of deps.cards.find(sc, a.kinds ?? []).slice(0, 10)) d.session.cards.set(c.id, c)
    }
  return [...d.session.cards.values()]
}

function firedOn(id: string, cards: Card[]): string[] {
  const q = QUESTIONS.find((x) => x.id === id)!
  const checker = cards.map(toCheckerCard)
  if (q.expected_tools.includes('query_data')) checker.push({ id: 'q1', metric: 'v.c', label: 'computed_not_card', n: 3, n_unit: 'rows', source_page: 'qv' })
  return checkAnswer({ question: q.text, answer: '', cards: checker })
    .results.filter((r) => r.verdict !== 'not_fired')
    .map((r) => r.code)
}

describe('AX-13 rules_should_fire (authoring check over the demo-card fixture)', () => {
  const inFixture = ['tr-2024_1-VER', 'tr-2020_14-HAM', 'tr-2018_1-RIC', 'tr-2021_16-HAM', 'tr-2024_5-NOR', 'ss-2024-NOR', 'sc-all', 'cp-2024-NOR', 'cp-2024-VER', 'sd-2024_1-VER', 'sd-2024_5-NOR']
  for (const id of inFixture)
    it(`${id}: the listed rules fire on the fetched cards`, async () => {
      const fired = firedOn(id, await cardsFor(id, demoCards))
      const q = QUESTIONS.find((x) => x.id === id)!
      for (const c of q.rules_should_fire) expect(fired, `${id} ${c}`).toContain(c)
    })
})

const CARDS = process.env.AX10_CARDS
describe.skipIf(!CARDS || !existsSync(CARDS))('AX-13 questions over the full card table (AX10_CARDS)', () => {
  const cards = CARDS ? (JSON.parse(readFileSync(CARDS, 'utf8')) as Card[]) : []
  const table = createCardTable(cards)
  it('every expected card of a registered kind resolves to at least one card; quote cards to exactly one value each', () => {
    for (const q of QUESTIONS)
      for (const e of q.expected_cards) {
        if (PENDING_KINDS.includes(e.kind)) continue
        const hits = resolveExpected(table, e)
        expect(hits.length, `${q.id} ${e.kind} ${JSON.stringify(e.scope)}`).toBeGreaterThan(0)
        if (e.quote) expect(hits.length, `${q.id} quote ${e.kind}`).toBe(1)
      }
  })
  it('every listed rule fires on the cards the correct calls return', async () => {
    const bad: string[] = []
    for (const q of QUESTIONS) {
      const fired = firedOn(q.id, await cardsFor(q.id, cards))
      for (const c of q.rules_should_fire) if (!fired.includes(c)) bad.push(`${q.id} ${c}`)
    }
    expect(bad).toEqual([])
  }, 60_000)
  it('the demo-card fixture is the same data for the demo races (no drift)', () => {
    for (const c of demoCards) expect(table.byId(c.id)?.value ?? null, c.id).toEqual(c.value)
  })
})


