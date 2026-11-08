// @vitest-environment node
// AX-10: the 10 sample questions and the 5 demo questions, headless, over real published files (the AX-04 Node
// adapter) with a SCRIPTED model: no network. Skipped unless AX06_DATA_DIR (a data root with assistant/qv, the
// catalogue and assistant_entities) and AX10_CARDS (a build-cards cards.json) are set. With AX10_EVIDENCE_DIR
// also set, writes sample-run.json and demo-run.json there.
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { registry, heldReasonFor } from '../cards/registry'
import { runQuestions, type RunRecord } from './cli'
import { createNodeRuntime, loadCardsJson, type NodeRuntime } from './nodeDeps'
import { generateTools } from './nodeTools'
import { SAMPLE_QUESTIONS, DEMO_QUESTIONS } from './sampleQuestions'
import { ScriptedModel } from './modelClient'
import { PEAK_TOKENS } from './budget'

const DATA = process.env.AX06_DATA_DIR
const CARDS = process.env.AX10_CARDS
const OUT = process.env.AX10_EVIDENCE_DIR
const enabled = !!DATA && !!CARDS && existsSync(join(DATA, 'assistant', 'catalogue.json')) && existsSync(CARDS)

describe.skipIf(!enabled)('AX-10 headless CLI over published files', () => {
  let rt: NodeRuntime
  let sample: RunRecord[]
  let demo: RunRecord[]
  let tokens: unknown

  beforeAll(async () => {
    const kinds = registry.map((s) => ({ kind: s.kind, held_reason: heldReasonFor(s) }))
    const gen = await generateTools({ catalogueJson: join(DATA!, 'assistant/catalogue.json'), kinds: kinds.map((k) => k.kind), appDir: resolve(__dirname, '../../..') })
    tokens = gen.tokens
    rt = await createNodeRuntime({ dataDir: DATA!, cards: loadCardsJson(CARDS!), tools: gen.tools, system: gen.system, kinds, specs: registry })
    const opts = { modelFor: (s: { script?: ConstructorParameters<typeof ScriptedModel>[0] }) => new ScriptedModel(s.script ?? []), depsFor: (m: ScriptedModel) => rt.loopDeps(m) }
    sample = await runQuestions(SAMPLE_QUESTIONS, opts)
    demo = await runQuestions(DEMO_QUESTIONS, opts)
    if (OUT) {
      mkdirSync(OUT, { recursive: true })
      writeFileSync(join(OUT, 'sample-run.json'), JSON.stringify({ mode: 'stub', tokens, records: sample }, null, 2))
      writeFileSync(join(OUT, 'demo-run.json'), JSON.stringify({ mode: 'stub', tokens, records: demo }, null, 2))
    }
  }, 120_000)
  afterAll(() => rt?.close())

  const by = (id: string) => sample.find((r) => r.id === id)!

  it('runs 10 samples: 3 card-only, 2 query_data, 1 list_values alias, 1 on-screen, 1 held, 1 what-if, 1 navigate', () => {
    expect(sample).toHaveLength(10)
    expect(sample.map((r) => r.kind.split(' ')[0])).toEqual(['card-only', 'card-only', 'card-only', 'query_data', 'query_data', 'list_values', 'on-screen', 'held', 'what-if', 'navigate'])
  })

  it('every sample is answered, passes the checker and the grounding check, with no notes', () => {
    for (const r of sample) {
      expect(r.status, r.id).toBe('answered')
      expect(r.checker.ok, `${r.id} ${r.checker.failed}`).toBe(true)
      expect(r.grounding.ungrounded, r.id).toEqual([])
      expect(r.notes, r.id).toEqual([])
    }
  })

  it('card-only questions make one get_fact_cards call; the bundle returns the recipe in that round', () => {
    for (const id of ['sample-1', 'sample-2', 'sample-3']) {
      expect(by(id).tools.map((t) => t.name)).toEqual(['get_fact_cards'])
      expect(by(id).cards_cited.length).toBeGreaterThan(0)
    }
    expect(by('sample-1').cards_cited).toEqual(expect.arrayContaining(['race.teammate_gap:2024_1:VER']))
  })

  it('query_data samples run the bounded builder on real files and quote its numbers', () => {
    for (const id of ['sample-4', 'sample-5']) {
      expect(by(id).tools[0]).toMatchObject({ name: 'query_data', status: 'ok' })
      expect(by(id).answer).toMatch(/computed from the data/)
    }
  })

  it('"Checo" resolves through list_values to Perez', () => {
    expect(by('sample-6').answer).toContain('PER')
  })

  it('the on-screen question needs 0 tool calls and cites the pre-loaded card', () => {
    const r = by('sample-7')
    expect(r.tools).toEqual([])
    expect(r.on_screen).toEqual(['race.cautions:2024_1'])
    expect(r.cards_cited).toEqual(['race.cautions:2024_1'])
  })

  it('the held-class question gets a held stub back and states the reason, no number', () => {
    const r = by('sample-8')
    expect(r.tools[0]).toMatchObject({ name: 'get_fact_cards', status: 'ok' })
    expect(r.checker.fired.map((f) => f.code)).toContain('HELD_CARD_WORDING')
    expect(r.answer.replace(/\[[^\]]*\]/g, '')).not.toMatch(/\d/) // no figure outside the citation
  })

  it('the what-if gets the Simulator link and no computed answer; navigate gets the pit page link', () => {
    expect(by('sample-9').links[0]).toContain('/ml/simulator')
    expect(by('sample-9').answer).toMatch(/do not compute/)
    expect(by('sample-10').links[0]).toContain('/tyre-strategy/pit-gantt')
  })

  it('every slot is reported and no run exceeds the 13,100 peak at the proposed slots', () => {
    for (const r of [...sample, ...demo]) {
      expect(r.budget.over_slot, r.id).toEqual([])
      expect(r.budget.peak_context, r.id).toBeLessThanOrEqual(PEAK_TOKENS)
      for (const k of ['instructions', 'tools', 'catalogue', 'page_context', 'history', 'tool_results', 'output']) expect(r.budget_line).toContain(`${k}=`)
    }
  })

  it('the 5 demo teammate_race questions are each one bundle call, one draft, within every slot', () => {
    expect(demo).toHaveLength(5)
    for (const r of demo) {
      expect(r.tools.map((t) => t.name), r.id).toEqual(['get_fact_cards'])
      expect(r.repaired, r.id).toBe(false)
      expect(r.checker.ok, r.id).toBe(true)
      expect(r.rounds).toBe(2)
    }
  })
})
