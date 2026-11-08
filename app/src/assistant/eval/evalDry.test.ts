// AX-13 stubbed-model dry run: 3 canned (STUB) answers end to end through the real AX-10 loop, dispatcher,
// checker and grounding check, then the grader and the summary. Tool schemas are generated from the registry
// (every kind, held classes included), cards are the demo-card fixture, query/list are AX-10's test stubs.
// No network, no wasm. Plus: the teammate_race minimum wording (system.md) is sufficient and each part necessary,
// and the eval's constants stay in step with the Worker's.
// @vitest-environment node
import { describe, it, expect, beforeAll } from 'vitest'
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { registry } from '../cards/registry'
import { generateTools, type GeneratedTools } from '../core/nodeTools'
import { createDispatcher } from '../core/dispatcher'
import { ScriptedModel } from '../core/modelClient'
import { demoStore, testDeps, demoCards } from '../core/testKit'
import { createCardTable, grade, RUN_TOKEN_LIMIT, type GradeResult, type RunObservation } from './grade'
import { runEval } from './run'
import { QUESTIONS } from './questions'
import { stubScript, systemSentences } from './stubModel'
import { BAR, DAILY_NEURON_CAP, WORKER_MAX_OUTPUT_TOKENS, renderSummary, summarize } from './report'

const APP = resolve(import.meta.dirname, '../../..')
const WORKER = resolve(APP, '../worker')
let gen: GeneratedTools

beforeAll(async () => {
  gen = await generateTools({ catalogueJson: join(WORKER, 'test/fixtures/assistant/catalogue.json'), kinds: registry.map((s) => s.kind), appDir: APP })
})

const ids = ['tr-2024_1-VER', 'sc-all', 'lv-checo']

