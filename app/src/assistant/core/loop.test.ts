import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ask, repairMessage, LIMIT_NOTE, MAX_ROUNDS } from './loop'
import { ScriptedModel, alwaysCalls } from './modelClient'
import { loopDeps, okQuery } from './testKit'
import { checkAnswer } from '../honesty/checker'
import { clearResults } from '../queryBuilder/store'
import { SLOTS } from './budget'

beforeEach(() => clearResults())

const HAM = 'race.teammate_gap:2020_14:HAM' // suppressed: 1 paired lap, rating_trust_label suppressed
const GOOD_HAM = `There is no reliable gap for Hamilton against Bottas in race 2020_14: no value for the teammate-paired median gap [card ${HAM}].`

describe('loop limit', () => {
  it('a stub that always asks for a tool is stopped after the 4th call and is told to answer from what it has', async () => {
    const model = alwaysCalls('list_values', { domain: 'driver', query: 'x' })
    const deps = loopDeps(model)
    const dispatch = vi.spyOn(deps.dispatcher, 'dispatch')
    const r = await ask('Who is x?', deps)
    expect(dispatch).toHaveBeenCalledTimes(4)
    expect(r.toolsCalled).toHaveLength(5) // the 5th ask is logged, refused as tool_call_limit, never dispatched
    expect(r.toolsCalled[4]).toMatchObject({ status: 'error', reason: 'tool_call_limit' })
    expect(r.rounds).toBe(MAX_ROUNDS)
    expect(r.status).toBe('no_answer')
    expect(r.notes[0]).toMatchObject({ kind: 'loop', code: 'ROUND_LIMIT' })
    // the model was told: the 4th result carries the note, and the last request shows it
    const last = model.requests[model.requests.length - 1].messages.filter((m) => m.role === 'tool')
    expect(last.some((m) => m.content.includes(LIMIT_NOTE))).toBe(true)
    expect(r.answer).not.toMatch(/\d/)
  })

  it('calls beyond the 4th inside one message get tool_call_limit and never reach the dispatcher', async () => {
    const five = Array.from({ length: 5 }, (_, i) => ({ name: 'list_values', arguments: { domain: 'driver', query: `q${i}` } }))
    const model = new ScriptedModel([{ tool_calls: five }, { content: 'I could only look up four names.' }])
    const deps = loopDeps(model)
    const dispatch = vi.spyOn(deps.dispatcher, 'dispatch')
    const r = await ask('Who are q0..q4?', deps)
    expect(dispatch).toHaveBeenCalledTimes(4)
    expect(r.toolsCalled).toHaveLength(5)
    expect(r.toolsCalled[4]).toMatchObject({ status: 'error', reason: 'tool_call_limit' })
    expect(r.status).toBe('answered')
    expect(r.rounds).toBe(2)
  })
})

describe('empty and refused calls go back to the model', () => {
  it('empty result: the answer says there is no data and contains no number', async () => {
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'query_data', arguments: { view: 'qv_stints', filters: [{ col: 'season', op: 'eq', val: 2024 }] } }] },
      { content: 'There is no data for that: the query matched no rows, so I cannot give a figure.' },
    ])
    const deps = loopDeps(model, { queryData: async () => ({ status: 'no_data', view: 'qv_stints', reason: 'no rows match the filters' }) })
    const r = await ask('How many pit stops did Zed make?', deps)
    expect(r.toolsCalled[0]).toMatchObject({ name: 'query_data', status: 'no_data' })
    expect(r.answer).toMatch(/no data/)
    expect(r.answer).not.toMatch(/\d/)
    expect(r.notes).toEqual([])
    // the tool message told the model it may retry once
    const tool = model.requests[1].messages.find((m) => m.role === 'tool')!
    expect(JSON.parse(tool.content).retry_hint).toMatch(/retry once/)
  })

  it('refused call (bad view, unknown tool): structured tool error; the next turn runs and the loop does not crash', async () => {
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'query_data', arguments: { view: 'laps_raw' } }, { name: 'drop_tables', arguments: {} }] },
      { content: 'I could not run that lookup, so I have no figure to give.' },
    ])
    const r = await ask('How many laps?', loopDeps(model))
    expect(r.toolsCalled.map((t) => t.status)).toEqual(['error', 'error'])
    const msgs = model.requests[1].messages
    const toolMsgs = msgs.filter((m) => m.role === 'tool').map((m) => JSON.parse(m.content))
    expect(toolMsgs[0]).toMatchObject({ status: 'error' })
    expect(toolMsgs[0].allowed).toContain('qv_laps')
    expect(toolMsgs[1]).toMatchObject({ status: 'error', reason: 'unknown tool' })
    expect(r.status).toBe('answered')
  })

  it('a held card is returned as a structured tool error with its reason', async () => {
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'get_fact_cards', arguments: { kinds: ['pit_strategy.verdict'], scopes: [{ race_id: '2023_6', driver_id: 'VER' }] } }] },
      { content: 'The pit-call verdict is held until the reproduction rate is re-measured; the app does not publish it yet.' },
    ])
    const deps = loopDeps(model, { kinds: [{ kind: 'pit_strategy.verdict', held_reason: 'held until the reproduction rate is re-measured' }] })
    const r = await ask('Was the pit call right?', deps)
    expect(r.toolsCalled[0]).toMatchObject({ status: 'error', reason: 'held' })
    const tool = JSON.parse(model.requests[1].messages.find((m) => m.role === 'tool')!.content)
    expect(tool.held[0].held_reason).toMatch(/re-measured/)
    expect(tool.retry_hint).toBeUndefined()
  })
})

