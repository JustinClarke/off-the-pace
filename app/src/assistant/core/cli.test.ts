import { describe, it, expect } from 'vitest'
import { runQuestions, formatRecord, callTool, type QuestionSpec } from './cli'
import { ScriptedModel } from './modelClient'
import { loopDeps } from './testKit'
import { createDispatcher } from './dispatcher'
import { testDeps } from './testKit'
import { SAMPLE_QUESTIONS, DEMO_QUESTIONS } from './sampleQuestions'

describe('cli runner (stub model, demo cards, no data files)', () => {
  const specs: QuestionSpec[] = [
    {
      id: 'a',
      kind: 'card-only',
      question: 'On screen?',
      page: { route: '/race-craft/race-control', params: { season: 2024, race_id: '2024_1' } },
      script: [{ content: '0 laps were under caution, of 57 laps [card race.cautions:2024_1].' }],
    },
    { id: 'b', kind: 'list', question: 'Who is Checo?', script: [{ tool_calls: [{ name: 'list_values', arguments: { domain: 'driver', query: 'Checo' } }] }, { content: 'Checo is Sergio Perez (PER).' }] },
  ]

  it('runs each question on its own dispatcher and produces a record with answer, tools, cards, checker and budget', async () => {
    const recs = await runQuestions(specs, { modelFor: (s) => new ScriptedModel(s.script ?? []), depsFor: (m) => loopDeps(m) })
    expect(recs.map((r) => r.id)).toEqual(['a', 'b'])
    expect(recs[0]).toMatchObject({ tools: [], on_screen: ['race.cautions:2024_1'], cards_cited: ['race.cautions:2024_1'], status: 'answered' })
    expect(recs[1].tools[0]).toMatchObject({ name: 'list_values', status: 'ok' })
    expect(recs[1].budget.rounds).toBe(2)
    const text = formatRecord(recs[0])
    for (const part of ['answer:', 'tools:', 'cards cited:', 'checker:', 'grounding:', 'budget ']) expect(text).toContain(part)
  })

  it('the explain_page CLI call goes through the dispatcher', async () => {
    const d = createDispatcher(testDeps())
    const r = (await callTool(d, 'explain_page', { page: '/drivers/era-translator' })) as { status: string; page_id: string }
    expect(r).toMatchObject({ status: 'ok', page_id: 'era-translator' })
  })

  it('has the 10 sample and 5 demo questions, each with a script', () => {
    expect(SAMPLE_QUESTIONS).toHaveLength(10)
    expect(DEMO_QUESTIONS).toHaveLength(5)
    for (const q of [...SAMPLE_QUESTIONS, ...DEMO_QUESTIONS]) expect(q.script?.length).toBeGreaterThan(0)
    expect(new Set(SAMPLE_QUESTIONS.map((q) => q.id)).size).toBe(10)
  })
})