describe('AX-13 dry run: 3 STUB answers end to end', () => {
  let observations: RunObservation[]
  let grades: GradeResult[]
  beforeAll(async () => {
    const store = demoStore()
    const out = await runEval(
      QUESTIONS.filter((q) => ids.includes(q.id)),
      {
        repeats: 1,
        mode: 'STUB',
        modelFor: (q) => new ScriptedModel(stubScript(q)),
        deps: {
          store,
          loopDeps: (model) => ({ model, dispatcher: createDispatcher(testDeps({ tools: gen.tools })), store, system: gen.system, toolsJson: JSON.stringify(gen.tools) }),
        },
        table: createCardTable(demoCards),
      },
    )
    observations = out.observations
    grades = out.grades
  })

  it('runs the three questions once each, answered, with the expected first tool', () => {
    expect(observations.map((o) => o.question_id)).toEqual(ids)
    for (const o of observations) expect(o.status, o.question_id).toBe('answered')
    expect(observations.map((o) => o.tools[0]?.name)).toEqual(['get_fact_cards', 'get_fact_cards', 'list_values'])
  })

  it('every check of the bar passes on the three STUB answers, with no repair turn', () => {
    for (const g of grades) expect(g.failures, g.question_id).toEqual([])
    for (const o of observations) expect(o.repaired, o.question_id).toBe(false)
  })

  it('the teammate_race answer carries the two system.md sentences and the gap read from the card table', () => {
    const tr = observations[0]
    const S = systemSentences()
    expect(tr.answer).toContain(S.pit)
    expect(tr.answer).toContain(S.heldMeasures)
    const gap = demoCards.find((c) => c.id === 'race.teammate_gap:2024_1:VER')!
    expect(tr.answer).toContain(Math.abs(gap.value as number).toFixed(3))
    expect(grades[0].checks.expected_value.pass).toBe(true)
  })

  it('records cards received, tokens and rounds for each run; the summary renders', () => {
    for (const o of observations) {
      expect(o.budget.total).toBeGreaterThan(0)
      expect(o.budget.total).toBeLessThanOrEqual(RUN_TOKEN_LIMIT)
      expect(o.rounds).toBeGreaterThanOrEqual(2)
    }
    expect(observations[0].cards_received).toContain('race.teammate_gap:2024_1:VER')
    const s = summarize(QUESTIONS.filter((q) => ids.includes(q.id)), observations, grades, { status: 'not_applicable' }, 'STUB')
    expect(s.bar.grounded.pass && s.bar.refusal.pass && s.bar.right_tool.pass && s.bar.tokens.pass).toBe(true)
    expect(s.verdict).toBe('INCOMPLETE') // one repeat, human read not applicable
    expect(s.neurons.answers_per_day_at_cap).toBe(Math.floor(DAILY_NEURON_CAP / s.neurons.mean))
    expect(renderSummary(s, '# t', [])).toMatch(/## Verdict: INCOMPLETE/)
  })
})

describe('AX-13 teammate_race minimum wording (AX-10 finding 7)', () => {
  const table = createCardTable(demoCards)
  const q = QUESTIONS.find((x) => x.id === 'tr-2024_1-VER')!
  const gap = demoCards.find((c) => c.id === 'race.teammate_gap:2024_1:VER')!
  const S = systemSentences()
  const received = [
    'race.coverage:2024_1', 'race.teammate_gap:2024_1:VER', 'race.teammate_gap:2024_1:PER', 'race.result:2024_1:VER', 'race.cautions:2024_1', 'driver_race.pit_stops:2024_1:VER',
    ...demoCards.filter((c) => c.id.startsWith('race_driver.skill_components:2024_1:VER')).map((c) => c.id),
  ]
  const parts = {
    gap: `Verstappen was ${Math.abs(gap.value as number).toFixed(3)} s per lap faster than Perez, the teammate-paired median gap [card ${gap.id}].`,
    air: 'The laps were chosen with the air-state filter; it is not a dirty-air estimate.',
    pit: S.pit,
    heldMeasures: S.heldMeasures,
  }
  const run = (answer: string): RunObservation => ({
    question_id: q.id, repeat: 1, mode: 'test', status: 'answered', answer, tools: [{ name: 'get_fact_cards', arguments: { bundle: 'teammate_race' }, status: 'ok' }],
    cards_received: received, results: [], query_results: [], budget: { total: 4900, peak_context: 2600, rounds: 2, neurons: 92, estimated: true },
    rounds: 2, repaired: false, repair_skipped: false, first_draft_failed: [], loop_notes: [], usage_rounds: [],
  })

  it('gap + air-state clause + the two system.md sentences pass every check', () => {
    expect(grade(q, run(Object.values(parts).join(' ')), table).failures).toEqual([])
  })
  for (const drop of Object.keys(parts) as (keyof typeof parts)[])
    it(`dropping the ${drop} part fails`, () => {
      const answer = Object.entries(parts).filter(([k]) => k !== drop).map(([, v]) => v).join(' ')
      expect(grade(q, run(answer), table).all_pass, drop).toBe(false)
    })

  it('system.md quotes both sentences and stays within its 1,200-token slot', () => {
    const md = readFileSync(join(APP, 'src/assistant/prompt/system.md'), 'utf8').trim()
    expect(md).toContain(S.pit)
    expect(md).toContain(S.heldMeasures)
    expect(Math.ceil(md.length / 3.5)).toBeLessThanOrEqual(1200)
  })
})

describe('AX-13 constants in step with the Worker', () => {
  const config = readFileSync(join(WORKER, 'src/config.ts'), 'utf8')
  it('MAX_OUTPUT_TOKENS and the daily neuron cap', () => {
    expect(Number(/MAX_OUTPUT_TOKENS = (\d+)/.exec(config)?.[1])).toBe(WORKER_MAX_OUTPUT_TOKENS)
    expect(Number(/DEFAULT_DAILY_NEURON_CAP = (\d+)/.exec(config)?.[1])).toBe(DAILY_NEURON_CAP)
  })
  it('the bar is the AX-13 Decided bar', () => {
    expect([BAR.grounded_rate, BAR.refusal_rate, BAR.right_tool_rate_min, BAR.max_run_tokens, BAR.repeats]).toEqual([1, 1, 0.95, 18000, 5])
  })
})