describe('grounding triggers exactly one repair turn', () => {
  it('a number in no card or result fails, one repair message is sent, and the fixed draft passes', async () => {
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'get_fact_cards', arguments: { kinds: ['race.teammate_gap'], scopes: [{ race_id: '2024_1', driver_id: 'VER' }] } }] },
      { content: 'Verstappen was 0.71 s per lap faster than Perez [card race.teammate_gap:2024_1:VER]. The laps were chosen with the air-state filter; it is not a dirty-air estimate.' },
      { content: 'Verstappen was 0.62 s per lap faster than Perez, a median gap on 46 paired laps [card race.teammate_gap:2024_1:VER]. The laps were chosen with the air-state filter; it is not a dirty-air estimate.' },
    ])
    const r = await ask('How much faster was Verstappen than Perez in Bahrain 2024?', loopDeps(model))
    expect(r.repaired).toBe(true)
    expect(r.rounds).toBe(3)
    expect(model.requests).toHaveLength(3)
    const repair = model.requests[2].messages.at(-1)!
    expect(repair.role).toBe('user')
    expect(repair.content).toMatch(/no source/)
    expect(repair.content).toContain('0.71')
    expect(r.answer).toContain('0.62')
    expect(r.notes).toEqual([])
    expect(r.ungrounded).toEqual([])
    expect(r.cardsCited).toEqual(['race.teammate_gap:2024_1:VER'])
  })

  it('never more than one repair: a second ungrounded draft is returned with the failure as a note', async () => {
    const bad = 'Verstappen was 0.71 s per lap faster [card race.teammate_gap:2024_1:VER]. The laps were chosen with the air-state filter.'
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'get_fact_cards', arguments: { kinds: ['race.teammate_gap'], scopes: [{ race_id: '2024_1', driver_id: 'VER' }] } }] },
      { content: bad },
      { content: bad.replace('0.71', '0.73') },
    ])
    const r = await ask('How much faster?', loopDeps(model))
    expect(model.requests).toHaveLength(3)
    expect(r.repaired).toBe(true)
    expect(r.notes.filter((n) => n.kind === 'ungrounded').map((n) => n.detail)[0]).toContain('0.73')
    expect(r.answer).toContain('0.73') // returned, not silently replaced or passed
  })

  it('a grounded, compliant first draft sends no repair', async () => {
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'get_fact_cards', arguments: { kinds: ['race.teammate_gap'], scopes: [{ race_id: '2024_1', driver_id: 'VER' }] } }] },
      { content: 'Verstappen was 0.62 s per lap faster over 46 paired laps [card race.teammate_gap:2024_1:VER]. The laps were chosen with the air-state filter; it is not a dirty-air estimate.' },
    ])
    const r = await ask('How much faster?', loopDeps(model))
    expect(r.repaired).toBe(false)
    expect(model.requests).toHaveLength(2)
    expect(r.notes).toEqual([])
  })

  it('query_data numbers are grounded by the result the model saw', async () => {
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'query_data', arguments: { view: 'qv_stints', group_by: ['driver_id'], aggregate: { fn: 'count', col: 'stint' } } }] },
      { content: 'Verstappen had 31 stints and Perez 29 in 2024 [result q0000000001]. These are plain counts computed from the data, not a rating.' },
    ])
    const r = await ask('How many stints did VER and PER have in 2024?', loopDeps(model))
    expect(r.ungrounded).toEqual([])
    expect(r.repaired).toBe(false)
    expect(okQuery().rows).toHaveLength(2)
  })
})

