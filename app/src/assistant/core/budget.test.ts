import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  BudgetMeter, HISTORY_TURNS, NEURONS_PER_M_INPUT, NEURONS_PER_M_OUTPUT, PEAK_TOKENS, SLOTS, TOOL_RESULT_SLOT,
  fitHistory, fitToolResult, formatBudgetLine, neuronsFor, splitSystemPrompt, tokensOf,
} from './budget'
import { system, toolsJson } from './testKit'

describe('budget slots', () => {
  it('sum to the spec peak of 13,100', () => {
    expect(PEAK_TOKENS).toBe(13_100)
    expect(SLOTS.tool_results).toBe(4 * TOOL_RESULT_SLOT)
  })

  it('neuron rates and formula stay in step with the Worker', () => {
    const cfg = readFileSync(join(__dirname, '../../../../worker/src/config.ts'), 'utf8')
    expect(cfg).toContain(`NEURONS_PER_M_INPUT = ${NEURONS_PER_M_INPUT}`)
    expect(cfg).toContain(`NEURONS_PER_M_OUTPUT = ${NEURONS_PER_M_OUTPUT}`)
    expect(neuronsFor({ prompt_tokens: 1_000_000, completion_tokens: 0 })).toBe(18_182)
    expect(neuronsFor({ prompt_tokens: 0, completion_tokens: 1_000_000 })).toBe(27_273)
    expect(neuronsFor(null)).toBe(0)
  })
})

describe('fitToolResult', () => {
  it('leaves a small result alone', () => {
    const f = fitToolResult({ status: 'ok', rows: [{ a: 1 }] })
    expect(f.truncated).toBe(false)
    expect(f.rows_dropped).toBe(0)
  })

  it('truncates to the 1,200-token slot and sets rows_dropped', () => {
    const rows = Array.from({ length: 200 }, (_, i) => ({ driver_id: 'VER', lap_number: i, value: 90.123, n: 3, note: 'x'.repeat(20) }))
    const f = fitToolResult({ status: 'ok', rows })
    expect(f.tokens).toBeLessThanOrEqual(TOOL_RESULT_SLOT)
    expect(f.truncated).toBe(true)
    expect(f.rows_dropped).toBeGreaterThan(0)
    expect((f.result.rows as unknown[]).length + f.rows_dropped).toBe(200)
    expect(f.result.rows_dropped).toBe(f.rows_dropped)
    expect(JSON.parse(f.text).rows_dropped).toBe(f.rows_dropped)
    expect(f.text.length).toBeLessThanOrEqual(5000) // the Worker's per-tool-message cap
  })

  it('adds to a rows_dropped the tool already set', () => {
    const rows = Array.from({ length: 150 }, (_, i) => ({ g: i, value: 1.5, n: 3, pad: 'y'.repeat(30) }))
    const f = fitToolResult({ status: 'ok', rows, rows_dropped: 7 })
    expect(f.result.rows_dropped).toBe(7 + f.rows_dropped)
  })

  it('trims the cards list of a get_fact_cards result the same way', () => {
    const cards = Array.from({ length: 40 }, (_, i) => ({ id: `k:${i}`, m: 'metric name', v: i + 0.123456, n: '30 laps', cav: ['A', 'B'], pad: 'z'.repeat(40) }))
    const f = fitToolResult({ status: 'ok', cards })
    expect(f.tokens).toBeLessThanOrEqual(TOOL_RESULT_SLOT)
    expect(f.rows_dropped).toBeGreaterThan(0)
  })

  it('a result with no row list that is too long becomes an explicit refusal, never cut JSON', () => {
    const f = fitToolResult({ status: 'ok', summary: 'w'.repeat(9000) })
    expect(JSON.parse(f.text)).toMatchObject({ status: 'error', reason: 'result_too_large' })
  })
})

describe('fitHistory', () => {
  const t = (n: number, size = 40) => ({ question: `q${n}`, answer: 'a'.repeat(size) })
  it('keeps the last two turns', () => {
    const h = fitHistory([t(1), t(2), t(3)])
    expect(h.turns.map((x) => x.question)).toEqual(['q2', 'q3'])
    expect(h.turns).toHaveLength(HISTORY_TURNS)
  })
  it('drops the oldest turn before the slot overflows', () => {
    const h = fitHistory([t(1, 9000), t(2, 9000)], 2000)
    expect(h.turns.map((x) => x.question)).toEqual([])
    const h2 = fitHistory([t(1, 6000), t(2, 3000)], 2000)
    expect(h2.turns.map((x) => x.question)).toEqual(['q2'])
    expect(h2.tokens).toBeLessThanOrEqual(2000)
  })
})

describe('BudgetMeter', () => {
  it('splits the system prompt into instructions and the query catalogue and counts both slots', () => {
    const s = splitSystemPrompt(system)
    expect(s.catalogue).toContain('Data views for query_data')
    const m = new BudgetMeter()
    m.setStatic(system, toolsJson)
    const l = m.line()
    expect(l.slots.instructions).toBe(tokensOf(s.instructions))
    expect(l.slots.catalogue).toBe(tokensOf(s.catalogue))
    expect(l.slots.tools).toBe(tokensOf(toolsJson))
    expect(l.slots.instructions).toBeLessThanOrEqual(SLOTS.instructions)
    expect(l.slots.tools).toBeLessThanOrEqual(SLOTS.tools)
    expect(l.slots.catalogue).toBeLessThanOrEqual(SLOTS.catalogue)
  })

  it('uses usage when present and marks chars/4 as estimated otherwise', () => {
    const a = new BudgetMeter()
    a.recordRound({ prompt_tokens: 3000, completion_tokens: 200 }, 99999, 'ignored')
    expect(a.line()).toMatchObject({ total: 3200, rounds: 1, estimated: false })
    expect(a.line().neurons).toBe(neuronsFor({ prompt_tokens: 3000, completion_tokens: 200 }))
    const b = new BudgetMeter()
    b.recordRound(null, 4000, 'x'.repeat(400))
    expect(b.line()).toMatchObject({ total: 1100, estimated: true })
  })

  it('the log line names every slot, total, rounds and neurons', () => {
    const m = new BudgetMeter()
    m.setStatic(system, toolsJson)
    m.recordRound(null, 1000, 'hello')
    const line = formatBudgetLine(m.line())
    for (const k of Object.keys(SLOTS)) expect(line).toContain(`${k}=`)
    expect(line).toMatch(/total=\d+ rounds=1 neurons=\d+/)
  })
})