describe('repair turn: required wording', () => {
  const askHam = (script: { content: string }[]) => {
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'get_fact_cards', arguments: { kinds: ['race.teammate_gap'], scopes: [{ race_id: '2020_14', driver_id: 'HAM' }] } }] },
      ...script,
    ])
    return { model, run: () => ask('Did Hamilton beat Bottas in race 2020_14?', loopDeps(model)) }
  }

  it('the fixture omits required wording: the first draft fails the checker', () => {
    const rep = checkAnswer({ answer: 'Hamilton beat Bottas in race 2020_14.', cards: [{ id: HAM, metric: 'teammate_gap_s', rating_trust_label: 'suppressed', label: 'unavailable', value: null, n: 0 }] })
    expect(rep.failed).toContain('RATING_TRUST_LABEL')
  })

  it('passes after the repair', async () => {
    const { model, run } = askHam([{ content: `Hamilton beat Bottas in race 2020_14 [card ${HAM}].` }, { content: GOOD_HAM }])
    const r = await run()
    expect(r.repaired).toBe(true)
    expect(r.notes).toEqual([])
    expect(r.check.ok).toBe(true)
    const repair = model.requests[2].messages.at(-1)!.content
    expect(repair).toContain('RATING_TRUST_LABEL')
    expect(repair).toMatch(/no reliable gap/i)
  })

  it('is flagged after a second failure: the draft comes back with the rule codes as notes', async () => {
    const { run } = askHam([{ content: `Hamilton beat Bottas [card ${HAM}].` }, { content: `Hamilton definitely beat Bottas [card ${HAM}].` }])
    const r = await run()
    expect(r.repaired).toBe(true)
    expect(r.check.ok).toBe(false)
    expect(r.notes.some((n) => n.kind === 'rule' && n.code === 'RATING_TRUST_LABEL')).toBe(true)
    expect(r.answer).toContain('definitely')
  })

  it('a repair that returns tool calls instead of text keeps the first draft, flagged', async () => {
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'get_fact_cards', arguments: { kinds: ['race.teammate_gap'], scopes: [{ race_id: '2020_14', driver_id: 'HAM' }] } }] },
      { content: `Hamilton beat Bottas [card ${HAM}].` },
      { tool_calls: [{ name: 'list_values', arguments: { domain: 'driver', query: 'ham' } }] },
    ])
    const r = await ask('q', loopDeps(model))
    expect(r.notes.some((n) => n.code === 'REPAIR_FAILED')).toBe(true)
    expect(r.answer).toContain('Hamilton beat Bottas')
  })

  it('repairMessage lists failed codes, the wording description and the ungrounded numbers', () => {
    const report = checkAnswer({ answer: 'Hamilton definitely beat Bottas.', cards: [{ id: HAM, metric: 'm', rating_trust_label: 'suppressed' }] })
    const msg = repairMessage(report, [{ text: '0.71', index: 0, context: 'x 0.71 y' }])
    expect(msg).toContain('RATING_TRUST_LABEL')
    expect(msg).toContain('definitely')
    expect(msg).toContain('0.71')
  })

  it('when all 5 rounds went on tool calls and the answer, no repair is possible and the notes say so', async () => {
    const call = (q: string) => ({ tool_calls: [{ name: 'list_values', arguments: { domain: 'driver', query: q } }] })
    const model = new ScriptedModel([call('a'), call('b'), call('c'), call('d'), { content: 'He was 9.99 s faster.' }])
    const r = await ask('q', loopDeps(model))
    expect(r.rounds).toBe(5)
    expect(r.repairSkipped).toBe(true)
    expect(r.notes.some((n) => n.code === 'REPAIR_SKIPPED')).toBe(true)
    expect(r.notes.some((n) => n.kind === 'ungrounded')).toBe(true)
  })
})

describe('page-card pre-load and wire shape', () => {
  it('an on-screen question needs 0 tool calls: the page card is in the first user message', async () => {
    const model = new ScriptedModel([{ content: 'It was under caution for 0 of 57 laps [card race.cautions:2024_1].' }])
    const deps = loopDeps(model)
    const r = await ask('How many laps were under caution in this race?', deps, {
      page: { route: '/race-craft/race-control', params: { season: 2024, race_id: '2024_1' } },
    })
    expect(r.toolsCalled).toEqual([])
    expect(r.onScreenIds).toEqual(['race.cautions:2024_1']) // page-wide pooled-rate cards are left out when a card is tied to the params
    expect(model.requests[0].messages[0].content).toContain('race.cautions:2024_1')
    expect(r.notes).toEqual([])
    expect(r.cardsCited).toEqual(['race.cautions:2024_1'])
  })

  it('assistant tool calls go out in OpenAI form with JSON-string arguments; roles are user|assistant|tool only', async () => {
    const model = new ScriptedModel([{ tool_calls: [{ name: 'list_values', arguments: { domain: 'driver', query: 'Checo' } }] }, { content: 'Checo is Sergio Perez (PER).' }])
    await ask('Who is Checo?', loopDeps(model))
    const msgs = model.requests[1].messages
    expect(msgs.map((m) => m.role)).toEqual(['user', 'assistant', 'tool'])
    const tc = (msgs[1].tool_calls as { id: string; type: string; function: { name: string; arguments: string } }[])[0]
    expect(tc).toMatchObject({ type: 'function', function: { name: 'list_values' } })
    expect(JSON.parse(tc.function.arguments)).toEqual({ domain: 'driver', query: 'Checo' })
    expect(msgs[2].tool_call_id).toBe(tc.id)
  })

  it('history: only the last two turns are replayed, as plain user/assistant text', async () => {
    const model = new ScriptedModel([{ content: 'Ok.' }])
    await ask('now?', loopDeps(model), {
      history: [1, 2, 3].map((n) => ({ question: `q${n}`, answer: `a${n} [card race.cautions:2024_1]` })),
    })
    expect(model.requests[0].messages.map((m) => m.content.slice(0, 2))).toEqual(['q2', 'a2', 'q3', 'a3', 'no'])
  })
})

describe('budget line', () => {
  it('every slot is reported and a run stays within the 13,100 peak', async () => {
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'query_data', arguments: { view: 'qv_stints', group_by: ['driver_id'], aggregate: { fn: 'count', col: 'stint' } } }], usage: { prompt_tokens: 2500, completion_tokens: 60 } },
      { content: 'Verstappen had 31 stints and Perez 29 [result q0000000001]. These are plain counts computed from the data, not a rating.', usage: { prompt_tokens: 3200, completion_tokens: 40 } },
    ])
    const r = await ask('q', loopDeps(model))
    for (const k of Object.keys(SLOTS)) expect(r.budgetText).toContain(`${k}=`)
    expect(r.budget.peak_context).toBeLessThanOrEqual(13_100)
    expect(r.budget.over_slot).toEqual([])
    expect(r.budget).toMatchObject({ total: 5800, rounds: 2, estimated: false })
    expect(r.budget.slots.tool_results).toBeGreaterThan(0)
  })

  it('a long tool result is truncated to its slot, rows_dropped is set, and it is on the budget line', async () => {
    const rows = Array.from({ length: 25 }, (_, i) => ({ driver_id: `D${i}`, lap_number: i, value: 90.5, n: 20, pad: 'p'.repeat(200) }))
    const big = { ...okQuery('q0000000009'), rows, row_count: 25, rows_shown: 25 }
    const model = new ScriptedModel([
      { tool_calls: [{ name: 'query_data', arguments: { view: 'qv_stints' } }] },
      { content: 'Too long to list.' },
    ])
    const r = await ask('q', loopDeps(model, { queryData: async () => big }))
    expect(r.budget.rows_dropped).toBeGreaterThan(0)
    const tool = JSON.parse(model.requests[1].messages.find((m) => m.role === 'tool')!.content)
    expect(tool.rows_dropped).toBeGreaterThan(0)
    expect(tool.truncated).toBe(true)
    expect(model.requests[1].messages.find((m) => m.role === 'tool')!.content.length).toBeLessThanOrEqual(5000)
  })
})
